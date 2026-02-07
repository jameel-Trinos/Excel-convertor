"""
AC (Assembly Constituency) number extractor from PDF text.

Extracts the Assembly Constituency number from various text formats
found in Indian election result PDFs.
"""

import logging
import re
from typing import List, Optional

logger = logging.getLogger(__name__)


class ACExtractor:
    """
    Extract Assembly Constituency number from PDF text.
    
    Handles various formats:
    - "No. & Name of the Assembly Constituency: 149 - Ariyalur"
    - "AC no: 149"
    - "Assembly number: 149"
    - "No of Assembly constituency: 149"
    - "No & name of the Assembly constituency: 149 - Name"
    - Similar variations with different spacing, punctuation, and case
    """

    # Patterns to match AC number in various formats
    # Pattern 1: "No. & Name of the Assembly Constituency: 149 - Name"
    # Pattern 2: "AC no: 149" or "AC No: 149" or "AC NO: 149"
    # Pattern 3: "Assembly number: 149" or "Assembly Number: 149"
    # Pattern 4: "No of Assembly constituency: 149"
    # Pattern 5: "No & name of the Assembly constituency: 149 - Name"
    # Pattern 6: "Assembly Constituency No: 149"
    # Pattern 7: "Constituency No: 149"
    
    PATTERNS = [
        # Pattern: "No. & Name of the Assembly Constituency: 149 - Name"
        re.compile(
            r'(?:no\.?\s*&?\s*name\s+of\s+the\s+)?assembly\s+constituency[:\s]+(\d+)',
            re.IGNORECASE
        ),
        # Pattern: "AC no: 149" or "AC No: 149" or "AC NO: 149"
        re.compile(
            r'ac\s+no\.?\s*:?\s*(\d+)',
            re.IGNORECASE
        ),
        # Pattern: "Assembly number: 149"
        re.compile(
            r'assembly\s+number[:\s]+(\d+)',
            re.IGNORECASE
        ),
        # Pattern: "No of Assembly constituency: 149"
        re.compile(
            r'no\.?\s+of\s+assembly\s+constituency[:\s]+(\d+)',
            re.IGNORECASE
        ),
        # Pattern: "Assembly Constituency No: 149"
        re.compile(
            r'assembly\s+constituency\s+no\.?\s*:?\s*(\d+)',
            re.IGNORECASE
        ),
        # Pattern: "Constituency No: 149"
        re.compile(
            r'constituency\s+no\.?\s*:?\s*(\d+)',
            re.IGNORECASE
        ),
        # Pattern: "No & name of the Assembly constituency: 149 - Name"
        re.compile(
            r'no\.?\s*&?\s*name\s+of\s+the\s+assembly\s+constituency[:\s]+(\d+)',
            re.IGNORECASE
        ),
    ]

    @staticmethod
    def extract_ac_number(page_texts: List[str]) -> Optional[str]:
        """
        Extract AC number from PDF page texts.
        
        Args:
            page_texts: List of text content from each PDF page
            
        Returns:
            AC number as string (e.g., "149") or None if not found
        """
        if not page_texts:
            logger.warning("No page texts provided for AC extraction")
            return None
        
        # Combine all page texts, prioritizing first page
        combined_text = "\n".join(page_texts)
        
        # Try each pattern
        for pattern in ACExtractor.PATTERNS:
            matches = pattern.findall(combined_text)
            if matches:
                # Take the first match (most likely to be correct)
                ac_number = matches[0].strip()
                logger.info(f"Extracted AC number: {ac_number}")
                return ac_number
        
        # If no pattern matched, try a more flexible search
        # Look for patterns like "149 - Name" or ": 149" near "constituency" or "assembly"
        flexible_pattern = re.compile(
            r'(?:assembly|constituency|ac)[\s\w&:.-]*?[:\s-]+(\d{1,4})',
            re.IGNORECASE
        )
        matches = flexible_pattern.findall(combined_text)
        if matches:
            # Filter out obviously wrong numbers (too large, too small)
            for match in matches:
                num = int(match)
                # AC numbers are typically 1-300 for most states
                if 1 <= num <= 300:
                    logger.info(f"Extracted AC number (flexible match): {match}")
                    return match
        
        logger.warning("Could not extract AC number from PDF text")
        return None

    @staticmethod
    def extract_from_text(text: str) -> Optional[str]:
        """
        Extract AC number from a single text string.
        
        Args:
            text: Text content to search
            
        Returns:
            AC number as string or None if not found
        """
        return ACExtractor.extract_ac_number([text])


def extract_ac_number(page_texts: List[str]) -> Optional[str]:
    """
    Convenience function to extract AC number from page texts.
    
    Args:
        page_texts: List of text content from each PDF page
        
    Returns:
        AC number as string or None if not found
    """
    return ACExtractor.extract_ac_number(page_texts)

