import json
import logging
import os
import re
from difflib import get_close_matches
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class PartyNormalizer:
    def __init__(self, data_path: str = None):
        if data_path is None:
            # Default to ../dets.json relative to this file
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.data_path = os.path.join(base_dir, "dets.json")
        else:
            self.data_path = data_path
        
        self.mapping: Dict[str, str] = {}
        self.known_parties = {
            "DMK", "AIADMK", "BJP", "INC", "PMK", "NTK", "VCK",
            "CPI", "CPI(M)", "DMDK", "MDMK", "TMC(M)", "AMMK", "IUML", "IND"
        }
        self.non_candidate_headers = {
            # Serial numbers
            "sl. no", "sl.no", "slno", "s.no", "s no", "serial number", "sr no", "sr. no",
            "ps no.", "ps no", "polling station no", "polling station number",

            # Totals and aggregates
            "total", "total votes", "total valid votes", "grand total", "sum",
            "total votes polled", "total electors",

            # Special voter categories
            "nota", "none of the above",
            "overseas electors", "service electors", "postal ballot",
            "tendred votes", "challenged votes",

            # Metadata fields
            "remarks", "notes", "date", "time", "place",
            "constituency", "constituency name", "assembly constituency",
            "part no", "part number", "booth no", "booth number",

            # Other common headers
            "percentage", "%", "rank", "position"
        }
        self.load_data()

    def load_data(self):
        """Load candidate to party mapping from JSON file."""
        if not os.path.exists(self.data_path):
            logger.warning(f"Mapping file {self.data_path} not found.")
            return

        try:
            with open(self.data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Reset mappings
            self.mapping = {}
            self.constituency_map = {}
            
            if isinstance(data, list):
                # New Format: List of dicts with 'candidate', 'party', 'constituency'
                for item in data:
                    candidate = item.get("candidate", "").strip()
                    party = item.get("party", "").strip()
                    constituency = item.get("constituency", "").strip()
                    
                    if candidate and party:
                        self.mapping[candidate] = party
                        if constituency:
                            self.constituency_map[candidate] = constituency
            
            elif isinstance(data, dict):
                # Fallback: Old Format: Dict[Candidate, Party]
                self.mapping = data
                
            logger.info(f"Loaded {len(self.mapping)} candidate mappings from {self.data_path}")
        except Exception as e:
            logger.error(f"Error loading mapping file: {e}")

    def normalize_value(self, text: str, constituency: str = None, use_constituency_filter: bool = True) -> str:
        """
        Normalize a single cell value to a party name.

        Args:
            text: Text to normalize
            constituency: Target constituency (if None, uses original broad matching)
            use_constituency_filter: If True and constituency provided, only match candidates from that constituency

        Logic (when use_constituency_filter=True and constituency provided):
        1. Check blacklist
        2. Use find_candidates_in_constituency() for constituency-aware matching
        3. Return party name if high-confidence match found
        4. Otherwise return original text

        Logic (legacy mode - when constituency not provided or use_constituency_filter=False):
        0. Check for critical name collisions (Annadurai, Senthilnathan, etc.) using Constituency context.
        1. Check if it's already a known party.
        2. Check for exact match in mapping keys.
        3. Check for reversed text match.
        4. Check for fuzzy match against mapping keys.
        """
        if not text or not isinstance(text, str):
            return text

        text = text.strip()

        # NEW: If constituency provided and filtering enabled, use strict constituency-based matching
        if constituency and use_constituency_filter:
            # Check blacklist
            if text.lower() in self.non_candidate_headers:
                return text

            # Find candidate in constituency
            match_result = self.find_candidates_in_constituency(text, constituency, min_threshold=0.75)

            if match_result:
                logger.info(f"Constituency match: '{text}' -> {match_result['party']} "
                           f"(candidate: {match_result['candidate']}, confidence: {match_result['confidence']:.2f})")
                return match_result['party']
            else:
                logger.debug(f"No constituency match for '{text}' in '{constituency}', keeping original")
                return text

        # LEGACY: Original broad matching logic (unchanged for backward compatibility)
        
        # 0. Check for critical name collisions
        collision_party = self.check_collisions(text, constituency)
        if collision_party:
            return collision_party
        
        # 0. Cleanup specific known OCR junk
        clean_text = re.sub(r'\s+', ' ', text)
        
        # 1. Check if already a known party
        if clean_text.upper() in self.known_parties:
            return clean_text.upper()
            
        # 2. Check exact match (Case Sensitive & Title Case)
        if clean_text in self.mapping:
            return self.mapping[clean_text]
        if clean_text.title() in self.mapping:
            return self.mapping[clean_text.title()]
            
        # 3. Check reversed text
        # OCR sometimes produces reversed text like "M T IHTAPANAGAVLES"
        reversed_text = clean_text[::-1]
        
        # Check if reversed text is a valid party
        if reversed_text.upper() in self.known_parties:
             return reversed_text.upper()

        # Check if reversed text is a candidate (Title Case)
        reversed_title = reversed_text.title()
        if reversed_title in self.mapping:
             return self.mapping[reversed_title]
             
        # Fuzzy match reversed text
        matches = get_close_matches(reversed_title, self.mapping.keys(), n=1, cutoff=0.7)
        if matches:
             return self.mapping[matches[0]]

        # 4. Check Reordered Initials (e.g. "Selvaganapathi T M" -> "T M Selvaganapathi")
        # Apply to both original and reversed text
        for candidate_text in [clean_text, reversed_text]:
            candidate_title = candidate_text.title()
            parts = candidate_title.split()
            if len(parts) > 1:
                # heuristic: if last part is short (initial-like), try moving to front
                if len(parts[-1].replace('.', '')) <= 1:
                    initials = []
                    names = []
                    for p in parts:
                        if len(p.replace('.', '')) == 1:
                            initials.append(p)
                        else:
                            names.append(p)
                    
                    reordered = " ".join(initials + names)
                    
                    # Fuzzy match reordered
                    matches = get_close_matches(reordered, self.mapping.keys(), n=1, cutoff=0.7)
                    if matches:
                        return self.mapping[matches[0]]

        # 5. Fuzzy match original text
        matches = get_close_matches(clean_text, self.mapping.keys(), n=1, cutoff=0.6)
        if matches:
            return self.mapping[matches[0]]
            
        return text

    def check_collisions(self, text: str, constituency: str = None) -> Optional[str]:
        """
        Handle specific name collisions based on User's critical warning.
        """
        text_lower = text.lower()
        cons_lower = constituency.lower() if constituency else ""
        
        # 1. Annadurai
        if "annadurai" in text_lower:
            if "c. n." in text_lower or "c.n." in text_lower or "tiruvannamalai" in cons_lower:
                return "DMK"
            if "salem" in cons_lower:
                return "PMK"
            # Default fallback if just "Annadurai"? 
            # User said "If 'Salem' or just 'Annadurai' (no initials) -> PMK"
            if "c. n." not in text_lower and "c.n." not in text_lower:
                return "PMK"

        # 2. Senthilnathan
        if "senthilnathan" in text_lower:
            if "v. v." in text_lower or "v.v." in text_lower or "karur" in cons_lower:
                return "BJP"
            if "p." in text_lower or "tiruchirappalli" in cons_lower:
                return "AMMK"

        # 3. Venkatesan
        if "venkatesan" in text_lower:
            if "jothi" in text_lower or "kancheepuram" in cons_lower:
                return "PMK"
            if "su." in text_lower or "madurai" in cons_lower:
                return "CPI(M)"
                
        # 4. Mani
        if "mani" in text_lower:
            if "a. mani" in text_lower or "dharmapuri" in cons_lower:
                return "DMK"
            if "tamil mani" in text_lower or "namakkal" in cons_lower:
                return "AIADMK"
                
        return None

        # Check if reversed text is a valid candidate
        # Need to handle potential spacing issues in reversed text too
        # e.g. "M T IHTAPANAGAVLES" -> "SELVAGANAPATHI T M"
        # We should try to fuzzy match the reversed text against keys
        
        matches = get_close_matches(reversed_text, self.mapping.keys(), n=1, cutoff=0.7)
        if matches:
            logger.info(f"Reversed match found: '{text}' -> '{matches[0]}' -> {self.mapping[matches[0]]}")
            return self.mapping[matches[0]]

        # 4. Fuzzy match original text
        matches = get_close_matches(clean_text, self.mapping.keys(), n=1, cutoff=0.6)
        if matches:
            logger.info(f"Fuzzy match found: '{text}' -> '{matches[0]}' -> {self.mapping[matches[0]]}")
            return self.mapping[matches[0]]
            
        # If no match found, returns original text
        return text

    def normalize_column(self, values: List[str], constituency_values: List[str] = None) -> List[str]:
        """Normalize a list of values, optionally using constituency context."""
        if constituency_values and len(values) == len(constituency_values):
            return [self.normalize_value(v, c) for v, c in zip(values, constituency_values)]
        
        return [self.normalize_value(v) for v in values]

    def detect_constituency(self, headers: List[str]) -> Optional[str]:
        """
        Detect the constituency from a list of headers (candidate names).
        
        Strategy:
        1. Iterate through all headers.
        2. Identify candidates using fuzzy matching / exact matching.
        3. If a candidate maps to a constituency, tally the votes for that constituency.
        4. Return the constituency with the most votes (or the first one found if unique).
        """
        constituency_votes = {}
        
        for header in headers:
            if not header or not isinstance(header, str):
                continue
                
            clean_header = header.strip()
            
            # Skip common non-candidate headers
            if clean_header.upper() in ["TOTAL", "NOTA", "OVERSEAS ELECTORS", "SERVICE ELECTORS"]:
                continue

            # Try to identify candidate (reusing normalize_value logic partially would be good, 
            # but normalize_value returns Party, we need Candidate Name to look up Constituency)
            
            # Simple Exact/Fuzzy check against mapping keys
            candidate_name = None
            
            # 1. Exact
            if clean_header in self.mapping:
                candidate_name = clean_header
            elif clean_header.title() in self.mapping:
                candidate_name = clean_header.title()
            
            # 2. Reversed
            if not candidate_name:
                reversed_text = clean_header[::-1]
                reversed_title = reversed_text.title()
                if reversed_title in self.mapping:
                    candidate_name = reversed_title
                else:
                    # Fuzzy reversed
                    matches = get_close_matches(reversed_title, self.mapping.keys(), n=1, cutoff=0.7)
                    if matches:
                        candidate_name = matches[0]

            # 3. Fuzzy Original
            if not candidate_name:
                matches = get_close_matches(clean_header, self.mapping.keys(), n=1, cutoff=0.6)
                if matches:
                    candidate_name = matches[0]
            
            # If identified and has constituency
            if candidate_name and hasattr(self, 'constituency_map') and candidate_name in self.constituency_map:
                cons = self.constituency_map[candidate_name]
                constituency_votes[cons] = constituency_votes.get(cons, 0) + 1
                logger.info(f"Header '{header}' identifies candidate '{candidate_name}' -> Constituency '{cons}'")

        if not constituency_votes:
            logger.warning("No constituency detected from headers.")
            return None

        # Return winner
        logger.info(f"Constituency detection votes: {constituency_votes}")
        best_constituency = max(constituency_votes, key=constituency_votes.get)
        total_votes = sum(constituency_votes.values())
        logger.info(f"Detected constituency: '{best_constituency}' with {constituency_votes[best_constituency]}/{total_votes} votes")
        return best_constituency

    def find_candidates_in_constituency(self, text: str, constituency: str, min_threshold: float = 0.75) -> Optional[Dict]:
        """
        Find if text matches a candidate from the specified constituency with high confidence.

        Args:
            text: Header text to match
            constituency: Target constituency to search within
            min_threshold: Minimum fuzzy match threshold (default 0.75 for conservative matching)

        Returns:
            Dict with keys: 'candidate', 'party', 'constituency', 'confidence' if match found
            None if no match or match is below threshold
        """
        if not text or not isinstance(text, str) or not constituency:
            return None

        clean_text = text.strip()

        # Helper function to strip common titles/prefixes
        def strip_titles(name: str) -> str:
            """Remove common titles like Dr, Mr, Mrs, Prof, etc."""
            titles = ['dr.', 'dr', 'mr.', 'mr', 'mrs.', 'mrs', 'ms.', 'ms',
                     'prof.', 'prof', 'professor', 'adv.', 'adv', 'advocate',
                     'hon.', 'hon', 'honourable', 'shri', 'smt.', 'smt']
            words = name.split()
            # Remove title from beginning
            while words and words[0].lower().rstrip('.') in titles:
                words.pop(0)
            # Remove title from end (sometimes OCR puts them there)
            while words and words[-1].lower().rstrip('.') in titles:
                words.pop()
            return ' '.join(words)

        # Check blacklist first
        if clean_text.lower() in self.non_candidate_headers:
            logger.info(f"Skipping blacklisted header: '{text}'")
            return None

        # Filter candidates to only those from target constituency
        constituency_candidates = {
            candidate: party
            for candidate, party in self.mapping.items()
            if self.constituency_map.get(candidate) == constituency
        }

        if not constituency_candidates:
            logger.warning(f"No candidates found for constituency '{constituency}'")
            return None

        # Try exact match first
        if clean_text in constituency_candidates:
            return {
                'candidate': clean_text,
                'party': constituency_candidates[clean_text],
                'constituency': constituency,
                'confidence': 1.0
            }

        # Try title case
        clean_title = clean_text.title()
        if clean_title in constituency_candidates:
            return {
                'candidate': clean_title,
                'party': constituency_candidates[clean_title],
                'constituency': constituency,
                'confidence': 1.0
            }

        # Try reversed text (for OCR errors like "M T IHTAPANAGAVLES" -> "SELVAGANAPATHI T M")
        reversed_text = clean_text[::-1]
        reversed_title = reversed_text.title()

        # Check exact match on reversed
        if reversed_title in constituency_candidates:
            logger.info(f"Reversed match found: '{text}' -> '{reversed_title}'")
            return {
                'candidate': reversed_title,
                'party': constituency_candidates[reversed_title],
                'constituency': constituency,
                'confidence': 1.0
            }

        # Try fuzzy match on reversed text (with title stripping for better matching)
        reversed_stripped = strip_titles(reversed_title)
        # Create a version of candidates dict with titles stripped for comparison
        candidates_stripped = {strip_titles(cand): cand for cand in constituency_candidates.keys()}

        reversed_matches = get_close_matches(reversed_stripped, candidates_stripped.keys(), n=1, cutoff=min_threshold)
        if reversed_matches:
            # Get original candidate name (with titles)
            matched_candidate = candidates_stripped[reversed_matches[0]]
            from difflib import SequenceMatcher
            confidence = SequenceMatcher(None, reversed_stripped, reversed_matches[0]).ratio()

            logger.info(f"Reversed fuzzy match: '{text}' (reversed to '{reversed_title}', stripped to '{reversed_stripped}') -> '{matched_candidate}' (confidence: {confidence:.2f})")

            return {
                'candidate': matched_candidate,
                'party': constituency_candidates[matched_candidate],
                'constituency': constituency,
                'confidence': confidence
            }

        # Try reordering initials on reversed text
        # e.g., "SELVAGANAPATHI T M" -> "T M Selvaganapathi"
        reversed_parts = reversed_title.split()
        if len(reversed_parts) > 1:
            # Separate initials from names
            initials = []
            names = []
            for part in reversed_parts:
                # Check if it's an initial (single char or single char with dot)
                if len(part.replace('.', '').replace(' ', '')) <= 1:
                    initials.append(part)
                else:
                    names.append(part)

            # Try: initials first, then names
            if initials and names:
                reordered = " ".join(initials + names)
                reordered_matches = get_close_matches(reordered, constituency_candidates.keys(), n=1, cutoff=min_threshold)
                if reordered_matches:
                    matched_candidate = reordered_matches[0]
                    from difflib import SequenceMatcher
                    confidence = SequenceMatcher(None, reordered, matched_candidate).ratio()

                    logger.info(f"Reversed + reordered match: '{text}' (reversed to '{reversed_title}', reordered to '{reordered}') -> '{matched_candidate}' (confidence: {confidence:.2f})")

                    return {
                        'candidate': matched_candidate,
                        'party': constituency_candidates[matched_candidate],
                        'constituency': constituency,
                        'confidence': confidence
                    }

        # Try fuzzy matching with higher threshold on original text
        matches = get_close_matches(clean_title, constituency_candidates.keys(), n=1, cutoff=min_threshold)
        if matches:
            matched_candidate = matches[0]
            # Calculate actual similarity score
            from difflib import SequenceMatcher
            confidence = SequenceMatcher(None, clean_title, matched_candidate).ratio()

            logger.info(f"Fuzzy match: '{text}' -> '{matched_candidate}' (confidence: {confidence:.2f})")

            return {
                'candidate': matched_candidate,
                'party': constituency_candidates[matched_candidate],
                'constituency': constituency,
                'confidence': confidence
            }

        return None
