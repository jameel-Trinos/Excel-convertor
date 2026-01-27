"""PDF Type Detection - Determines if a PDF is text-based or image-based (scanned)."""

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class PDFType(Enum):
    """Type of PDF document."""
    TEXT = "text"
    IMAGE = "image"
    MIXED = "mixed"


@dataclass
class PDFDetectionResult:
    """Result of PDF type detection."""
    pdf_type: PDFType
    confidence: float  # 0.0 to 1.0
    total_pages: int
    pages_sampled: int
    text_pages: int
    image_pages: int
    avg_text_density: float  # Characters per page
    has_embedded_fonts: bool
    detection_method: str
    details: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "type": self.pdf_type.value,
            "confidence": round(self.confidence, 2),
            "total_pages": self.total_pages,
            "pages_sampled": self.pages_sampled,
            "text_pages": self.text_pages,
            "image_pages": self.image_pages,
            "avg_text_density": round(self.avg_text_density, 2),
            "has_embedded_fonts": self.has_embedded_fonts,
            "detection_method": self.detection_method,
            "details": self.details,
        }


class PDFTypeDetector:
    """
    Detect if a PDF contains extractable text or is image-based (scanned).

    Detection Strategy:
    1. Sample pages from the PDF (first, middle, last for multi-page)
    2. Check for extractable text using pdfplumber
    3. Analyze text density (characters per page)
    4. Check for embedded fonts
    5. Analyze image coverage on pages

    A PDF is considered:
    - TEXT: >80% of sampled pages have substantial extractable text
    - IMAGE: <20% of sampled pages have extractable text
    - MIXED: Between 20-80% of pages have extractable text
    """

    # Minimum characters per page to consider it "text-based"
    MIN_TEXT_DENSITY = 100

    # Minimum percentage of text pages to classify as TEXT type
    TEXT_THRESHOLD = 0.8

    # Maximum percentage of text pages to classify as IMAGE type
    IMAGE_THRESHOLD = 0.2

    # Maximum pages to sample for large documents
    MAX_SAMPLE_PAGES = 5

    def __init__(self):
        """Initialize the detector."""
        pass

    def detect(self, pdf_path: str) -> PDFDetectionResult:
        """
        Detect if PDF is text-based or image-based.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            PDFDetectionResult with detection details
        """
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        try:
            import pdfplumber
        except ImportError:
            raise ImportError("pdfplumber is required for PDF detection")

        logger.info(f"Detecting PDF type for: {path.name}")

        text_pages = 0
        image_pages = 0
        total_text_chars = 0
        has_embedded_fonts = False
        sampled_pages = []

        with pdfplumber.open(str(path)) as pdf:
            total_pages = len(pdf.pages)

            # Determine which pages to sample
            sample_indices = self._get_sample_indices(total_pages)
            pages_sampled = len(sample_indices)

            for page_idx in sample_indices:
                page = pdf.pages[page_idx]
                sampled_pages.append(page_idx + 1)  # 1-indexed for logging

                # Extract text from the page
                text = page.extract_text() or ""
                char_count = len(text.strip())
                total_text_chars += char_count

                # Check for embedded fonts (indicates text-based PDF)
                if page.chars:
                    has_embedded_fonts = True
                    for char in page.chars[:10]:  # Sample first 10 chars
                        if char.get("fontname"):
                            has_embedded_fonts = True
                            break

                # Analyze page content
                page_has_text = char_count >= self.MIN_TEXT_DENSITY

                # Check for large images (potential scanned content)
                images = page.images
                page_width = page.width
                page_height = page.height
                page_area = page_width * page_height

                # Calculate total image coverage
                image_coverage = 0
                for img in images:
                    img_width = img.get("width", 0) or img.get("x1", 0) - img.get("x0", 0)
                    img_height = img.get("height", 0) or img.get("top", 0) - img.get("bottom", 0)
                    img_area = abs(img_width * img_height)
                    image_coverage += img_area / page_area if page_area > 0 else 0

                # Determine if page is text or image based
                if page_has_text and (image_coverage < 0.7 or char_count > 500):
                    text_pages += 1
                    logger.debug(f"Page {page_idx + 1}: TEXT (chars={char_count}, img_coverage={image_coverage:.2f})")
                else:
                    image_pages += 1
                    logger.debug(f"Page {page_idx + 1}: IMAGE (chars={char_count}, img_coverage={image_coverage:.2f})")

        # Calculate metrics
        avg_text_density = total_text_chars / pages_sampled if pages_sampled > 0 else 0
        text_ratio = text_pages / pages_sampled if pages_sampled > 0 else 0

        # Determine PDF type
        if text_ratio >= self.TEXT_THRESHOLD:
            pdf_type = PDFType.TEXT
            confidence = text_ratio
            detection_method = "text_extraction"
        elif text_ratio <= self.IMAGE_THRESHOLD:
            pdf_type = PDFType.IMAGE
            confidence = 1.0 - text_ratio
            detection_method = "image_analysis"
        else:
            pdf_type = PDFType.MIXED
            confidence = 0.5 + abs(text_ratio - 0.5)
            detection_method = "mixed_analysis"

        # Adjust confidence based on additional signals
        if has_embedded_fonts and pdf_type == PDFType.IMAGE:
            # Unusual: has fonts but classified as image
            confidence *= 0.8

        if avg_text_density > 1000 and pdf_type == PDFType.IMAGE:
            # Unusual: high text density but classified as image
            confidence *= 0.7

        result = PDFDetectionResult(
            pdf_type=pdf_type,
            confidence=min(confidence, 1.0),
            total_pages=total_pages,
            pages_sampled=pages_sampled,
            text_pages=text_pages,
            image_pages=image_pages,
            avg_text_density=avg_text_density,
            has_embedded_fonts=has_embedded_fonts,
            detection_method=detection_method,
            details=f"Sampled pages: {sampled_pages}"
        )

        logger.info(
            f"PDF Detection: type={pdf_type.value}, confidence={confidence:.2f}, "
            f"text_pages={text_pages}/{pages_sampled}, avg_density={avg_text_density:.0f}"
        )

        return result

    def _get_sample_indices(self, total_pages: int) -> list[int]:
        """
        Get indices of pages to sample for detection.

        For small PDFs: sample all pages
        For large PDFs: sample first, middle, and last pages

        Args:
            total_pages: Total number of pages in PDF

        Returns:
            List of page indices (0-indexed)
        """
        if total_pages <= self.MAX_SAMPLE_PAGES:
            return list(range(total_pages))

        # Sample first, some middle pages, and last
        indices = [0]  # First page

        # Add evenly distributed middle pages
        step = total_pages // (self.MAX_SAMPLE_PAGES - 1)
        for i in range(1, self.MAX_SAMPLE_PAGES - 1):
            idx = i * step
            if idx not in indices and idx < total_pages - 1:
                indices.append(idx)

        # Last page
        if total_pages - 1 not in indices:
            indices.append(total_pages - 1)

        return sorted(indices)

    def is_scanned_pdf(self, pdf_path: str) -> bool:
        """
        Quick check if PDF is scanned/image-based.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            True if PDF appears to be scanned/image-based
        """
        result = self.detect(pdf_path)
        return result.pdf_type == PDFType.IMAGE

    def get_extraction_recommendation(self, pdf_path: str) -> dict:
        """
        Get recommended extraction method for the PDF.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Dictionary with recommendation details
        """
        result = self.detect(pdf_path)

        recommendations = {
            PDFType.TEXT: {
                "method": "pdfplumber",
                "fallback": "camelot",
                "reason": "PDF contains extractable text, use text-based extraction",
                "ocr_needed": False,
            },
            PDFType.IMAGE: {
                "method": "ocr",
                "fallback": "ocr_enhanced",
                "reason": "PDF appears to be scanned, OCR required",
                "ocr_needed": True,
            },
            PDFType.MIXED: {
                "method": "hybrid",
                "fallback": "ocr",
                "reason": "PDF has mixed content, hybrid extraction recommended",
                "ocr_needed": True,
            },
        }

        rec = recommendations[result.pdf_type]
        return {
            "detection": result.to_dict(),
            "recommendation": rec,
        }
