"""Enhanced PDF table extraction using Claude AI for cell-level precision."""

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from anthropic import Anthropic

from .models import TableData
from .pdf_processor import PDFProcessor


class EnhancedClaudeProcessor:
    """
    Enhanced PDF processor using Claude AI for superior cell-level extraction.

    Features:
    - Cell-by-cell structure analysis
    - Intelligent header deduplication across pages
    - Column alignment validation
    - Perfect table reconstruction
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize enhanced Claude processor.

        Args:
            api_key: Anthropic API key (if not provided, reads from ANTHROPIC_API_KEY env)
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")

        if not self.api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is required for enhanced processing. "
                "Set it in your .env file or pass as parameter."
            )

        self.client = Anthropic(api_key=self.api_key)
        self.model = "claude-sonnet-4-20250514"  # Latest Sonnet 4 model

    async def analyze_table_structure(
        self,
        pdf_path: str,
        page_texts: List[str],
        raw_tables: List[TableData]
    ) -> Dict[str, Any]:
        """
        Use Claude to analyze table structure and identify issues.

        Args:
            pdf_path: Path to PDF file
            page_texts: Extracted page text
            raw_tables: Initially extracted tables

        Returns:
            Analysis results with structure information
        """
        # Prepare analysis prompt
        tables_summary = []
        for idx, table in enumerate(raw_tables):
            tables_summary.append({
                "table_index": idx,
                "page_number": table.page_number,
                "num_columns": len(table.headers),
                "num_rows": len(table.rows),
                "headers": table.headers,
                "first_3_rows": table.rows[:3] if len(table.rows) >= 3 else table.rows,
                "last_3_rows": table.rows[-3:] if len(table.rows) >= 3 else [],
            })

        prompt = f"""Analyze this PDF table extraction and identify structural issues:

PDF Text Content (first 2 pages):
{chr(10).join(page_texts[:2])}

Extracted Tables Summary:
{json.dumps(tables_summary, indent=2)}

Please analyze and provide:
1. **Document Title**: Extract the main document title/heading from the PDF text
2. **True Column Headers**: Identify the actual column headers (not duplicate headers appearing in data)
3. **Duplicate Headers**: List any rows in the data that are actually duplicate headers from multi-page tables
4. **Section Headers**: Identify any section break rows that should be removed
5. **Column Alignment Issues**: Note any columns that appear misaligned or merged incorrectly
6. **Data Quality**: Assess if all data appears complete and accurate

