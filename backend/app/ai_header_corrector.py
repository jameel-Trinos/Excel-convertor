"""AI-powered header corrector for fixing ambiguous reversed headers."""

import json
import logging
import os
from typing import Dict, List, Optional

from .party_name_fixer import PartyNameFixer

logger = logging.getLogger(__name__)


class AIHeaderCorrector:
    """
    AI-powered header corrector for ambiguous cases.
    
    Uses Claude/OpenAI as a fallback when pattern matching fails.
    Only used when:
    1. Pattern matching couldn't fix the header
    2. AI API is available
    3. Header appears to be a party name but couldn't be fixed
    """

    def __init__(self, use_claude: bool = True, use_openai: bool = False):
        """
        Initialize AI header corrector.
        
        Args:
            use_claude: Use Anthropic Claude if available (default: True)
            use_openai: Use OpenAI GPT as fallback (default: False)
        """
        self.use_claude = use_claude
        self.use_openai = use_openai
        self.claude_client = None
        self.openai_client = None
        self.enabled = False
        
        # Try to initialize Claude
        if use_claude:
            try:
                from anthropic import Anthropic
                api_key = os.getenv("ANTHROPIC_API_KEY")
                if api_key:
                    self.claude_client = Anthropic(api_key=api_key)
                    self.enabled = True
                    logger.info("AI Header Corrector: Claude AI enabled")
            except ImportError:
                logger.warning("Anthropic SDK not available, Claude disabled")
            except Exception as e:
                logger.warning(f"Failed to initialize Claude: {e}")
        
        # Try to initialize OpenAI as fallback
        if not self.enabled and use_openai:
            try:
                from openai import OpenAI
                api_key = os.getenv("OPENAI_API_KEY")
                if api_key:
                    self.openai_client = OpenAI(api_key=api_key)
                    self.enabled = True
                    logger.info("AI Header Corrector: OpenAI enabled")
            except ImportError:
                logger.warning("OpenAI SDK not available, OpenAI disabled")
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI: {e}")
        
        if not self.enabled:
            logger.info("AI Header Corrector: Disabled (no API keys available)")

    def fix_headers_with_ai(
        self,
        headers: List[str],
        batch_size: int = 15,
        use_ai_as_primary: bool = True
    ) -> List[str]:
        """
        Fix headers using AI as the primary correction method.
        
        Args:
            headers: List of headers that may need correction
            batch_size: Number of headers to process in one API call
            use_ai_as_primary: If True, use AI for all headers. If False, only for ambiguous ones.
            
        Returns:
            List of corrected headers
        """
        if not self.enabled:
            logger.info("AI not available, using pattern matching fallback")
            # Fallback to pattern matching
            from .header_fixer import HeaderFixer
            return HeaderFixer.fix_header_list(headers)
        
        logger.info(f"Using AI to fix {len(headers)} headers (primary method)")
        
        # Process all headers with AI
        corrected_headers = headers.copy()
        
        # Process in batches to avoid token limits
        for i in range(0, len(headers), batch_size):
            batch = headers[i:i + batch_size]
            batch_indices = list(range(i, min(i + batch_size, len(headers))))
            
            try:
                corrected_batch = self._fix_batch_with_ai(batch)
                
                # Update corrected headers
                for orig_idx, corrected in zip(batch_indices, corrected_batch):
                    if corrected and corrected != headers[orig_idx]:
                        corrected_headers[orig_idx] = corrected
                        logger.debug(f"AI corrected: '{headers[orig_idx]}' -> '{corrected}'")
            except Exception as e:
                logger.warning(f"AI correction failed for batch: {e}")
                # Fallback to pattern matching for this batch
                from .header_fixer import HeaderFixer
                fallback_fixed = HeaderFixer.fix_header_list(batch)
                for j, fixed in enumerate(fallback_fixed):
                    corrected_headers[batch_indices[j]] = fixed
        
        return corrected_headers

    def _fix_batch_with_ai(self, headers: List[str]) -> List[str]:
        """
        Fix a batch of headers using AI.
        
        Args:
            headers: List of headers to fix
            
        Returns:
            List of corrected headers
        """
        if self.claude_client:
            return self._fix_with_claude(headers)
        elif self.openai_client:
            return self._fix_with_openai(headers)
        else:
            return headers

    def _fix_with_claude(self, headers: List[str]) -> List[str]:
        """Fix headers using Claude AI."""
        try:
            prompt = self._create_correction_prompt(headers)
            
            message = self.claude_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                temperature=0.1,  # Lower temperature for more consistent results
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            response_text = message.content[0].text.strip()
            return self._parse_ai_response(response_text, headers)
            
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            # Fallback to pattern matching
            from .header_fixer import HeaderFixer
            return HeaderFixer.fix_header_list(headers)

    def _fix_with_openai(self, headers: List[str]) -> List[str]:
        """Fix headers using OpenAI GPT."""
        try:
            prompt = self._create_correction_prompt(headers)
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at correcting Indian election PDF headers. Fix reversed Tamil party names to their canonical forms. Always return valid JSON arrays."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,  # Lower temperature for consistency
                max_tokens=1500
            )
            
            response_text = response.choices[0].message.content.strip()
            return self._parse_ai_response(response_text, headers)
            
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            # Fallback to pattern matching
            from .header_fixer import HeaderFixer
            return HeaderFixer.fix_header_list(headers)

    def _create_correction_prompt(self, headers: List[str]) -> str:
        """Create prompt for AI correction with comprehensive examples."""
        headers_str = "\n".join(f"{i+1}. {header}" for i, header in enumerate(headers))
        
        prompt = f"""You are correcting column headers from an Indian election PDF. The headers may contain reversed Tamil party names due to vertical text extraction issues.

CANONICAL PARTY NAMES (correct format):
1. "DRAVIDA MUNNETRA KAZHAGAM" (DMK)
2. "ALL INDIA DRAVIDA MUNNETRA KAZHAGAM" (AIADMK) - Note: WITHOUT "ANNA"
3. "BHARATIYA JANATA PARTY" (BJP)
4. "INDIAN NATIONAL CONGRESS" (Congress)
5. "VIDUTHALAI CHIRUTHAIGAL KATCHI" (VCK)
6. "PATTALI MAKKAL KATCHI" (PMK)
7. "NAAM TAMIZHAR KATCHI" (NTK) - Note: "TAMIZHAR" not "TAMILAR"
8. "BAHUJAN SAMAJ PARTY" (BSP)
9. "AMMA MAKKAL MUNNETRA KAZHAGAM"
10. "MAKKAL NAADAALUM KATCHI"
11. "INDEPENDENT" (IND)
12. "NOTA"

EXAMPLES OF REVERSALS TO FIX:
- Character reversal: "LAKKAM ARTENNUM MAGAHZAK AMMA" → "AMMA MAKKAL MUNNETRA KAZHAGAM"
- Word order: "JANATA BHARATIYA PARTY" → "BHARATIYA JANATA PARTY"
- Word order: "MUNNETRA ANNA KAZHAGAM INDIA DRAVIDA ALL" → "ALL INDIA DRAVIDA MUNNETRA KAZHAGAM" (remove ANNA)
- Word order: "SAMAJ PARTY BAHUJAN" → "BAHUJAN SAMAJ PARTY"
- Word order: "KATCHI VIDUTHALAI CHIRUTHAIGAL" → "VIDUTHALAI CHIRUTHAIGAL KATCHI"
- Word order: "TAMILAR KATCHI NAAM" → "NAAM TAMIZHAR KATCHI" (also fix TAMILAR to TAMIZHAR)

HEADER FORMATS TO HANDLE:
- "CANDIDATE NAME - PARTY NAME" (fix only the party part)
- "CANDIDATE NAME (PARTY)" (fix only the party part)
- Standalone party names (fix the entire string)

HEADERS TO CORRECT:
{headers_str}

INSTRUCTIONS:
1. Fix reversed party names to their canonical forms listed above
2. For "NAME - PARTY" format, only fix the party part, keep candidate name unchanged
3. Remove "ANNA" from AIADMK party name (use "ALL INDIA DRAVIDA MUNNETRA KAZHAGAM")
4. Normalize "TAMILAR" to "TAMIZHAR" in NTK party name
5. Preserve non-party headers (like "SL. NO.", "Polling Station No.", "Total", etc.) exactly as-is
6. Return a JSON array with corrected headers in the same order

Return ONLY a valid JSON array, no other text:
["corrected header 1", "corrected header 2", ...]
"""
        return prompt

    def _parse_ai_response(self, response_text: str, original_headers: List[str]) -> List[str]:
        """Parse AI response and extract corrected headers."""
        try:
            # Try to extract JSON from response
            # AI might wrap JSON in markdown code blocks
            if "```json" in response_text:
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                if end > start:
                    response_text = response_text[start:end].strip()
            elif "```" in response_text:
                start = response_text.find("```") + 3
                end = response_text.find("```", start)
                if end > start:
                    response_text = response_text[start:end].strip()
            
            # Try to find JSON array in the response
            # Look for array pattern: [...]
            if "[" in response_text and "]" in response_text:
                start = response_text.find("[")
                end = response_text.rfind("]") + 1
                if end > start:
                    response_text = response_text[start:end]
            
            # Parse JSON
            corrected = json.loads(response_text)
            
            # Ensure we have the same number of headers
            if isinstance(corrected, list) and len(corrected) == len(original_headers):
                # Validate: all items should be strings
                if all(isinstance(h, str) for h in corrected):
                    return corrected
                else:
                    logger.warning("AI returned non-string values in header list")
                    return original_headers
            else:
                logger.warning(f"AI returned {len(corrected) if isinstance(corrected, list) else 'non-list'} headers, expected {len(original_headers)}")
                return original_headers
                
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse AI response as JSON: {e}")
            logger.debug(f"Response text: {response_text[:200]}...")
            return original_headers
        except Exception as e:
            logger.warning(f"Error parsing AI response: {e}")
            return original_headers


