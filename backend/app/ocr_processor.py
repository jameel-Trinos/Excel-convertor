"""OCR Processor - Extract tables from image-based/scanned PDFs using OCR."""

import logging
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import numpy as np

from .models import ExtractionResult, TableData

logger = logging.getLogger(__name__)


@dataclass
class OCRConfig:
    """Configuration for OCR processing."""
    # Image preprocessing
    dpi: int = 300  # Resolution for PDF to image conversion
    denoise: bool = True
    deskew: bool = True
    contrast_enhance: bool = True
    binarize: bool = False  # Convert to black/white

    # OCR engine settings
    language: str = "eng"  # Tesseract language code
    psm: int = 6  # Page segmentation mode (6 = uniform block of text)
    oem: int = 3  # OCR Engine mode (3 = default, based on what's available)

    # Table detection
    use_table_detection: bool = True
    min_table_rows: int = 3
    min_table_cols: int = 2

    # Quality thresholds
    min_confidence: float = 60.0  # Minimum confidence for OCR results

    # Fallback
    use_easyocr_fallback: bool = True


@dataclass
class OCRPageResult:
    """Result of OCR on a single page."""
    page_number: int
    raw_text: str
    confidence: float  # 0-100
    word_confidences: List[float]
    bounding_boxes: List[dict]  # List of {text, x, y, width, height, confidence}
    preprocessing_applied: List[str]
    ocr_engine: str


