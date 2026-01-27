"""
Example usage of OCR-enabled PDF to Excel conversion system.

This script demonstrates:
1. Text-based PDF extraction (pdfplumber)
2. Image-based PDF extraction (OCR)
3. Automatic detection and fallback
4. Configuration options
"""

import asyncio
import logging
from pathlib import Path

from app.pdf_processor import PDFProcessor
from app.pdf_detector import PDFTypeDetector
from app.ocr_processor import OCRProcessor, OCRConfig
from app.data_validator import ExtractionValidator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def example_text_based_pdf(pdf_path: str):
    """
    Example 1: Process a text-based PDF using pdfplumber.
    
    This is the standard path for PDFs with extractable text.
    """
    print("\n" + "="*60)
    print("EXAMPLE 1: Text-based PDF (pdfplumber)")
    print("="*60)
    
    processor = PDFProcessor(pdf_path, force_ocr=False, auto_detect=True)
    
    def progress_callback(progress: int, message: str):
        print(f"  Progress: {progress}% - {message}")
    
    # Extract tables
    result = await processor.extract_tables(progress_callback=progress_callback)
    
    # Display results
    print(f"\nExtraction Summary:")
    print(f"  Method: {result.tables[0].extraction_method if result.tables else 'N/A'}")
    print(f"  Confidence: {result.tables[0].confidence_score:.2%}" if result.tables else "N/A")
    print(f"  Tables found: {len(result.tables)}")
    
    if result.tables:
        table = result.tables[0]
        print(f"  Headers: {len(table.headers)}")
        print(f"  Rows: {len(table.rows)}")
        print(f"\n  First 3 rows:")
        for i, row in enumerate(table.rows[:3], 1):
            print(f"    Row {i}: {row[:5]}...")  # Show first 5 columns
    
    return result


async def example_ocr_pdf(pdf_path: str):
    """
    Example 2: Process an image-based/scanned PDF using OCR.
    
    This path is used for scanned documents like election Form 20 PDFs.
    """
    print("\n" + "="*60)
    print("EXAMPLE 2: Image-based PDF (OCR)")
    print("="*60)
    
    # Configure OCR with custom settings
    ocr_config = OCRConfig(
        dpi=300,                    # High resolution for better accuracy
        denoise=True,               # Remove noise from scanned images
        deskew=True,                # Correct skewed text
        contrast_enhance=True,     # Improve contrast
        language="eng",             # English language
        psm=6,                      # Page segmentation mode (uniform block)
        min_confidence=60.0,        # Minimum OCR confidence threshold
        use_easyocr_fallback=True   # Use EasyOCR if Tesseract fails
    )
    
    processor = PDFProcessor(pdf_path, force_ocr=True, auto_detect=False)
    
    def progress_callback(progress: int, message: str):
        print(f"  Progress: {progress}% - {message}")
    
    # Extract tables
    result = await processor.extract_tables(progress_callback=progress_callback)
    
    # Display results
    print(f"\nExtraction Summary:")
    print(f"  Method: {result.tables[0].extraction_method if result.tables else 'N/A'}")
    print(f"  Confidence: {result.tables[0].confidence_score:.2%}" if result.tables else "N/A")
    print(f"  Tables found: {len(result.tables)}")
    
    if result.tables:
        table = result.tables[0]
        print(f"  Headers: {len(table.headers)}")
        print(f"  Rows: {len(table.rows)}")
        print(f"\n  First 3 rows:")
        for i, row in enumerate(table.rows[:3], 1):
            print(f"    Row {i}: {row[:5]}...")  # Show first 5 columns
    
    return result


async def example_auto_detect(pdf_path: str):
    """
    Example 3: Automatic detection and appropriate extraction method.
    
    The system automatically detects PDF type and uses the best method.
    """
    print("\n" + "="*60)
    print("EXAMPLE 3: Automatic Detection")
    print("="*60)
    
    # First, detect PDF type
    detector = PDFTypeDetector()
    detection = detector.detect(pdf_path)
    
    print(f"\nPDF Detection Results:")
    print(f"  Type: {detection.pdf_type.value}")
    print(f"  Confidence: {detection.confidence:.2%}")
    print(f"  Total pages: {detection.total_pages}")
    print(f"  Text pages: {detection.text_pages}/{detection.pages_sampled}")
    print(f"  Image pages: {detection.image_pages}/{detection.pages_sampled}")
    print(f"  Avg text density: {detection.avg_text_density:.0f} chars/page")
    
    # Process with auto-detection
    processor = PDFProcessor(pdf_path, force_ocr=False, auto_detect=True)
    
    def progress_callback(progress: int, message: str):
        print(f"  Progress: {progress}% - {message}")
    
    result = await processor.extract_tables(progress_callback=progress_callback)
    
    # Get validation report
    validator = ExtractionValidator()
    validation = validator.validate(result.tables, result.tables[0].extraction_method if result.tables else "unknown")
    
    print(f"\nValidation Results:")
    print(f"  Quality Grade: {validation.quality_grade}")
    print(f"  Confidence: {validation.confidence_score:.2%}")
    print(f"  Valid: {validation.is_valid}")
    print(f"  Errors: {validation.errors_count}")
    print(f"  Warnings: {validation.warnings_count}")
    
    if validation.issues:
        print(f"\n  Issues found:")
        for issue in validation.issues[:5]:  # Show first 5 issues
            print(f"    [{issue.severity.value}] {issue.message}")
    
    return result, validation