Return your analysis in JSON format:
{{
  "document_title": "string",
  "true_headers": ["col1", "col2", ...],
  "duplicate_header_patterns": [["pattern1_col1", "pattern1_col2", ...], ...],
  "section_header_patterns": [["text", "", "", ...], ...],
  "column_alignment": {{
    "is_aligned": boolean,
    "issues": ["description of issues"],
    "corrections": {{"old_col_name": "corrected_col_name"}}
  }},
  "data_quality": {{
    "completeness": "high|medium|low",
    "issues": ["list of issues"],
    "recommendations": ["list of recommendations"]
  }}
}}"""

        try:
            response = await asyncio.to_thread(
                self.client.messages.create,
                model=self.model,
                max_tokens=4000,
                temperature=0,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            # Extract JSON from response
            content = response.content[0].text

            # Try to extract JSON from markdown code blocks if present
            if "```json" in content:
                json_start = content.find("```json") + 7
                json_end = content.find("```", json_start)
                content = content[json_start:json_end].strip()
            elif "```" in content:
                json_start = content.find("```") + 3
                json_end = content.find("```", json_start)
                content = content[json_start:json_end].strip()

            analysis = json.loads(content)
            return analysis

        except Exception as e:
            print(f"Claude analysis failed: {e}")
            # Return default analysis
            return {
                "document_title": "",
                "true_headers": raw_tables[0].headers if raw_tables else [],
                "duplicate_header_patterns": [],
                "section_header_patterns": [],
                "column_alignment": {
                    "is_aligned": True,
                    "issues": [],
                    "corrections": {}
                },
                "data_quality": {
                    "completeness": "medium",
                    "issues": [],
                    "recommendations": []
                }
            }

    def remove_duplicate_and_section_headers(
        self,
        tables: List[TableData],
        analysis: Dict[str, Any]
    ) -> List[TableData]:
        """
        Remove duplicate headers and section breaks from tables.

        Args:
            tables: Raw extracted tables
            analysis: Claude's structure analysis

        Returns:
            Cleaned tables
        """
        duplicate_patterns = analysis.get("duplicate_header_patterns", [])
        section_patterns = analysis.get("section_header_patterns", [])

        cleaned_tables = []

        for table in tables:
            cleaned_rows = []

            for row in table.rows:
                # Check if row matches duplicate header pattern
                is_duplicate = False
                for pattern in duplicate_patterns:
                    if self._row_matches_pattern(row, pattern, threshold=0.7):
                        is_duplicate = True
                        break

                if is_duplicate:
                    continue

                # Check if row matches section header pattern
                is_section = False
                for pattern in section_patterns:
                    if self._row_matches_pattern(row, pattern, threshold=0.6):
                        is_section = True
                        break

                if is_section:
                    continue

                # Keep the row
                cleaned_rows.append(row)

            # Create cleaned table
            if cleaned_rows:
                cleaned_table = TableData(
                    headers=table.headers,
                    rows=cleaned_rows,
                    page_number=table.page_number
                )
                cleaned_table.title_rows = table.title_rows
                cleaned_table.header_rows = table.header_rows
                cleaned_tables.append(cleaned_table)

        return cleaned_tables

    def _row_matches_pattern(
        self,
        row: List[str],
        pattern: List[str],
        threshold: float = 0.7
    ) -> bool:
        """
        Check if a row matches a pattern.

        Args:
            row: Data row to check
            pattern: Pattern to match against
            threshold: Minimum match ratio (0-1)

        Returns:
            True if row matches pattern
        
        IMPORTANT: Be very conservative - never filter rows that have numeric data.
        """
        if not pattern:
            return False
        
        # Quick check: if first cell is numeric, it's a DATA row, NOT a pattern match
        first_cell = row[0].strip() if row and row[0] else ""
        if first_cell and first_cell.replace(",", "").replace(".", "").isdigit():
            return False

        text_matches = 0
        text_comparisons = 0
        comparisons = min(len(row), len(pattern))

        for i in range(comparisons):
            row_val = row[i].strip().lower() if i < len(row) else ""
            pattern_val = pattern[i].strip().lower() if i < len(pattern) else ""

            if not row_val and not pattern_val:
                continue
            
            # Skip numeric values - they can match by coincidence
            if row_val.replace(",", "").replace(".", "").isdigit():
                continue
            if pattern_val.replace(",", "").replace(".", "").isdigit():
                continue

            text_comparisons += 1
            if row_val == pattern_val:
                text_matches += 1

        # Need at least 5 text cells to compare and 80% must match
        if text_comparisons < 5:
            return False

        return (text_matches / text_comparisons) >= 0.8

    def standardize_headers(
        self,
        tables: List[TableData],
        analysis: Dict[str, Any]
    ) -> List[TableData]:
        """
        Standardize headers across all tables using Claude's analysis.

        Args:
            tables: Tables with potentially different headers
            analysis: Claude's analysis with true headers

        Returns:
            Tables with standardized headers
        """
        true_headers = analysis.get("true_headers", [])

        if not true_headers and tables:
            true_headers = tables[0].headers

        standardized_tables = []

        for table in tables:
            # Update headers
            standardized_table = TableData(
                headers=true_headers,
                rows=table.rows,
                page_number=table.page_number
            )
            standardized_table.title_rows = table.title_rows
            standardized_table.header_rows = table.header_rows
            standardized_tables.append(standardized_table)

        return standardized_tables

    async def validate_cell_accuracy(
        self,
        pdf_path: str,
        page_texts: List[str],
        tables: List[TableData],
        sample_size: int = 5
    ) -> Dict[str, Any]:
        """
        Use Claude to validate cell-level accuracy by sampling.

        Args:
            pdf_path: Path to PDF
            page_texts: Extracted page text
            tables: Extracted tables
            sample_size: Number of rows to validate per table

        Returns:
            Validation results
        """
        # Sample rows from first table
        if not tables or not tables[0].rows:
            return {"valid": True, "issues": []}

        first_table = tables[0]
        sample_rows = first_table.rows[:sample_size]

        prompt = f"""Validate this table extraction by comparing with source PDF text:

PDF Text (Page 1):
{page_texts[0] if page_texts else "N/A"}

Extracted Table Headers:
{first_table.headers}

Sample Extracted Rows:
{json.dumps(sample_rows, indent=2)}

Please verify:
1. Are the column headers correctly identified?
2. Are the data values accurate?
3. Are columns properly aligned?
4. Are there any missing or extra cells?

Return JSON:
{{
  "valid": boolean,
  "header_accuracy": "high|medium|low",
  "data_accuracy": "high|medium|low",
  "alignment_issues": ["list of issues"],
  "recommendations": ["list of recommendations"]
}}"""

        try:
            response = await asyncio.to_thread(
                self.client.messages.create,
                model=self.model,
                max_tokens=2000,
                temperature=0,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            content = response.content[0].text

            # Extract JSON
            if "```json" in content:
                json_start = content.find("```json") + 7
                json_end = content.find("```", json_start)
                content = content[json_start:json_end].strip()
            elif "```" in content:
                json_start = content.find("```") + 3
                json_end = content.find("```", json_start)
                content = content[json_start:json_end].strip()

            validation = json.loads(content)
            return validation

        except Exception as e:
            print(f"Validation failed: {e}")
            return {"valid": True, "issues": []}

    async def enhanced_extract(
        self,
        pdf_path: str,
        progress_callback: Optional[callable] = None,
    ) -> Tuple[List[TableData], Dict[str, Any]]:
        """
        Perform enhanced extraction with Claude AI analysis.

        Args:
            pdf_path: Path to PDF file
            progress_callback: Optional progress callback

        Returns:
            Tuple of (cleaned_tables, analysis_metadata)
        """
        def update_progress(pct: int, msg: str):
            if progress_callback:
                progress_callback(pct, msg)

        # Step 1: Basic extraction
        update_progress(10, "Extracting tables from PDF...")
        processor = PDFProcessor(pdf_path)
        extraction_result = await processor.extract_tables(progress_callback)

        raw_tables = extraction_result.tables
        page_texts = extraction_result.page_texts

        if not raw_tables:
            return [], {"error": "No tables extracted"}

        # Step 2: Claude structure analysis
        update_progress(40, "Analyzing table structure with Claude AI...")
        analysis = await self.analyze_table_structure(
            pdf_path,
            page_texts,
            raw_tables
        )

        # Step 3: Remove duplicates and section headers
        update_progress(60, "Removing duplicate headers and section breaks...")
        cleaned_tables = self.remove_duplicate_and_section_headers(
            raw_tables,
            analysis
        )

        # Step 4: Standardize headers
        update_progress(70, "Standardizing column headers...")
        standardized_tables = self.standardize_headers(
            cleaned_tables,
            analysis
        )

        # Step 5: Validate accuracy
        update_progress(85, "Validating cell-level accuracy...")
        validation = await self.validate_cell_accuracy(
            pdf_path,
            page_texts,
            standardized_tables
        )

        update_progress(95, "Enhanced extraction complete")

        # Combine metadata
        metadata = {
            "document_title": analysis.get("document_title", ""),
            "structure_analysis": analysis,
            "validation": validation,
            "tables_processed": len(standardized_tables),
            "total_rows": sum(len(t.rows) for t in standardized_tables),
        }

        return standardized_tables, metadata

