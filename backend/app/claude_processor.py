"""AI-powered PDF analysis using Anthropic Claude."""

import hashlib
import json
import logging
import os
from typing import Dict, List, Optional, Tuple

from anthropic import Anthropic, AnthropicError

from .party_normalizer import PartyNormalizer

logger = logging.getLogger(__name__)


class ClaudeProcessor:
    """
    AI processor for intelligent PDF extraction features using Anthropic Claude.

    Features:
    - Document heading detection from page text
    - Column header standardization across tables
    - Data completeness validation
    - Enhanced table structure analysis
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-sonnet-4-20250514"):
        """
        Initialize the Claude AI processor.

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            model: Claude model to use (default: claude-sonnet-4-20250514 for best quality)
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model
        self.client = None
        self.enabled = False
        self._response_cache: Dict[str, any] = {}
        self.party_normalizer = PartyNormalizer()

        if self.api_key:
            try:
                self.client = Anthropic(api_key=self.api_key)
                self.enabled = True
                logger.info(f"Claude AI processor initialized with model: {self.model}")
            except Exception as e:
                logger.error(f"Failed to initialize Anthropic client: {e}")
                self.enabled = False
        else:
            logger.warning("ANTHROPIC_API_KEY not set, AI features disabled")

    def extract_document_heading(
        self,
        page_texts: List[str],
        fallback: str = "Untitled Document",
    ) -> Tuple[str, float]:
        """
        Extract the main document heading from page text using Claude AI.

        Args:
            page_texts: List of text content from each page
            fallback: Fallback heading if extraction fails

        Returns:
            Tuple of (heading, confidence_score)
        """
        if not self.enabled or not page_texts:
            return fallback, 0.0

        try:
            # Use first page text (usually contains the main heading)
            first_page_text = page_texts[0][:2000]  # Limit to first 2000 chars

            # Check cache
            cache_key = self._get_cache_key("heading", first_page_text)
            if cache_key in self._response_cache:
                logger.info("Using cached heading response")
                return self._response_cache[cache_key]

            # Create prompt for Claude
            prompt = f"""Analyze this PDF page text and identify the main document heading or title.
Look for text that appears at the top and represents the document's subject.
The heading is typically in larger font, bold, or positioned prominently.

IMPORTANT: Extract the COMPLETE heading, preserving all lines if it's multi-line.
For example, if the heading is:
  FORM 20 - FINAL RESULT SHEET - PART - I
  GENERAL ELECTIONS TO TAMIL NADU LEGISLATIVE ASSEMBLY 2021
Then return both lines exactly as shown.

Page text:
{first_page_text}

Return ONLY the heading text (may be multi-line), nothing else. If no clear heading exists, return "Untitled Document"."""

            # Call Claude API
            message = self.client.messages.create(
                model=self.model,
                max_tokens=100,
                temperature=0.3,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            )

            # Extract heading from response
            heading = message.content[0].text.strip()

            # Clean up the heading
            heading = heading.strip('"').strip("'").strip()

            # If heading is too long or generic, use fallback
            if len(heading) > 200 or heading.lower() in ["untitled document", "none", "n/a"]:
                heading = fallback
                confidence = 0.3
            else:
                confidence = 0.95  # Claude typically gives high-quality results

            result = (heading, confidence)
            self._response_cache[cache_key] = result

            logger.info(f"Claude extracted heading: '{heading}' (confidence: {confidence})")
            return result

        except AnthropicError as e:
            logger.error(f"Anthropic API error during heading extraction: {e}")
            return fallback, 0.0
        except Exception as e:
            logger.error(f"Unexpected error during heading extraction: {e}")
            return fallback, 0.0

    def standardize_column_headers(
        self,
        all_headers: List[List[str]],
    ) -> Tuple[Dict[str, List[str]], float]:
        """
        Create a standardized column schema by analyzing headers from all tables using Claude.

        Args:
            all_headers: List of header lists from each table

        Returns:
            Tuple of (column_mapping, confidence_score)
            column_mapping format: {"Standard Name": ["Variant1", "Variant2", ...]}
        """
        if not self.enabled or not all_headers:
            # Fallback: use first table headers as standard
            if all_headers and all_headers[0]:
                mapping = {header: [header] for header in all_headers[0]}
                return mapping, 0.0
            return {}, 0.0

        try:
            # Filter out empty headers
            valid_headers = [headers for headers in all_headers if headers]
            if not valid_headers:
                return {}, 0.0

            # If all tables have identical headers, no standardization needed
            if all(headers == valid_headers[0] for headers in valid_headers):
                mapping = {header: [header] for header in valid_headers[0]}
                return mapping, 1.0

            # Check cache
            headers_str = json.dumps(valid_headers, sort_keys=True)
            cache_key = self._get_cache_key("headers", headers_str)
            if cache_key in self._response_cache:
                logger.info("Using cached column standardization response")
                return self._response_cache[cache_key]

            # Create prompt for Claude
            headers_list = "\n".join(
                [f"Table {i+1}: {json.dumps(headers)}" for i, headers in enumerate(valid_headers)]
            )

            prompt = f"""You are analyzing table headers from a multi-page PDF. Different pages may use slightly different column names for the same data.

Headers from all tables:
{headers_list}

Task: Create a standardized column schema. Map all variations to a single canonical name.
Choose the most descriptive name as the standard. Group similar columns together.

CRITICAL REQUIREMENTS:
1. Preserve exact column names - do NOT translate, abbreviate, or modify them
2. If a column appears with the same exact name in multiple tables, group all instances under that name
3. Only group columns that are genuinely variations (e.g., "Name" and "CANDIDATE NAME", or "Total" and "TOTAL VOTES")
4. Keep the MOST DESCRIPTIVE original name as the standard (prefer longer, more detailed names)
5. Maintain the ORIGINAL ORDER of columns as they appear in the first table

Return ONLY valid JSON in this exact format (no markdown, no explanations):
{{
  "Standard Name 1": ["Exact Match 1", "Variation 1", "Variation 2"],
  "Standard Name 2": ["Exact Match 2", "Variation 3"],
  ...
}}

Important:
- Use the most common or descriptive ORIGINAL name as the standard
- Include ALL column names from ALL tables
- Each column should appear exactly once in the mapping
- Preserve special characters, numbers, and formatting from original headers
- Return only the JSON object, no additional text or code blocks"""

            # Call Claude API
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                temperature=0.2,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            )

            # Extract JSON from response
            content = message.content[0].text.strip()

            # Remove markdown code blocks if present
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            # Parse JSON response
            column_mapping = json.loads(content)

            # Validate mapping
            if not isinstance(column_mapping, dict):
                raise ValueError("Invalid mapping format")

            # Verify all headers are mapped
            all_header_names = set()
            for headers in valid_headers:
                all_header_names.update(headers)

            mapped_headers = set()
            for variants in column_mapping.values():
                mapped_headers.update(variants)

            coverage = len(mapped_headers) / len(all_header_names) if all_header_names else 0
            confidence = min(coverage, 0.95)

            # Apply party name normalization
            logger.info("Applying Tamil Nadu party name normalization")
            column_mapping = self.party_normalizer.normalize_column_mapping(column_mapping)

            result = (column_mapping, confidence)
            self._response_cache[cache_key] = result

            logger.info(f"Claude standardized {len(column_mapping)} columns (confidence: {confidence})")
            logger.debug(f"Column mapping: {json.dumps(column_mapping, indent=2)}")

            return result

        except (AnthropicError, json.JSONDecodeError, ValueError) as e:
            logger.error(f"Error during column standardization with Claude: {e}")
            # Fallback: use first table headers
            if valid_headers and valid_headers[0]:
                mapping = {header: [header] for header in valid_headers[0]}
                return mapping, 0.0
            return {}, 0.0
        except Exception as e:
            logger.error(f"Unexpected error during column standardization: {e}")
            if valid_headers and valid_headers[0]:
                mapping = {header: [header] for header in valid_headers[0]}
                return mapping, 0.0
            return {}, 0.0

    def analyze_table_structure(
        self,
        page_text: str,
        extracted_table: List[List[str]],
    ) -> Tuple[Dict[str, any], float]:
        """
        Use Claude to analyze and improve table structure extraction.

        Args:
            page_text: Raw text from the PDF page
            extracted_table: Initial table extraction result

        Returns:
            Tuple of (analysis_result, confidence_score)
            analysis_result contains:
            - has_title: boolean
            - title_rows: list of indices
            - header_rows: list of indices
            - data_start_row: int
        """
        if not self.enabled or not page_text or not extracted_table:
            return {
                "has_title": False,
                "title_rows": [],
                "header_rows": [0],
                "data_start_row": 1,
            }, 0.0

        try:
            # Create a summary of the table for analysis
            table_preview = "\n".join(
                ["|".join(str(cell) for cell in row) for row in extracted_table[:10]]
            )

            prompt = f"""Analyze this table structure from a PDF and identify its components:

Page Text (first 500 chars):
{page_text[:500]}

Table Preview (first 10 rows):
{table_preview}

Identify:
1. Title rows: Rows containing document titles or headers (usually merged cells or centered text)
2. Column header rows: Rows containing column names
3. Data start row: First row of actual data

Return ONLY valid JSON:
{{
  "has_title": true/false,
  "title_rows": [list of row indices starting from 0],
  "header_rows": [list of row indices],
  "data_start_row": integer
}}"""

            message = self.client.messages.create(
                model=self.model,
                max_tokens=200,
                temperature=0.1,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            )

            content = message.content[0].text.strip()

            # Parse JSON
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            analysis = json.loads(content)

            return analysis, 0.9

        except Exception as e:
            logger.error(f"Error during table structure analysis: {e}")
            return {
                "has_title": False,
                "title_rows": [],
                "header_rows": [0],
                "data_start_row": 1,
            }, 0.0

    def validate_table_extraction(
        self,
        pdf_text_sample: str,
        extracted_row_count: int,
    ) -> Tuple[bool, float]:
        """
        Validate that table extraction is complete by analyzing PDF text.

        Args:
            pdf_text_sample: Sample of PDF text content
            extracted_row_count: Number of rows extracted

        Returns:
            Tuple of (is_complete, confidence_score)
        """
        if not self.enabled or not pdf_text_sample:
            return True, 0.0

        try:
            # Simple heuristic: check if text contains reasonable number of line breaks
            line_count = pdf_text_sample.count("\n")

            # If extracted rows are roughly aligned with text lines, likely complete
            if line_count > 0:
                ratio = extracted_row_count / line_count
                is_complete = 0.3 <= ratio <= 3.0  # Allow 3x variance
                confidence = 0.7 if is_complete else 0.3
            else:
                is_complete = extracted_row_count > 0
                confidence = 0.5

            logger.info(
                f"Extraction validation: {extracted_row_count} rows extracted, "
                f"{line_count} lines in text (complete: {is_complete}, confidence: {confidence})"
            )

            return is_complete, confidence

        except Exception as e:
            logger.error(f"Error during extraction validation: {e}")
            return True, 0.0

    def _get_cache_key(self, prefix: str, content: str) -> str:
        """Generate a cache key for response caching."""
        content_hash = hashlib.md5(content.encode()).hexdigest()
        return f"{prefix}:{content_hash}"

    def clear_cache(self):
        """Clear the response cache."""
        self._response_cache.clear()
        logger.info("Claude AI response cache cleared")