async def example_election_form20(pdf_path: str):
    """
    Example 4: Specific handling for Election Form 20 documents.
    
    This demonstrates the specialized parsing for election result PDFs.
    """
    print("\n" + "="*60)
    print("EXAMPLE 4: Election Form 20 Processing")
    print("="*60)
    
    # Configure OCR specifically for election documents
    ocr_config = OCRConfig(
        dpi=300,
        denoise=True,
        deskew=True,
        contrast_enhance=True,
        language="eng",
        psm=6,  # Uniform block mode works well for tables
        min_confidence=50.0,  # Lower threshold for scanned documents
        use_easyocr_fallback=True
    )
    
    processor = PDFProcessor(pdf_path, force_ocr=False, auto_detect=True)
    
    def progress_callback(progress: int, message: str):
        print(f"  Progress: {progress}% - {message}")
    
    result = await processor.extract_tables(progress_callback=progress_callback)
    
    if result.tables:
        table = result.tables[0]
        print(f"\nElection Form 20 Extraction:")
        print(f"  Method: {table.extraction_method}")
        print(f"  Confidence: {table.confidence_score:.2%}")
        print(f"  Headers ({len(table.headers)}):")
        for i, header in enumerate(table.headers[:10], 1):  # Show first 10
            print(f"    {i}. {header}")
        print(f"  Data rows: {len(table.rows)}")
        print(f"\n  Sample data (first row):")
        if table.rows:
            print(f"    {table.rows[0]}")
    
    return result


def example_ocr_configuration():
    """
    Example 5: Different OCR configuration options.
    
    Shows how to configure OCR for different scenarios.
    """
    print("\n" + "="*60)
    print("EXAMPLE 5: OCR Configuration Options")
    print("="*60)
    
    configs = {
        "High Quality (Slow)": OCRConfig(
            dpi=400,                # Very high resolution
            denoise=True,
            deskew=True,
            contrast_enhance=True,
            binarize=True,          # Convert to black/white
            min_confidence=70.0,    # High confidence threshold
            use_easyocr_fallback=True
        ),
        "Fast (Lower Quality)": OCRConfig(
            dpi=200,                # Lower resolution
            denoise=False,          # Skip denoising
            deskew=False,           # Skip deskewing
            contrast_enhance=False,
            min_confidence=40.0,    # Lower threshold
            use_easyocr_fallback=False
        ),
        "Balanced (Default)": OCRConfig(
            dpi=300,
            denoise=True,
            deskew=True,
            contrast_enhance=True,
            min_confidence=60.0,
            use_easyocr_fallback=True
        ),
        "Election Form 20 Optimized": OCRConfig(
            dpi=300,
            denoise=True,
            deskew=True,
            contrast_enhance=True,
            psm=6,                  # Uniform block (good for tables)
            min_confidence=50.0,     # Lower for scanned docs
            use_easyocr_fallback=True
        )
    }
    
    for name, config in configs.items():
        print(f"\n{name}:")
        print(f"  DPI: {config.dpi}")
        print(f"  Denoise: {config.denoise}")
        print(f"  Deskew: {config.deskew}")
        print(f"  Contrast Enhance: {config.contrast_enhance}")
        print(f"  Min Confidence: {config.min_confidence}%")
        print(f"  EasyOCR Fallback: {config.use_easyocr_fallback}")


async def main():
    """Main function demonstrating all examples."""
    print("\n" + "="*60)
    print("PDF to Excel Converter - OCR Usage Examples")
    print("="*60)
    
    # Example file paths (update these to your actual PDF files)
    text_pdf = "path/to/text_based.pdf"
    scanned_pdf = "path/to/scanned_election_form20.pdf"
    
    # Show configuration options
    example_ocr_configuration()
    
    # Run examples if files exist
    if Path(text_pdf).exists():
        await example_text_based_pdf(text_pdf)
    
    if Path(scanned_pdf).exists():
        await example_ocr_pdf(scanned_pdf)
        await example_election_form20(scanned_pdf)
    
    # Auto-detect example (use any PDF)
    test_pdf = text_pdf if Path(text_pdf).exists() else scanned_pdf
    if Path(test_pdf).exists():
        await example_auto_detect(test_pdf)
    
    print("\n" + "="*60)
    print("Examples complete!")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())




