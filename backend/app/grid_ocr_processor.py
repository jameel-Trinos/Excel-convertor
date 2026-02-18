"""Grid-line-based OCR table extraction for scanned PDFs.

Detects physical table grid lines using OpenCV morphological operations,
extracts cell rectangles from line intersections, then OCRs each cell
individually for accurate column alignment.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import cv2
import numpy as np

from .models import TableData

logger = logging.getLogger(__name__)


@dataclass
class GridCell:
    """A single cell in the detected grid."""
    row: int
    col: int
    x: int
    y: int
    width: int
    height: int
    text: str = ""
    confidence: float = 0.0


@dataclass
class GridDetectionResult:
    """Result of grid line detection on a single page image."""
    cells: List[GridCell] = field(default_factory=list)
    num_rows: int = 0
    num_cols: int = 0
    horizontal_lines: List[int] = field(default_factory=list)
    vertical_lines: List[int] = field(default_factory=list)
    grid_detected: bool = False


class GridLineDetector:
    """
    Detect table grid lines in a page image using OpenCV morphological operations.

    Uses multiple binarization strategies and kernel sizes for robustness:
    1. Adaptive threshold (Gaussian) — good for uneven lighting
    2. Otsu's threshold — good for clean scans
    3. Simple binary threshold — fallback for high-contrast scans

    For each binarization, tries multiple kernel sizes to handle tables
    that don't span the full page width.
    """

    def __init__(
        self,
        line_thickness: int = 2,
        cluster_tolerance: int = 15,
    ):
        self.line_thickness = line_thickness
        self.cluster_tolerance = cluster_tolerance

    def detect_grid(
        self,
        image: np.ndarray,
        expected_cols: Optional[int] = None,
    ) -> GridDetectionResult:
        """
        Detect horizontal and vertical grid lines in the image.

        Tries multiple binarization methods and kernel sizes, picking
        the result with the most lines detected.

        Args:
            image: Grayscale or BGR image (numpy array)
            expected_cols: If known (from page 1), prefer results matching this col count

        Returns:
            GridDetectionResult with line positions
        """
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        h, w = gray.shape

        # Generate binary images with different thresholding strategies
        binaries = self._get_binary_images(gray)

        # Try different kernel length ratios (from small to large)
        # Smaller ratios detect shorter lines (tables that don't span full page)
        # 0.06 helps very narrow tables; 0.08-0.25 cover typical election tables
        kernel_ratios = [0.06, 0.08, 0.12, 0.18, 0.25]

        best_result = None
        best_score = -1

        for binary in binaries:
            for ratio in kernel_ratios:
                h_kernel_len = max(int(w * ratio), 30)
                v_kernel_len = max(int(h * ratio), 30)

                h_lines, v_lines = self._detect_lines_with_params(
                    binary, h_kernel_len, v_kernel_len
                )

                if len(h_lines) < 3 or len(v_lines) < 3:
                    continue

                # Score the result
                score = self._score_grid(h_lines, v_lines, expected_cols)

                if score > best_score:
                    best_score = score
                    best_result = (h_lines, v_lines)

        if best_result is None:
            logger.debug(
                f"No grid detected after trying {len(binaries)} binarizations "
                f"x {len(kernel_ratios)} kernel sizes"
            )
            return GridDetectionResult(grid_detected=False)

        h_lines, v_lines = best_result

        logger.info(
            f"Grid detected: {len(h_lines)} horizontal lines, "
            f"{len(v_lines)} vertical lines "
            f"({len(h_lines) - 1} rows x {len(v_lines) - 1} cols)"
        )

        return GridDetectionResult(
            horizontal_lines=h_lines,
            vertical_lines=v_lines,
            num_rows=max(0, len(h_lines) - 1),
            num_cols=max(0, len(v_lines) - 1),
            grid_detected=True,
        )

    def _get_binary_images(self, gray: np.ndarray) -> List[np.ndarray]:
        """
        Generate multiple binary images using different thresholding strategies.

        Returns:
            List of binary (inverted) images
        """
        binaries = []

        # Strategy 1: Adaptive threshold (Gaussian) — handles uneven lighting
        try:
            adaptive = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY_INV, 15, 5
            )
            binaries.append(adaptive)
        except Exception:
            pass

        # Strategy 2: Adaptive threshold with larger block size
        try:
            adaptive_large = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY_INV, 25, 8
            )
            binaries.append(adaptive_large)
        except Exception:
            pass

        # Strategy 3: Otsu's threshold — good for bimodal histograms (clean scans)
        try:
            _, otsu = cv2.threshold(
                gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
            )
            binaries.append(otsu)
        except Exception:
            pass

        # Strategy 4: Fixed threshold — good for high-contrast scans
        try:
            _, fixed = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY_INV)
            binaries.append(fixed)
        except Exception:
            pass

        # Strategy 4b: Lighter fixed threshold — for faint/faded grid lines
        try:
            _, light = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
            binaries.append(light)
        except Exception:
            pass

        # Strategy 5: Adaptive threshold (Mean) — alternative to Gaussian
        try:
            adaptive_mean = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                cv2.THRESH_BINARY_INV, 15, 10
            )
            binaries.append(adaptive_mean)
        except Exception:
            pass

        return binaries

    def _detect_lines_with_params(
        self,
        binary: np.ndarray,
        h_kernel_len: int,
        v_kernel_len: int,
    ) -> Tuple[List[int], List[int]]:
        """
        Detect horizontal and vertical lines with specific kernel sizes.

        Args:
            binary: Binary (inverted) image
            h_kernel_len: Horizontal kernel length in pixels
            v_kernel_len: Vertical kernel length in pixels

        Returns:
            Tuple of (horizontal_line_positions, vertical_line_positions)
        """
        # Horizontal line detection
        h_kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT, (h_kernel_len, self.line_thickness)
        )
        h_mask = cv2.morphologyEx(binary, cv2.MORPH_OPEN, h_kernel)

        # Dilate slightly to connect broken line segments
        dilate_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        h_mask = cv2.dilate(h_mask, dilate_kernel, iterations=1)

        h_positions = self._extract_line_positions(h_mask, "horizontal")
        h_lines = self._cluster_lines(h_positions)

        # Vertical line detection
        v_kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT, (self.line_thickness, v_kernel_len)
        )
        v_mask = cv2.morphologyEx(binary, cv2.MORPH_OPEN, v_kernel)
        v_mask = cv2.dilate(v_mask, dilate_kernel, iterations=1)

        v_positions = self._extract_line_positions(v_mask, "vertical")
        v_lines = self._cluster_lines(v_positions)

        return h_lines, v_lines

    def _score_grid(
        self,
        h_lines: List[int],
        v_lines: List[int],
        expected_cols: Optional[int] = None,
    ) -> float:
        """
        Score a grid detection result. Higher is better.

        Prefers:
        - More rows (up to a reasonable limit)
        - Column count matching expected_cols (if provided)
        - Evenly spaced lines (consistent row heights / column widths)

        Args:
            h_lines: Horizontal line positions
            v_lines: Vertical line positions
            expected_cols: Expected number of columns (from page 1)

        Returns:
            Score value (higher = better grid)
        """
        num_rows = len(h_lines) - 1
        num_cols = len(v_lines) - 1

        # Base score: more lines = better, but diminishing returns
        score = min(num_rows, 40) + min(num_cols, 20) * 2

        # Strong bonus for matching expected column count
        if expected_cols is not None and num_cols == expected_cols:
            score += 50
        elif expected_cols is not None and abs(num_cols - expected_cols) <= 1:
            score += 20

        # Bonus for even spacing (consistent row heights)
        if num_rows >= 2:
            row_heights = [h_lines[i+1] - h_lines[i] for i in range(num_rows)]
            if row_heights:
                mean_h = np.mean(row_heights)
                if mean_h > 0:
                    std_h = np.std(row_heights)
                    # Lower coefficient of variation = more even = better
                    cv = std_h / mean_h
                    score += max(0, 10 * (1 - cv))

        # Bonus for even column widths
        if num_cols >= 2:
            col_widths = [v_lines[i+1] - v_lines[i] for i in range(num_cols)]
            if col_widths:
                mean_w = np.mean(col_widths)
                if mean_w > 0:
                    std_w = np.std(col_widths)
                    cv = std_w / mean_w
                    score += max(0, 10 * (1 - cv))

        # Penalty for too few rows or cols (likely false positive)
        if num_rows < 3:
            score -= 20
        if num_cols < 3:
            score -= 20

        return score

    def _extract_line_positions(
        self, mask: np.ndarray, direction: str
    ) -> List[int]:
        """
        Extract line positions from a binary mask via pixel projection.
        """
        if direction == "horizontal":
            projection = np.sum(mask, axis=1)
        else:
            projection = np.sum(mask, axis=0)

        max_val = np.max(projection)
        if max_val == 0:
            return []

        # Use 20% of max as threshold (lowered from 30% for better sensitivity)
        threshold = max_val * 0.2
        positions = np.where(projection > threshold)[0]

        return positions.tolist()

    def _cluster_lines(self, positions: List[int]) -> List[int]:
        """
        Cluster nearby line positions and return representative positions.
        Lines within cluster_tolerance pixels of each other are merged.
        """
        if not positions:
            return []

        sorted_pos = sorted(set(positions))
        clusters = []
        current_cluster = [sorted_pos[0]]

        for pos in sorted_pos[1:]:
            if pos - current_cluster[-1] <= self.cluster_tolerance:
                current_cluster.append(pos)
            else:
                clusters.append(int(np.mean(current_cluster)))
                current_cluster = [pos]

        clusters.append(int(np.mean(current_cluster)))
        return clusters


class CellExtractor:
    """
    Extract cell rectangles from grid line intersections.
    """

    def extract_cells(
        self,
        horizontal_lines: List[int],
        vertical_lines: List[int],
    ) -> List[GridCell]:
        """
        Compute cell rectangles from line intersections.
        """
        cells = []
        for r in range(len(horizontal_lines) - 1):
            for c in range(len(vertical_lines) - 1):
                y1 = horizontal_lines[r]
                y2 = horizontal_lines[r + 1]
                x1 = vertical_lines[c]
                x2 = vertical_lines[c + 1]
                cells.append(GridCell(
                    row=r,
                    col=c,
                    x=x1,
                    y=y1,
                    width=x2 - x1,
                    height=y2 - y1,
                ))
        return cells


class CellOCR:
    """
    OCR individual cells from cropped image regions.
    """

    def __init__(self, language: str = "eng", padding: int = 4):
        self.language = language
        self.padding = padding

    def ocr_cells(
        self, image: np.ndarray, cells: List[GridCell]
    ) -> List[GridCell]:
        """
        OCR each cell by cropping from the page image.
        """
        import pytesseract

        h, w = image.shape[:2]

        for cell in cells:
            # Crop with padding inset (to avoid grid line pixels)
            x1 = max(0, cell.x + self.padding)
            y1 = max(0, cell.y + self.padding)
            x2 = min(w, cell.x + cell.width - self.padding)
            y2 = min(h, cell.y + cell.height - self.padding)

            if x2 <= x1 or y2 <= y1:
                cell.text = ""
                cell.confidence = 0.0
                continue

            cell_img = image[y1:y2, x1:x2]

            # Skip very small cells (likely artifacts)
            if cell_img.shape[0] < 5 or cell_img.shape[1] < 5:
                cell.text = ""
                cell.confidence = 0.0
                continue

            cell.text, cell.confidence = self._ocr_single_cell(cell_img)

        return cells

    def _ocr_single_cell(
        self, cell_image: np.ndarray
    ) -> Tuple[str, float]:
        """
        OCR a single cropped cell image.

        Uses PSM 7 (single text line) for standard cells.
        Falls back to PSM 6 (uniform block) for taller cells.
        """
        import pytesseract

        h, w = cell_image.shape[:2]
        if h > w * 1.5:
            psm = 6  # Tall cell - might have multi-line text
        else:
            psm = 7  # Standard cell - single line

        config = f'--oem 3 --psm {psm} -l {self.language}'

        try:
            data = pytesseract.image_to_data(
                cell_image, config=config,
                output_type=pytesseract.Output.DICT
            )

            words = []
            confidences = []

            for i, text in enumerate(data['text']):
                text = text.strip()
                conf = float(data['conf'][i])
                if text and conf > 0:
                    words.append(text)
                    confidences.append(conf)

            text = ' '.join(words)
            avg_conf = float(np.mean(confidences)) if confidences else 0.0
            return text, avg_conf

        except Exception as e:
            logger.warning(f"Cell OCR failed: {e}")
            return "", 0.0


class GridOCRTableExtractor:
    """
    High-level orchestrator that combines grid detection, cell extraction,
    and cell-level OCR to produce a TableData object from a page image.
    """

    def __init__(
        self,
        language: str = "eng",
        cluster_tolerance: int = 15,
        cell_padding: int = 4,
    ):
        self.detector = GridLineDetector(
            cluster_tolerance=cluster_tolerance,
        )
        self.cell_extractor = CellExtractor()
        self.cell_ocr = CellOCR(language=language, padding=cell_padding)
        self._expected_cols: Optional[int] = None  # Learned from page 1

    def extract_table_from_image(
        self, image: np.ndarray, page_number: int = 1
    ) -> Optional[TableData]:
        """
        Full pipeline: detect grid -> extract cells -> OCR cells -> build TableData.

        Args:
            image: Page image (BGR or grayscale numpy array)
            page_number: Page number for the TableData

        Returns:
            TableData with headers and rows, or None if no grid detected
        """
        # 1. Detect grid lines
        grid = self.detector.detect_grid(image, expected_cols=self._expected_cols)
        if not grid.grid_detected:
            return None

        logger.info(
            f"Page {page_number}: Grid detected - "
            f"{grid.num_rows} rows x {grid.num_cols} cols"
        )

        # 2. Extract cell rectangles
        cells = self.cell_extractor.extract_cells(
            grid.horizontal_lines, grid.vertical_lines
        )

        # 3. Prepare grayscale image for OCR
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        # 4. OCR each cell
        cells = self.cell_ocr.ocr_cells(gray, cells)

        # 5. Assemble cells into rows
        all_rows = self._cells_to_rows(cells, grid.num_rows, grid.num_cols)

        if len(all_rows) < 2:
            logger.warning(f"Page {page_number}: Too few rows extracted ({len(all_rows)})")
            return None

        # 6. Identify headers and data rows
        from .table_parser import OCRTableParser
        parser = OCRTableParser()
        headers, data_rows = parser._identify_headers_and_data(all_rows)

        if not headers:
            headers = all_rows[0]
            data_rows = all_rows[1:]

        # 7. Correct OCR errors in data rows
        corrected_rows = []
        for row in data_rows:
            corrected_rows.append(parser._correct_ocr_errors(row, headers))

        # Remember column count for subsequent pages
        self._expected_cols = grid.num_cols

        logger.info(
            f"Page {page_number}: Grid OCR extracted "
            f"{len(headers)} headers, {len(corrected_rows)} data rows"
        )

        return TableData(
            headers=headers,
            rows=corrected_rows,
            page_number=page_number,
        )

    def extract_data_only(
        self,
        image: np.ndarray,
        expected_headers: List[str],
        page_number: int = 1,
    ) -> Optional[TableData]:
        """
        Extract only data rows (skip header rows) for subsequent pages.

        Args:
            image: Page image (BGR or grayscale numpy array)
            expected_headers: Headers from first page
            page_number: Page number

        Returns:
            TableData with only data rows, or None if extraction fails
        """
        # 1. Detect grid — pass expected col count for better scoring
        grid = self.detector.detect_grid(image, expected_cols=self._expected_cols)
        if not grid.grid_detected:
            return None

        # Validate: if col count differs from expected, reject and fall back to bbox parsing
        if self._expected_cols is not None:
            if abs(grid.num_cols - self._expected_cols) > 1:
                logger.warning(
                    f"Page {page_number}: Grid col count {grid.num_cols} doesn't match "
                    f"expected {self._expected_cols}, rejecting grid result (fallback to bbox)"
                )
                return None

        cells = self.cell_extractor.extract_cells(
            grid.horizontal_lines, grid.vertical_lines
        )

        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        cells = self.cell_ocr.ocr_cells(gray, cells)

        all_rows = self._cells_to_rows(cells, grid.num_rows, grid.num_cols)

        if not all_rows:
            return None

        # 2. Filter out header rows, keep only data rows
        from .table_parser import OCRTableParser
        parser = OCRTableParser()

        data_rows = []
        for row in all_rows:
            if self._is_header_like_row(row, expected_headers):
                logger.debug(f"Page {page_number}: Skipping header row: {row[:3]}")
                continue
            data_rows.append(row)

        if not data_rows:
            return None

        # 3. Normalize row lengths to match expected headers
        normalized_rows = []
        for row in data_rows:
            corrected = parser._correct_ocr_errors(row, expected_headers)
            if len(corrected) < len(expected_headers):
                corrected.extend([""] * (len(expected_headers) - len(corrected)))
            elif len(corrected) > len(expected_headers):
                corrected = corrected[:len(expected_headers)]
            normalized_rows.append(corrected)

        logger.info(
            f"Page {page_number}: Grid OCR extracted "
            f"{len(normalized_rows)} data rows (headers skipped)"
        )

        return TableData(
            headers=expected_headers,
            rows=normalized_rows,
            page_number=page_number,
        )

    def _cells_to_rows(
        self,
        cells: List[GridCell],
        num_rows: int,
        num_cols: int,
    ) -> List[List[str]]:
        """
        Convert flat list of cells into a 2D row structure.
        """
        rows_dict = {}
        for cell in cells:
            if cell.row not in rows_dict:
                rows_dict[cell.row] = {}
            rows_dict[cell.row][cell.col] = cell.text

        all_rows = []
        for r in range(num_rows):
            row = []
            for c in range(num_cols):
                row.append(rows_dict.get(r, {}).get(c, ""))
            all_rows.append(row)

        return all_rows

    def _is_header_like_row(
        self, row: List[str], expected_headers: List[str]
    ) -> bool:
        """
        Check if a row looks like a header row.
        """
        if not row:
            return False

        # If first cell is numeric, it's likely a data row
        first_cell = str(row[0]).strip() if row[0] else ""
        if first_cell and first_cell.isdigit():
            return False

        # Check for header keywords
        row_text = " ".join(str(cell) for cell in row).upper()
        header_keywords = [
            "PARTY ABBREVIATION",
            "NO. OF VALID VOTES",
            "NO OF VALID VOTES",
            "VALID VOTES",
            "POLLING STATION",
            "SL. NO",
            "SL.NO",
            "SERIAL NUMBER",
            "S.NO",
            "CANDIDATE",
            "NAME",
        ]

        if any(keyword in row_text for keyword in header_keywords):
            return True

        # Check similarity to expected headers
        if expected_headers:
            row_values = [str(cell).strip().lower() for cell in row[:len(expected_headers)]]
            header_values = [str(h).strip().lower() for h in expected_headers]

            matches = sum(
                1 for r_val, h_val in zip(row_values, header_values)
                if r_val and h_val and r_val == h_val
            )

            if len(expected_headers) > 0 and matches > len(expected_headers) * 0.4:
                return True

        # Check if row has mostly text (not numbers) - typical of headers
        non_empty = [str(cell).strip() for cell in row if cell and str(cell).strip()]
        if non_empty:
            numeric_count = sum(
                1 for cell in non_empty
                if cell.replace(",", "").replace(".", "").replace(" ", "").isdigit()
            )
            text_count = len(non_empty) - numeric_count

            if len(non_empty) > 0 and text_count / len(non_empty) >= 0.7:
                return True

        return False