class OCRProcessor:
    """
    Extract tables from image-based PDFs using OCR.

    Processing Pipeline:
    1. Convert PDF pages to images (pdf2image)
    2. Preprocess images (denoise, deskew, contrast adjustment)
    3. Apply OCR (pytesseract primary, EasyOCR fallback)
    4. Parse OCR output into table structure
    5. Handle election Form 20 specific format
    6. Return TableData objects matching pdfplumber output format
    """

    def __init__(self, pdf_path: str, config: Optional[OCRConfig] = None):
        """
        Initialize OCR processor.

        Args:
            pdf_path: Path to the PDF file
            config: OCR configuration options
        """
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        self.config = config or OCRConfig()
        self._easyocr_reader = None

    def extract_tables(
        self,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> ExtractionResult:
        """
        Extract tables from all pages using OCR.

        Args:
            progress_callback: Optional callback for progress updates (progress%, message)

        Returns:
            ExtractionResult containing extracted tables
        """
        def update_progress(progress: int, message: str):
            if progress_callback:
                progress_callback(progress, message)

        update_progress(5, "Starting OCR extraction...")

        # Convert PDF to images
        update_progress(10, "Converting PDF pages to images...")
        images = self._pdf_to_images()
        total_pages = len(images)
        logger.info(f"Converted {total_pages} pages to images")

        all_tables: List[TableData] = []
        all_page_texts: List[str] = []
        total_confidence = 0.0
        first_page_headers = None  # Headers extracted from first page only

        for page_idx, image in enumerate(images):
            page_num = page_idx + 1
            progress = int(10 + ((page_idx / total_pages) * 70))
            update_progress(progress, f"Processing page {page_num} of {total_pages} with OCR...")

            # Preprocess the image
            processed_image, preprocessing_steps = self._preprocess_image(image)

            # Perform OCR
            ocr_result = self._perform_ocr(processed_image, page_num, preprocessing_steps)
            all_page_texts.append(ocr_result.raw_text)
            total_confidence += ocr_result.confidence

            # FIRST PAGE: Extract headers and data rows
            if page_num == 1:
                # Parse OCR result into table structure (includes headers)
                table_data = self._parse_ocr_to_table(ocr_result)
                
                if table_data and not table_data.is_empty:
                    # Store headers from first page
                    first_page_headers = table_data.headers
                    logger.info(
                        f"Page 1: Extracted headers: {len(first_page_headers)} columns, "
                        f"{len(table_data.rows)} data rows, confidence={ocr_result.confidence:.1f}%"
                    )
                    all_tables.append(table_data)
                else:
                    logger.warning(f"Page 1: No table data extracted")
            else:
                # SUBSEQUENT PAGES: Extract only data rows (skip headers)
                if first_page_headers is None:
                    logger.warning(f"Page {page_num}: No headers from first page, skipping")
                    continue
                
                # Parse OCR result but extract only data rows
                table_data = self._parse_ocr_data_only(ocr_result, first_page_headers)
                
                if table_data and not table_data.is_empty:
                    all_tables.append(table_data)
                    logger.info(
                        f"Page {page_num}: Extracted {len(table_data.rows)} data rows (headers skipped), "
                        f"confidence={ocr_result.confidence:.1f}%"
                    )
                else:
                    logger.warning(f"Page {page_num}: No data rows extracted")

        # Merge tables from all pages
        update_progress(85, "Merging tables from all pages...")
        merged_table = self._merge_tables(all_tables)

        # Calculate overall confidence
        avg_confidence = total_confidence / total_pages if total_pages > 0 else 0

        # Add OCR metadata to the table
        if merged_table:
            merged_table.extraction_method = "ocr"
            merged_table.confidence_score = avg_confidence / 100.0

        update_progress(100, f"OCR extraction complete (confidence: {avg_confidence:.1f}%)")

        return ExtractionResult(
            tables=[merged_table] if merged_table else [],
            page_texts=all_page_texts,
        )

    def _pdf_to_images(self) -> List[np.ndarray]:
        """
        Convert PDF pages to images.

        Returns:
            List of images as numpy arrays (BGR format)
        """
        try:
            from pdf2image import convert_from_path
        except ImportError:
            raise ImportError(
                "pdf2image is required for OCR. Install with: pip install pdf2image"
            )

        try:
            import cv2
        except ImportError:
            raise ImportError(
                "OpenCV is required for OCR. Install with: pip install opencv-python-headless"
            )

        # Convert PDF to PIL images
        pil_images = convert_from_path(
            str(self.pdf_path),
            dpi=self.config.dpi,
            fmt="png",
        )

        # Convert PIL images to numpy arrays (OpenCV format)
        images = []
        for pil_img in pil_images:
            # Convert PIL to numpy array
            img_array = np.array(pil_img)
            # Convert RGB to BGR (OpenCV format)
            if len(img_array.shape) == 3 and img_array.shape[2] == 3:
                img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            images.append(img_array)

        return images

    def _preprocess_image(self, image: np.ndarray) -> Tuple[np.ndarray, List[str]]:
        """
        Preprocess image to improve OCR accuracy.

        Args:
            image: Input image as numpy array

        Returns:
            Tuple of (processed_image, list_of_preprocessing_steps)
        """
        try:
            import cv2
        except ImportError:
            raise ImportError("OpenCV is required for image preprocessing")

        steps_applied = []
        processed = image.copy()

        # Convert to grayscale if color
        if len(processed.shape) == 3:
            processed = cv2.cvtColor(processed, cv2.COLOR_BGR2GRAY)
            steps_applied.append("grayscale")

        # Denoise
        if self.config.denoise:
            processed = cv2.fastNlMeansDenoising(processed, h=10)
            steps_applied.append("denoise")

        # Deskew
        if self.config.deskew:
            processed, skew_angle = self._deskew_image(processed)
            if abs(skew_angle) > 0.5:
                steps_applied.append(f"deskew({skew_angle:.1f}deg)")

        # Contrast enhancement
        if self.config.contrast_enhance:
            # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            processed = clahe.apply(processed)
            steps_applied.append("contrast_enhance")

        # Binarization (optional)
        if self.config.binarize:
            # Adaptive thresholding for better results on varying backgrounds
            processed = cv2.adaptiveThreshold(
                processed, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                11, 2
            )
            steps_applied.append("binarize")

        return processed, steps_applied

    def _deskew_image(self, image: np.ndarray) -> Tuple[np.ndarray, float]:
        """
        Deskew a rotated image.

        Args:
            image: Grayscale image

        Returns:
            Tuple of (deskewed_image, skew_angle_in_degrees)
        """
        import cv2

        # Detect edges
        edges = cv2.Canny(image, 50, 150, apertureSize=3)

        # Detect lines using Hough transform
        lines = cv2.HoughLinesP(
            edges, 1, np.pi / 180, 100,
            minLineLength=100, maxLineGap=10
        )

        if lines is None or len(lines) == 0:
            return image, 0.0

        # Calculate angles of detected lines
        angles = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            if x2 - x1 != 0:
                angle = np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi
                # Only consider near-horizontal lines
                if abs(angle) < 45:
                    angles.append(angle)

        if not angles:
            return image, 0.0

        # Use median angle to avoid outliers
        skew_angle = np.median(angles)

        # Only deskew if angle is significant
        if abs(skew_angle) < 0.5:
            return image, skew_angle

        # Rotate image to correct skew
        (h, w) = image.shape[:2]
        center = (w // 2, h // 2)
        rotation_matrix = cv2.getRotationMatrix2D(center, skew_angle, 1.0)
        deskewed = cv2.warpAffine(
            image, rotation_matrix, (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE
        )

        return deskewed, skew_angle

    def _perform_ocr(
        self,
        image: np.ndarray,
        page_number: int,
        preprocessing_steps: List[str]
    ) -> OCRPageResult:
        """
        Perform OCR on an image.

        Args:
            image: Preprocessed image
            page_number: Page number (1-indexed)
            preprocessing_steps: List of preprocessing steps applied

        Returns:
            OCRPageResult with extracted text and metadata
        """
        # Try Tesseract first
        try:
            result = self._ocr_with_tesseract(image, page_number, preprocessing_steps)
            if result.confidence >= self.config.min_confidence:
                return result
            logger.warning(
                f"Page {page_number}: Tesseract confidence low ({result.confidence:.1f}%), "
                f"trying fallback..."
            )
        except Exception as e:
            logger.warning(f"Tesseract OCR failed: {e}")
            result = None

        # Fallback to EasyOCR if enabled and Tesseract failed or low confidence
        if self.config.use_easyocr_fallback:
            try:
                easyocr_result = self._ocr_with_easyocr(image, page_number, preprocessing_steps)
                if result is None or easyocr_result.confidence > result.confidence:
                    logger.info(f"Page {page_number}: Using EasyOCR result (confidence: {easyocr_result.confidence:.1f}%)")
                    return easyocr_result
            except Exception as e:
                logger.warning(f"EasyOCR fallback failed: {e}")

        # Return Tesseract result even if low confidence
        if result:
            return result

        # Return empty result if all OCR engines failed
        return OCRPageResult(
            page_number=page_number,
            raw_text="",
            confidence=0.0,
            word_confidences=[],
            bounding_boxes=[],
            preprocessing_applied=preprocessing_steps,
            ocr_engine="failed"
        )

    def _ocr_with_tesseract(
        self,
        image: np.ndarray,
        page_number: int,
        preprocessing_steps: List[str]
    ) -> OCRPageResult:
        """
        Perform OCR using Tesseract.

        Args:
            image: Preprocessed image
            page_number: Page number
            preprocessing_steps: Applied preprocessing steps

        Returns:
            OCRPageResult
        """
        try:
            import pytesseract
            from pytesseract import Output
        except ImportError:
            raise ImportError(
                "pytesseract is required for OCR. Install with: pip install pytesseract"
            )

        # Get detailed OCR data
        custom_config = f'--oem {self.config.oem} --psm {self.config.psm}'

        # Get OCR data with bounding boxes and confidence
        ocr_data = pytesseract.image_to_data(
            image,
            lang=self.config.language,
            config=custom_config,
            output_type=Output.DICT
        )

        # Extract text and confidence
        words = []
        word_confidences = []
        bounding_boxes = []

        n_boxes = len(ocr_data['text'])
        for i in range(n_boxes):
            text = ocr_data['text'][i].strip()
            conf = float(ocr_data['conf'][i])

            if text and conf > 0:
                words.append(text)
                word_confidences.append(conf)
                bounding_boxes.append({
                    'text': text,
                    'x': ocr_data['left'][i],
                    'y': ocr_data['top'][i],
                    'width': ocr_data['width'][i],
                    'height': ocr_data['height'][i],
                    'confidence': conf,
                    'line_num': ocr_data['line_num'][i],
                    'block_num': ocr_data['block_num'][i],
                })

        # Calculate average confidence
        avg_confidence = np.mean(word_confidences) if word_confidences else 0.0

        # Get full text
        raw_text = pytesseract.image_to_string(
            image,
            lang=self.config.language,
            config=custom_config
        )

        return OCRPageResult(
            page_number=page_number,
            raw_text=raw_text,
            confidence=avg_confidence,
            word_confidences=word_confidences,
            bounding_boxes=bounding_boxes,
            preprocessing_applied=preprocessing_steps,
            ocr_engine="tesseract"
        )

    def _ocr_with_easyocr(
        self,
        image: np.ndarray,
        page_number: int,
        preprocessing_steps: List[str]
    ) -> OCRPageResult:
        """
        Perform OCR using EasyOCR (fallback).

        Args:
            image: Preprocessed image
            page_number: Page number
            preprocessing_steps: Applied preprocessing steps

        Returns:
            OCRPageResult
        """
        try:
            import easyocr
        except ImportError:
            raise ImportError(
                "easyocr is required for fallback OCR. Install with: pip install easyocr"
            )

        # Initialize reader (lazy loading)
        if self._easyocr_reader is None:
            self._easyocr_reader = easyocr.Reader(['en'], gpu=False)

        # Perform OCR
        results = self._easyocr_reader.readtext(image)

        # Extract text and confidence
        lines = []
        word_confidences = []
        bounding_boxes = []

        for bbox, text, conf in results:
            if text.strip():
                lines.append(text)
                word_confidences.append(conf * 100)  # Convert to percentage
                bounding_boxes.append({
                    'text': text,
                    'bbox': bbox,
                    'confidence': conf * 100,
                })

        # Calculate average confidence
        avg_confidence = np.mean(word_confidences) if word_confidences else 0.0

        # Reconstruct text
        raw_text = '\n'.join(lines)

        return OCRPageResult(
            page_number=page_number,
            raw_text=raw_text,
            confidence=avg_confidence,
            word_confidences=word_confidences,
            bounding_boxes=bounding_boxes,
            preprocessing_applied=preprocessing_steps,
            ocr_engine="easyocr"
        )

    def _parse_ocr_to_table(self, ocr_result: OCRPageResult) -> Optional[TableData]:
        """
        Parse OCR result into table structure.

        Uses the table_parser module for detailed parsing.

        Args:
            ocr_result: OCR result from a single page

        Returns:
            TableData or None if no table found
        """
        from .table_parser import OCRTableParser

        parser = OCRTableParser()

        # Try election Form 20 format first (primary use case)
        table_data = parser.parse_election_form20(
            ocr_result.raw_text,
            ocr_result.bounding_boxes,
            ocr_result.page_number
        )

        if table_data and not table_data.is_empty:
            return table_data

        # Fallback to generic table parsing
        table_data = parser.parse_generic_table(
            ocr_result.raw_text,
            ocr_result.bounding_boxes,
            ocr_result.page_number
        )

        return table_data

    def _parse_ocr_data_only(
        self, 
        ocr_result: OCRPageResult, 
        expected_headers: List[str]
    ) -> Optional[TableData]:
        """
        Parse OCR result extracting only data rows, skipping headers.
        
        This is used for subsequent pages where headers have already been
        extracted from the first page. It identifies and skips header rows
        that appear on each page.
        
        Args:
            ocr_result: OCR result from a single page
            expected_headers: Headers from first page
            
        Returns:
            TableData with only data rows (headers skipped) or None
        """
        from .table_parser import OCRTableParser

        parser = OCRTableParser()

        # Parse the page to get all rows (including headers)
        # Try election Form 20 format first
        full_table = parser.parse_election_form20(
            ocr_result.raw_text,
            ocr_result.bounding_boxes,
            ocr_result.page_number
        )

        if not full_table or full_table.is_empty:
            # Fallback to generic parsing
            full_table = parser.parse_generic_table(
                ocr_result.raw_text,
                ocr_result.bounding_boxes,
                ocr_result.page_number
            )

        if not full_table or full_table.is_empty:
            return None

        # Extract only data rows, skipping headers
        data_rows = []
        for row in full_table.rows:
            # Skip rows that look like headers
            if self._is_header_row(row, expected_headers):
                logger.debug(f"Page {ocr_result.page_number}: Skipping header row: {row[:3]}")
                continue
            
            # Normalize row length to match expected headers
            normalized_row = row[:]
            if len(normalized_row) < len(expected_headers):
                normalized_row.extend([""] * (len(expected_headers) - len(normalized_row)))
            elif len(normalized_row) > len(expected_headers):
                normalized_row = normalized_row[:len(expected_headers)]
            
            data_rows.append(normalized_row)

        if not data_rows:
            return None

        return TableData(
            headers=expected_headers,
            rows=data_rows,
            page_number=ocr_result.page_number,
        )

    def _is_header_row(self, row: List[str], expected_headers: List[str]) -> bool:
        """
        Check if a row looks like a header row.
        
        Args:
            row: Row to check
            expected_headers: Headers from first page (for comparison)
            
        Returns:
            True if row appears to be a header row
        """
        if not row:
            return False
        
        # Check if first cell is numeric - if so, it's likely a data row
        first_cell = str(row[0]).strip() if row and row[0] else ""
        if first_cell.isdigit():
            return False
        
        # Check if row contains header-like keywords
        row_text = " ".join(str(cell) for cell in row).upper()
        header_keywords = [
            "PARTY ABBREVIATION",
            "NO. OF VALID VOTES",
            "POLLING STATION",
            "SL. NO",
            "SL.NO",
            "SERIAL NUMBER"
        ]
        
        if any(keyword in row_text for keyword in header_keywords):
            return True
        
        # Check if row matches expected headers (similarity check)
        if expected_headers:
            row_values = [str(cell).strip().lower() for cell in row[:len(expected_headers)]]
            header_values = [str(h).strip().lower() for h in expected_headers]
            
            # Count matches
            matches = sum(1 for r, h in zip(row_values, header_values) if r and h and r == h)
            
            # If more than 50% of cells match headers, it's likely a header row
            if matches > len(expected_headers) * 0.5:
                return True
        
        # Check if row has mostly text (not numbers) - typical of headers
        non_empty = [str(cell).strip() for cell in row if cell]
        if non_empty:
            numeric_count = sum(1 for cell in non_empty if cell.isdigit() or (cell.replace(".", "").replace(",", "").isdigit()))
            text_count = len(non_empty) - numeric_count
            
            # If mostly text (at least 70% text), likely a header row
            if len(non_empty) > 0 and text_count / len(non_empty) >= 0.7:
                return True
        
        return False

    def _merge_tables(self, tables: List[TableData]) -> Optional[TableData]:
        """
        Merge tables from multiple pages into a single table.

        Args:
            tables: List of TableData objects

        Returns:
            Merged TableData or None if no tables
        """
        if not tables:
            return None

        if len(tables) == 1:
            return tables[0]

        # Use headers from first non-empty table
        headers = []
        for table in tables:
            if table.headers:
                headers = table.headers
                break

        if not headers:
            logger.warning("No headers found in any table")
            return None

        # Merge all rows
        all_rows = []
        seen_rows = set()  # For deduplication

        for table in tables:
            for row in table.rows:
                # Normalize row length
                normalized_row = row[:]
                if len(normalized_row) < len(headers):
                    normalized_row.extend([""] * (len(headers) - len(normalized_row)))
                elif len(normalized_row) > len(headers):
                    normalized_row = normalized_row[:len(headers)]

                # Deduplicate rows (especially headers that repeat on each page)
                row_key = tuple(str(cell).strip().lower() for cell in normalized_row[:3])
                if row_key not in seen_rows:
                    all_rows.append(normalized_row)
                    seen_rows.add(row_key)

        logger.info(f"Merged {len(tables)} tables: {len(all_rows)} total rows")

        return TableData(
            headers=headers,
            rows=all_rows,
            page_number=1,
        )

    def get_page_count(self) -> int:
        """Get the number of pages in the PDF."""
        try:
            from pdf2image import pdfinfo_from_path
            info = pdfinfo_from_path(str(self.pdf_path))
            return info.get('Pages', 0)
        except Exception:
            # Fallback: convert and count
            images = self._pdf_to_images()
            return len(images)
