"""Convert constituency PDF to Excel using text-based parser.

This script uses the constituency text parser to extract structured entries
from PDFs with the format:
[Serial Number] [ID Number] [Text content]
[1] -Sub-area 1, [2] -Sub-area 2, etc.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.constituency_processor import ConstituencyProcessor
from app.constituency_excel_creator import ConstituencyExcelCreator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def convert_pdf_to_excel(pdf_path: str, output_dir: str = None):
    """
    Convert constituency PDF to Excel format.
    
    Args:
        pdf_path: Path to input PDF file
        output_dir: Output directory (default: backend/outputs)
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    
    if output_dir is None:
        output_dir = Path(__file__).parent / "backend" / "outputs"
    else:
        output_dir = Path(output_dir)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate output filename
    output_filename = pdf_path.stem + "_converted.xlsx"
    output_path = output_dir / output_filename
    
    logger.info(f"Converting PDF: {pdf_path}")
    logger.info(f"Output will be saved to: {output_path}")
    
    def progress_callback(progress: int, message: str):
        logger.info(f"Progress: {progress}% - {message}")
    
    # Initialize processor
    processor = ConstituencyProcessor(str(pdf_path), force_ocr=False, auto_detect=True)
    
    # Extract using text parser
    logger.info("Extracting data using text-based parser...")
    result = await processor.extract_tables(
        progress_callback=progress_callback,
        validate=True,
        use_text_parser=True  # Use text-based parser
    )
    
    if not result.tables or all(t.is_empty for t in result.tables):
        raise ValueError("No data extracted from PDF")
    
    logger.info(f"Extracted {len(result.tables)} table(s)")
    for table in result.tables:
        logger.info(f"  - {len(table.rows)} rows, {len(table.headers)} columns")
    
    # Create Excel file
    logger.info("Creating Excel file...")
    creator = ConstituencyExcelCreator()
    output_file = creator.create_from_tables(
        tables=result.tables,
        output_path=str(output_path),
        source_filename=pdf_path.name,
        page_texts=result.page_texts
    )
    
    logger.info(f"✓ Excel file created successfully: {output_file}")
    return output_file


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python convert_constituency_pdf.py <pdf_path> [output_dir]")
        print("\nExample:")
        print("  python convert_constituency_pdf.py AC001.pdf")
        print("  python convert_constituency_pdf.py AC001.pdf ./outputs")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        output_file = asyncio.run(convert_pdf_to_excel(pdf_path, output_dir))
        print(f"\n✓ Conversion complete!")
        print(f"Output file: {output_file}")
    except Exception as e:
        logger.error(f"Conversion failed: {e}", exc_info=True)
        sys.exit(1)




