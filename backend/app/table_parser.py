"""OCR Table Parser - Parse OCR text output into structured tables."""

import logging
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .models import TableData

# Column boundaries: list of (x_min, x_max) per column for stable assignment across pages
ColumnBoundaries = List[Tuple[float, float]]

logger = logging.getLogger(__name__)


@dataclass
class BoundingBox:
    """Bounding box for OCR text."""
    text: str
    x: int
    y: int
    width: int
    height: int
    confidence: float
    line_num: int = 0
    block_num: int = 0


class OCRTableParser:
    """
    Parse OCR text output into structured tables.

    Handles:
    - Election Form 20 format (primary use case)
    - Generic tabular data
    - Common OCR error correction (O vs 0, I vs 1, etc.)
    """

    # Common OCR character misreads
    OCR_CORRECTIONS = {
        'O': '0',  # Letter O to digit 0 (in numeric context)
        'o': '0',
        'I': '1',  # Letter I to digit 1
        'l': '1',  # Lowercase L to digit 1
        '|': '1',  # Pipe to digit 1
        'S': '5',  # S to 5 (sometimes)
        'B': '8',  # B to 8 (sometimes)
        'Z': '2',  # Z to 2
        'G': '6',  # G to 6
        '·': '.',  # Middle dot to period
        '—': '-',  # Em dash to hyphen
        '–': '-',  # En dash to hyphen
    }

    # Election Form 20 specific patterns
    FORM20_PATTERNS = {
        'polling_station': r'^(\d{1,4})\s*$',  # Polling station number
        'vote_count': r'^[\d,]+$',  # Numeric vote count
        'candidate_header': r'(candidate|name|party|votes?)',  # Header keywords
        'sl_no': r'^(sl\.?\s*no\.?|s\.?no\.?|sr\.?\s*no\.?)$',  # Serial number header
        'total_row': r'^(total|grand\s*total|sub\s*total)$',  # Total row indicator
    }

    def __init__(self):
        """Initialize the table parser."""
        pass

    def parse_election_form20(
        self,
        ocr_text: str,
        bounding_boxes: List[dict],
        page_number: int = 1,
        column_boundaries: Optional[ColumnBoundaries] = None,
        y_tolerance: int = 15,
    ) -> Optional[TableData]:
        """
        Parse OCR text from Election Form 20 format.

        Form 20 Structure:
        - Header row(s) with candidate names and party abbreviations
        - First column: Polling station numbers (sequential integers)
        - Subsequent columns: Vote counts for each candidate
        - Footer: Total row with sum of votes

        Args:
            ocr_text: Raw OCR text output
            bounding_boxes: List of bounding box dictionaries from OCR
            page_number: Page number (1-indexed)
            column_boundaries: Optional (x_min, x_max) per column from page 1 for stable alignment
            y_tolerance: Y-coordinate tolerance for grouping into rows (default 15)

        Returns:
            TableData or None if parsing fails
        """
        if not ocr_text.strip():
            return None

        logger.info(f"Parsing Election Form 20 from page {page_number}")

        # Split text into lines
        lines = ocr_text.strip().split('\n')
        lines = [line.strip() for line in lines if line.strip()]

        if len(lines) < 3:  # Need at least header + 2 data rows
            logger.warning("Not enough lines for Form 20 format")
            return None

        # Detect table structure from bounding boxes if available
        if bounding_boxes:
            table_data = self._parse_from_bounding_boxes(
                bounding_boxes, page_number,
                column_boundaries=column_boundaries,
                y_tolerance=y_tolerance,
            )
            if table_data and not table_data.is_empty:
                return table_data

        # Fallback to line-based parsing
        return self._parse_form20_from_lines(lines, page_number)

    def _parse_from_bounding_boxes(
        self,
        bounding_boxes: List[dict],
        page_number: int,
        column_boundaries: Optional[ColumnBoundaries] = None,
        y_tolerance: int = 15,
    ) -> Optional[TableData]:
        """
        Parse table structure using bounding box positions.

        Groups text by Y-coordinate to form rows. Columns are either sorted by X
        or assigned using column_boundaries (from page 1) for stable alignment.

        Args:
            bounding_boxes: List of bounding box dictionaries
            page_number: Page number
            column_boundaries: Optional (x_min, x_max) per column for assignment
            y_tolerance: Y-coordinate tolerance for same row

        Returns:
            TableData or None
        """
        if not bounding_boxes:
            return None

        # Convert to BoundingBox objects
        boxes = []
        for bb in bounding_boxes:
            if 'text' in bb and bb['text'].strip():
                boxes.append(BoundingBox(
                    text=bb['text'],
                    x=bb.get('x', bb.get('left', 0)),
                    y=bb.get('y', bb.get('top', 0)),
                    width=bb.get('width', 0),
                    height=bb.get('height', 0),
                    confidence=bb.get('confidence', 0),
                    line_num=bb.get('line_num', 0),
                    block_num=bb.get('block_num', 0),
                ))

        if not boxes:
            return None

        # Group boxes by line number if available, otherwise by Y-coordinate
        if any(b.line_num > 0 for b in boxes):
            rows = self._group_by_line_num(boxes)
        else:
            rows = self._group_by_y_coordinate(boxes, tolerance=y_tolerance)

        if len(rows) < 2:
            return None

        # Convert rows to string lists (with optional column boundaries)
        if column_boundaries:
            string_rows = self._rows_from_column_boundaries(rows, column_boundaries)
        else:
            string_rows = []
            for row_boxes in rows:
                sorted_boxes = sorted(row_boxes, key=lambda b: b.x)
                row = [b.text for b in sorted_boxes]
                string_rows.append(row)

        # Identify headers and data
        headers, data_rows = self._identify_headers_and_data(string_rows)

        if not headers or not data_rows:
            return None

        # Normalize to N columns and log when trimming
        n_cols = len(headers)
        normalized_data = []
        for i, row in enumerate(data_rows):
            if len(row) > n_cols:
                logger.debug(
                    "Page %s row %s: trimming %s cells to %s columns",
                    page_number, i + 1, len(row) - n_cols, n_cols,
                )
                row = row[:n_cols]
            elif len(row) < n_cols:
                row = self._pad_row(row, n_cols)
            normalized_data.append(row)

        # Correct OCR errors in numeric columns
        corrected_rows = []
        for row in normalized_data:
            corrected_row = self._correct_ocr_errors(row, headers)
            corrected_rows.append(corrected_row)

        return TableData(
            headers=headers,
            rows=corrected_rows,
            page_number=page_number,
        )

    def compute_column_boundaries(
        self,
        bounding_boxes: List[dict],
        y_tolerance: int = 15,
    ) -> Optional[ColumnBoundaries]:
        """
        Compute (x_min, x_max) per column from bounding boxes (e.g. from page 1).
        Use when parsing subsequent pages to keep column alignment stable.
        """
        if not bounding_boxes:
            return None
        boxes = []
        for bb in bounding_boxes:
            if "text" in bb and bb["text"].strip():
                boxes.append(BoundingBox(
                    text=bb["text"],
                    x=bb.get("x", bb.get("left", 0)),
                    y=bb.get("y", bb.get("top", 0)),
                    width=bb.get("width", 0),
                    height=bb.get("height", 0),
                    confidence=bb.get("confidence", 0),
                    line_num=bb.get("line_num", 0),
                    block_num=bb.get("block_num", 0),
                ))
        if not boxes:
            return None
        if any(b.line_num > 0 for b in boxes):
            rows = self._group_by_line_num(boxes)
        else:
            rows = self._group_by_y_coordinate(boxes, tolerance=y_tolerance)
        if not rows:
            return None
        max_cols = max(len(r) for r in rows)
        if max_cols == 0:
            return None
        # For each column index, get x range from all boxes in that column
        col_x_mins = []
        col_x_maxs = []
        for c in range(max_cols):
            xs = []
            for row_boxes in rows:
                sorted_row = sorted(row_boxes, key=lambda b: b.x)
                if c < len(sorted_row):
                    b = sorted_row[c]
                    xs.append(b.x)
                    xs.append(b.x + b.width)
            if xs:
                col_x_mins.append(min(xs))
                col_x_maxs.append(max(xs))
            else:
                col_x_mins.append(0)
                col_x_maxs.append(0)
        return list(zip(col_x_mins, col_x_maxs))

    def _rows_from_column_boundaries(
        self,
        rows: List[List[BoundingBox]],
        column_boundaries: ColumnBoundaries,
    ) -> List[List[str]]:
        """
        Build string rows by assigning each box to a column via X position.

        Multiple boxes in the same column are joined with a space.
        """
        n_cols = len(column_boundaries)
        string_rows = []
        for row_boxes in rows:
            cells = [[] for _ in range(n_cols)]
            for box in row_boxes:
                center_x = box.x + (box.width / 2.0)
                col_idx = None
                for c, (x_min, x_max) in enumerate(column_boundaries):
                    if x_min <= center_x <= x_max:
                        col_idx = c
                        break
                if col_idx is None:
                    # Assign to nearest column
                    for c, (x_min, x_max) in enumerate(column_boundaries):
                        if center_x < x_max:
                            col_idx = c
                            break
                    if col_idx is None:
                        col_idx = n_cols - 1
                cells[col_idx].append(box.text)
            row = [" ".join(cell).strip() for cell in cells]
            string_rows.append(row)
        return string_rows

    def _group_by_line_num(self, boxes: List[BoundingBox]) -> List[List[BoundingBox]]:
        """Group bounding boxes by line number."""
        lines_dict = {}
        for box in boxes:
            line_key = (box.block_num, box.line_num)
            if line_key not in lines_dict:
                lines_dict[line_key] = []
            lines_dict[line_key].append(box)

        # Sort by block then line number
        sorted_keys = sorted(lines_dict.keys())
        return [lines_dict[k] for k in sorted_keys]

    def _group_by_y_coordinate(
        self,
        boxes: List[BoundingBox],
        tolerance: int = 15
    ) -> List[List[BoundingBox]]:
        """
        Group bounding boxes by Y-coordinate into rows.

        Args:
            boxes: List of bounding boxes
            tolerance: Y-coordinate tolerance for same row

        Returns:
            List of rows, each row is a list of bounding boxes
        """
        if not boxes:
            return []

        # Sort by Y coordinate
        sorted_boxes = sorted(boxes, key=lambda b: b.y)

        rows = []
        current_row = [sorted_boxes[0]]
        current_y = sorted_boxes[0].y

        for box in sorted_boxes[1:]:
            if abs(box.y - current_y) <= tolerance:
                # Same row
                current_row.append(box)
            else:
                # New row
                rows.append(current_row)
                current_row = [box]
                current_y = box.y

        if current_row:
            rows.append(current_row)

        return rows

    def _parse_form20_from_lines(
        self,
        lines: List[str],
        page_number: int
    ) -> Optional[TableData]:
        """
        Parse Form 20 from text lines (fallback method).

        Args:
            lines: List of text lines
            page_number: Page number

        Returns:
            TableData or None
        """
        # Detect column structure by analyzing spacing patterns
        rows = []
        for line in lines:
            # Split by multiple spaces or tabs
            cells = re.split(r'\s{2,}|\t', line)
            cells = [c.strip() for c in cells if c.strip()]
            if cells:
                rows.append(cells)

        if len(rows) < 2:
            return None

        # Identify headers and data
        headers, data_rows = self._identify_headers_and_data(rows)

        if not headers:
            # Use first row as headers
            headers = rows[0]
            data_rows = rows[1:]

        # Normalize column counts
        max_cols = max(len(r) for r in [headers] + data_rows)
        headers = self._pad_row(headers, max_cols)
        data_rows = [self._pad_row(r, max_cols) for r in data_rows]

        # Correct OCR errors
        corrected_rows = []
        for row in data_rows:
            corrected_row = self._correct_ocr_errors(row, headers)
            corrected_rows.append(corrected_row)

        return TableData(
            headers=headers,
            rows=corrected_rows,
            page_number=page_number,
        )

    def _identify_headers_and_data(
        self,
        rows: List[List[str]]
    ) -> Tuple[List[str], List[List[str]]]:
        """
        Identify header rows and data rows from parsed rows.

        Headers typically:
        - Contain mostly text (not numbers)
        - Include keywords like "candidate", "party", "votes"
        - Are at the top of the table

        Args:
            rows: List of parsed rows

        Returns:
            Tuple of (headers, data_rows)
        """
        if not rows:
            return [], []

        header_rows = []
        data_start_idx = 0

        for idx, row in enumerate(rows[:5]):  # Check first 5 rows
            # Count numeric vs text cells
            numeric_count = 0
            text_count = 0
            has_header_keywords = False

            for cell in row:
                cell_clean = cell.strip().lower()

                # Check for header keywords
                if re.search(self.FORM20_PATTERNS['candidate_header'], cell_clean, re.I):
                    has_header_keywords = True
                if re.search(self.FORM20_PATTERNS['sl_no'], cell_clean, re.I):
                    has_header_keywords = True

                # Classify as numeric or text
                if self._is_numeric(cell):
                    numeric_count += 1
                else:
                    text_count += 1

            # Row is header if:
            # - Has header keywords, OR
            # - More text than numbers (60%+ text)
            total_cells = numeric_count + text_count
            if total_cells == 0:
                continue

            text_ratio = text_count / total_cells
            is_header = has_header_keywords or text_ratio >= 0.6

            if is_header:
                header_rows.append(row)
                data_start_idx = idx + 1
            else:
                # Found first data row
                break

        # If no headers detected, use first row
        if not header_rows and rows:
            header_rows = [rows[0]]
            data_start_idx = 1

        # Combine multi-row headers
        headers = self._combine_header_rows(header_rows)

        # Get data rows (skip duplicate headers)
        data_rows = []
        for row in rows[data_start_idx:]:
            # Skip rows that look like headers (repeat headers)
            if self._is_duplicate_header(row, header_rows):
                continue
            # Skip total rows (add them at the end if needed)
            if self._is_total_row(row):
                continue
            data_rows.append(row)

        return headers, data_rows

    def _combine_header_rows(self, header_rows: List[List[str]]) -> List[str]:
        """
        Combine multiple header rows into single headers.

        Args:
            header_rows: List of header rows

        Returns:
            Combined headers
        """
        if not header_rows:
            return []

        if len(header_rows) == 1:
            return header_rows[0]

        # Find max columns
        max_cols = max(len(r) for r in header_rows)

        combined = []
        for col_idx in range(max_cols):
            parts = []
            for row in header_rows:
                if col_idx < len(row) and row[col_idx].strip():
                    value = row[col_idx].strip()
                    # Skip generic spanning headers
                    if value.upper() not in ['NO. OF VALID VOTES', 'VALID VOTES', 'PARTY ABBREVIATION']:
                        parts.append(value)

            if parts:
                # Use most specific value (last non-empty)
                combined.append(parts[-1])
            else:
                combined.append(f"Column {col_idx + 1}")

        return combined

    def _is_duplicate_header(self, row: List[str], header_rows: List[List[str]]) -> bool:
        """Check if row is a duplicate of header rows."""
        if not row or not header_rows:
            return False

        # Quick check: if first cell is numeric, it's data not header
        first_cell = row[0].strip() if row else ""
        if first_cell and self._is_numeric(first_cell):
            return False

        for header_row in header_rows:
            # Compare non-empty cells
            matches = 0
            comparisons = 0
            for i in range(min(len(row), len(header_row))):
                r_val = row[i].strip().lower()
                h_val = header_row[i].strip().lower()
                if r_val and h_val:
                    comparisons += 1
                    if r_val == h_val:
                        matches += 1

            if comparisons >= 3 and matches / comparisons >= 0.8:
                return True

        return False

    def _is_total_row(self, row: List[str]) -> bool:
        """Check if row is a total/summary row."""
        if not row:
            return False

        first_cell = row[0].strip().lower()
        return bool(re.search(self.FORM20_PATTERNS['total_row'], first_cell, re.I))

    def _is_numeric(self, value: str) -> bool:
        """Check if string represents a number."""
        if not value:
            return False
        # Remove common formatting
        cleaned = value.strip().replace(',', '').replace(' ', '')
        try:
            float(cleaned)
            return True
        except ValueError:
            return False

    def _correct_ocr_errors(self, row: List[str], headers: List[str]) -> List[str]:
        """
        Correct common OCR errors in a row.

        Args:
            row: Data row
            headers: Column headers (to determine column type)

        Returns:
            Corrected row
        """
        corrected = []

        for idx, cell in enumerate(row):
            # Determine if this column should be numeric
            is_numeric_column = False
            if idx < len(headers):
                header = headers[idx].lower()
                # Columns that should be numeric
                numeric_keywords = ['votes', 'count', 'total', 'no.', 'sl', 'station']
                is_numeric_column = any(kw in header for kw in numeric_keywords)

            # Also check if the cell looks mostly numeric
            if not is_numeric_column:
                digit_count = sum(1 for c in cell if c.isdigit())
                is_numeric_column = digit_count > len(cell) * 0.5

            if is_numeric_column:
                corrected_cell = self._correct_numeric_cell(cell)
            else:
                corrected_cell = self._correct_text_cell(cell)

            corrected.append(corrected_cell)

        return corrected

    def _correct_numeric_cell(self, cell: str) -> str:
        """
        Correct OCR errors in a numeric cell.

        Args:
            cell: Cell value

        Returns:
            Corrected cell value
        """
        if not cell:
            return cell

        corrected = cell.strip()

        # Apply character corrections
        for wrong, correct in self.OCR_CORRECTIONS.items():
            # Only replace if it makes the cell more numeric
            if wrong.isalpha():
                # Replace letters that might be misread digits
                corrected = corrected.replace(wrong, correct)

        # Remove any remaining non-numeric characters except comma and period
        # But preserve the original if it's clearly not a number
        numeric_chars = set('0123456789,.')
        if all(c in numeric_chars or c.isspace() for c in corrected):
            # Remove spaces
            corrected = corrected.replace(' ', '')

        return corrected

    def _correct_text_cell(self, cell: str) -> str:
        """
        Correct OCR errors in a text cell.

        Args:
            cell: Cell value

        Returns:
            Corrected cell value
        """
        if not cell:
            return cell

        corrected = cell.strip()

        # Fix common dash/hyphen variants
        corrected = corrected.replace('—', '-').replace('–', '-')

        # Fix middle dots
        corrected = corrected.replace('·', '.')

        # Normalize whitespace
        corrected = ' '.join(corrected.split())

        return corrected

    def _pad_row(self, row: List[str], target_length: int) -> List[str]:
        """Pad row to target length with empty strings."""
        if len(row) >= target_length:
            return row[:target_length]
        return row + [''] * (target_length - len(row))

    def parse_generic_table(
        self,
        ocr_text: str,
        bounding_boxes: List[dict],
        page_number: int = 1
    ) -> Optional[TableData]:
        """
        Parse a generic table from OCR output.

        Used as fallback when Form 20 parsing fails.

        Args:
            ocr_text: Raw OCR text
            bounding_boxes: Bounding box data
            page_number: Page number

        Returns:
            TableData or None
        """
        if not ocr_text.strip():
            return None

        logger.info(f"Parsing generic table from page {page_number}")

        # Try bounding box approach first
        if bounding_boxes:
            result = self._parse_from_bounding_boxes(bounding_boxes, page_number)
            if result:
                return result

        # Fallback to line-based parsing
        lines = ocr_text.strip().split('\n')
        lines = [line.strip() for line in lines if line.strip()]

        if len(lines) < 2:
            return None

        # Parse rows by splitting on whitespace
        rows = []
        for line in lines:
            # Try tab-separated first
            if '\t' in line:
                cells = line.split('\t')
            else:
                # Split by multiple spaces
                cells = re.split(r'\s{2,}', line)

            cells = [c.strip() for c in cells if c.strip()]
            if cells:
                rows.append(cells)

        if len(rows) < 2:
            return None

        # Normalize column count
        max_cols = max(len(r) for r in rows)
        rows = [self._pad_row(r, max_cols) for r in rows]

        # First row as headers
        headers = rows[0]
        data_rows = rows[1:]

        return TableData(
            headers=headers,
            rows=data_rows,
            page_number=page_number,
        )
