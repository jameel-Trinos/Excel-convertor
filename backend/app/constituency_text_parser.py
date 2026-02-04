"""Text-based parser for constituency PDFs with structured entry format.

This parser handles PDFs with entries in the format:
[Serial Number] [ID Number] [Text content]
[1] -Sub-area 1, [2] -Sub-area 2, etc.

Handles special cases:
- Entries 1-9 may have numbers like "11", "22" instead of "1 1", "2 2"
- Multi-line entries spanning 2-5 lines
- Headers/footers to filter out
"""

import logging
import re
from pathlib import Path
from typing import List, Optional, Tuple

import pdfplumber

logger = logging.getLogger(__name__)


class ConstituencyTextParser:
    """
    Parse constituency PDFs with text-based entry extraction.
    
    Expected format:
    1 1 Panchayat Union Primary School, North Building
        [1] -Village (Ward-1), [2] -Colony (Ward-2)
    
    Output:
    - Serial Number (integer)
    - ID Number (integer)
    - Main Location Text (text before [1] marker)
    - Sub-areas (all [n] - text patterns, separated by |)
    """

    def __init__(self, file_path: str):
        """
        Initialize the parser.
        
        Args:
            file_path: Path to PDF file
        """
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"PDF not found: {file_path}")

    def parse(self) -> Tuple[List[str], List[List[str]]]:
        """
        Parse PDF and extract structured entries.
        
        Returns:
            Tuple of (headers, data_rows)
            headers: ["Sl.No", "ID", "Location", "Areas"]
            data_rows: List of [serial_no, id_no, location, areas]
        """
        logger.info(f"Starting constituency text parse of {self.file_path}")
        
        # Extract text from all pages
        all_text = self._extract_text_from_pdf()
        
        # Filter out headers and footers
        filtered_lines = self._filter_headers_footers(all_text)
        
        # Parse entries
        entries = self._parse_entries(filtered_lines)
        
        # Convert to table format
        headers = ["Sl.No", "ID", "Location", "Areas"]
        data_rows = []
        
        for entry in entries:
            data_rows.append([
                str(entry["serial_no"]),
                str(entry["id_no"]),
                entry["location"],
                entry["areas"]
            ])
        
        logger.info(f"Extracted {len(entries)} entries")
        
        # Log first few entries for debugging
        if entries:
            logger.info("Sample entries:")
            for i, entry in enumerate(entries[:3]):
                logger.info(f"  Entry {i+1}: Serial={entry['serial_no']}, ID={entry['id_no']}, "
                          f"Location='{entry['location'][:50]}...', Areas='{entry['areas'][:50]}...'")
        
        return headers, data_rows

    def _extract_text_from_pdf(self) -> List[str]:
        """Extract text lines from all pages of the PDF."""
        all_lines = []
        
        try:
            with pdfplumber.open(str(self.file_path)) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    # Try multiple extraction methods
                    text = page.extract_text()
                    
                    # If no text, try extracting words and reconstructing
                    if not text or len(text.strip()) < 10:
                        words = page.extract_words()
                        if words:
                            # Reconstruct text from words
                            text = " ".join([w.get("text", "") for w in words])
                    
                    if text:
                        # Split by newlines and clean
                        lines = text.split("\n")
                        # Clean each line
                        cleaned_lines = []
                        for line in lines:
                            line = line.strip()
                            if line:
                                cleaned_lines.append(line)
                        all_lines.extend(cleaned_lines)
                        logger.info(f"Page {page_num}: Extracted {len(cleaned_lines)} lines")
                    else:
                        logger.warning(f"Page {page_num}: No text extracted")
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {e}", exc_info=True)
            raise
        
        logger.info(f"Total lines extracted: {len(all_lines)}")
        return all_lines

    def _filter_headers_footers(self, lines: List[str]) -> List[str]:
        """
        Filter out header and footer lines.
        
        Patterns to filter:
        - "List of" (at start)
        - "Page Number" or "Page X" (standalone)
        - Lines with only a single number (likely page numbers, but be careful)
        - Common header/footer text
        """
        filtered = []
        
        # Patterns to skip - be more specific to avoid removing valid data
        skip_patterns = [
            r"^List\s+of\s+",  # "List of" at start
            r"^Page\s+Number\s*$",  # "Page Number" as standalone
            r"^Page\s+\d+\s*$",  # "Page 1", "Page 2" as standalone
            r"^Total\s*$",  # "Total" as standalone
            r"^Grand\s+Total\s*$",  # "Grand Total" as standalone
        ]
        
        compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in skip_patterns]
        
        for line in lines:
            original_line = line
            line = line.strip()
            if not line:
                continue
            
            # Skip if matches any pattern
            should_skip = False
            for pattern in compiled_patterns:
                if pattern.match(line):
                    should_skip = True
                    logger.debug(f"Skipping header/footer line: '{line[:50]}...'")
                    break
            
            # Additional check: single number on its own (but only if it's likely a page number)
            # Don't skip if it's at the start of what looks like an entry
            if not should_skip:
                # Check if line is just a number (but be careful - could be entry start)
                if re.match(r"^\d{1,2}\s*$", line):
                    # Only skip if it's clearly a page number (appears alone, not followed by entry)
                    # For now, keep it - let the entry parser decide
                    pass
            
            if not should_skip:
                filtered.append(line)
        
        logger.info(f"Filtered {len(lines)} lines to {len(filtered)} lines")
        return filtered

    def _parse_entries(self, lines: List[str]) -> List[dict]:
        """
        Parse entries from filtered lines.
        
        Entry format:
        - Starts with: [number] [number] [text...]
        - May span multiple lines
        - Sub-areas marked with [n] -text
        
        Special handling for entries 1-9:
        - "11" should be parsed as "1 1"
        - "22" should be parsed as "2 2"
        - etc.
        """
        entries = []
        current_entry = None
        entry_lines = []
        
        # More flexible patterns to handle various formats
        # Pattern 1: Two numbers at start (with spaces): "1 1 text" or "1  1  text"
        pattern1 = re.compile(r"^(\d{1,3})\s+(\d{1,3})\s+(.+)$")
        # Pattern 2: Double digit for entries 1-9: "11 text" or "22 text"
        pattern2 = re.compile(r"^(\d)(\d)\s+(.+)$")
        # Pattern 3: Single number followed by text (might be continuation)
        pattern3 = re.compile(r"^(\d{1,3})\s+(.+)$")
        
        # Pattern to match sub-area: [n] -text or [n] text
        sub_area_pattern = re.compile(
            r"\[(\d+)\]\s*-?\s*([^\[\],]+?)(?=\s*\[|\s*$|,)"
        )
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue
            
            # Try to match entry start patterns
            match = None
            serial_str = None
            id_str = None
            rest = None
            
            # Try pattern 1 first (two separate numbers)
            match = pattern1.match(line)
            if match:
                serial_str, id_str, rest = match.groups()
            else:
                # Try pattern 2 (double digit like "11", "22")
                match = pattern2.match(line)
                if match:
                    # Check if it's a double digit (same digit repeated)
                    if match.group(1) == match.group(2):
                        serial_str = match.group(1)
                        id_str = match.group(2)
                        rest = match.group(3)
            
            if serial_str and id_str and rest:
                # This is a new entry start
                # Save previous entry if exists
                if current_entry is not None:
                    location, areas = self._extract_location_and_areas(entry_lines, sub_area_pattern)
                    current_entry["location"] = location
                    current_entry["areas"] = areas
                    entries.append(current_entry)
                    logger.debug(f"Completed entry: Serial={current_entry['serial_no']}, ID={current_entry['id_no']}")
                
                # Parse numbers (handle special case for entries 1-9)
                serial_no, id_no = self._parse_entry_numbers(serial_str, id_str)
                
                # Start new entry
                current_entry = {
                    "serial_no": serial_no,
                    "id_no": id_no,
                    "location": "",
                    "areas": ""
                }
                entry_lines = [rest]  # Start with the rest of the line
                logger.debug(f"New entry started: Serial={serial_no}, ID={id_no}, Rest='{rest[:50]}...'")
            else:
                # This might be a continuation line
                if current_entry is not None:
                    # Check if this line looks like it starts a new entry (has two numbers at start)
                    # If so, it might be that previous entry ended and this is a new one
                    next_line_match = pattern1.match(line) or pattern2.match(line)
                    if next_line_match and i > 0:
                        # Check if previous line ended properly (has sub-areas or is complete)
                        # For now, assume continuation
                        entry_lines.append(line)
                        logger.debug(f"Continuation line added: '{line[:50]}...'")
                else:
                    # No current entry, but this line might be a data line
                    # Try to extract if it looks like an entry
                    match = pattern1.match(line) or pattern2.match(line)
                    if match:
                        if pattern1.match(line):
                            serial_str, id_str, rest = pattern1.match(line).groups()
                        else:
                            m = pattern2.match(line)
                            if m.group(1) == m.group(2):
                                serial_str = m.group(1)
                                id_str = m.group(2)
                                rest = m.group(3)
                        
                        if serial_str and id_str:
                            serial_no, id_no = self._parse_entry_numbers(serial_str, id_str)
                            current_entry = {
                                "serial_no": serial_no,
                                "id_no": id_no,
                                "location": "",
                                "areas": ""
                            }
                            entry_lines = [rest] if rest else []
                            logger.debug(f"New entry from orphaned line: Serial={serial_no}, ID={id_no}")
            
            i += 1
        
        # Don't forget the last entry
        if current_entry is not None:
            location, areas = self._extract_location_and_areas(entry_lines, sub_area_pattern)
            current_entry["location"] = location
            current_entry["areas"] = areas
            entries.append(current_entry)
            logger.debug(f"Final entry completed: Serial={current_entry['serial_no']}, ID={current_entry['id_no']}")
        
        logger.info(f"Parsed {len(entries)} entries from {len(lines)} lines")
        return entries

    def _parse_entry_numbers(self, serial_str: str, id_str: str) -> Tuple[int, int]:
        """
        Parse serial and ID numbers, handling special case for entries 1-9.
        
        For entries 1-9, numbers may appear as "11", "22", "33" instead of "1 1", "2 2", "3 3".
        
        Args:
            serial_str: Serial number string (may be "11" for entry 1)
            id_str: ID number string (may be "11" for entry 1)
            
        Returns:
            Tuple of (serial_no, id_no)
        """
        try:
            # Check if serial_str is a double digit (11, 22, 33, etc.)
            # and if it's the same digit repeated (only for 1-9)
            if len(serial_str) == 2 and serial_str[0] == serial_str[1] and serial_str[0] in "123456789":
                # This is likely "11" meaning "1 1", "22" meaning "2 2", etc.
                serial_no = int(serial_str[0])
            else:
                serial_no = int(serial_str)
        except (ValueError, TypeError):
            logger.warning(f"Invalid serial number: '{serial_str}', defaulting to 0")
            serial_no = 0
        
        try:
            # Same for ID
            if len(id_str) == 2 and id_str[0] == id_str[1] and id_str[0] in "123456789":
                id_no = int(id_str[0])
            else:
                id_no = int(id_str)
        except (ValueError, TypeError):
            logger.warning(f"Invalid ID number: '{id_str}', defaulting to 0")
            id_no = 0
        
        return serial_no, id_no

    def _extract_location_and_areas(
        self, entry_lines: List[str], sub_area_pattern: re.Pattern
    ) -> Tuple[str, str]:
        """
        Extract location text and sub-areas from entry lines.
        
        Location: Text before first [n] marker (where n is a number)
        Areas: All [n] -text patterns, separated by |
        
        Args:
            entry_lines: Lines belonging to this entry
            sub_area_pattern: Compiled regex pattern for sub-areas
            
        Returns:
            Tuple of (location, areas)
        """
        if not entry_lines:
            return "", ""
        
        # Combine all lines with proper spacing
        full_text = " ".join(entry_lines)
        
        # Find first [number] marker to separate location from areas
        # Look for pattern like [1], [2], etc.
        first_marker_match = re.search(r"\[(\d+)\]", full_text)
        
        if not first_marker_match:
            # No sub-areas found, entire text is location
            location = self._clean_text(full_text)
            logger.debug(f"No sub-areas found, location='{location[:50]}...'")
            return location, ""
        
        # Split location and areas
        first_marker_pos = first_marker_match.start()
        location_text = full_text[:first_marker_pos].strip()
        areas_text = full_text[first_marker_pos:]
        
        # Clean location
        location = self._clean_text(location_text)
        
        # Extract all sub-areas using improved pattern
        # Try multiple patterns to catch different formats
        sub_areas = []
        
        # Pattern 1: [n] -text
        pattern1 = re.compile(r"\[(\d+)\]\s*-\s*([^\[\],]+?)(?=\s*\[|\s*$|,)")
        # Pattern 2: [n] text (without dash)
        pattern2 = re.compile(r"\[(\d+)\]\s+([^\[\],]+?)(?=\s*\[|\s*$|,)")
        # Pattern 3: [n]text (no space)
        pattern3 = re.compile(r"\[(\d+)\]([^\[\],]+?)(?=\s*\[|\s*$|,)")
        
        # Try all patterns
        all_matches = []
        for pattern in [pattern1, pattern2, pattern3]:
            for match in pattern.finditer(areas_text):
                area_num = match.group(1)
                area_text = match.group(2).strip()
                # Remove leading dash if present
                area_text = area_text.lstrip("-").strip()
                # Clean area text
                area_text = self._clean_text(area_text)
                if area_text:  # Only add if there's actual text
                    all_matches.append((int(area_num), area_text))
        
        # Sort by area number and remove duplicates
        seen = set()
        unique_matches = []
        for area_num, area_text in sorted(all_matches, key=lambda x: x[0]):
            key = (area_num, area_text)
            if key not in seen:
                seen.add(key)
                unique_matches.append((area_num, area_text))
        
        # Format sub-areas
        for area_num, area_text in unique_matches:
            sub_areas.append(f"[{area_num}] {area_text}")
        
        # Join sub-areas with |
        areas = " | ".join(sub_areas)
        
        logger.debug(f"Extracted location='{location[:50]}...', areas='{areas[:50]}...'")
        return location, areas

    def _clean_text(self, text: str) -> str:
        """
        Clean text by removing unwanted patterns.
        
        Removes:
        - "ALL VOTERS"
        - Trailing commas
        - Extra whitespace
        """
        if not text:
            return ""
        
        # Remove "ALL VOTERS"
        text = re.sub(r"\bALL\s+VOTERS\b", "", text, flags=re.IGNORECASE)
        
        # Remove trailing commas and periods
        text = text.rstrip(".,;")
        
        # Normalize whitespace
        text = " ".join(text.split())
        
        return text.strip()

