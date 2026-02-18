"""
Analyze a complex OCR / image-based election PDF with the current pipeline.

Run from backend/ with:
  python analyze_complex_ocr_pdf.py <path_to_pdf>
  python analyze_complex_ocr_pdf.py ../path/to/AC215_Tirichendur.pdf

Logs: PDF type detection, extraction method, column/row counts, validation report,
and failure-mode hints (grid not found, column mismatch, etc.).
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

# Run from backend/ so app is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.pdf_processor import PDFProcessor
from app.pdf_detector import PDFTypeDetector

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _summarize_table(table):
    """Return a small dict for one TableData."""
    return {
        "page_number": getattr(table, "page_number", None),
        "headers_count": len(table.headers) if table.headers else 0,
        "rows_count": len(table.rows) if table.rows else 0,
        "extraction_method": getattr(table, "extraction_method", ""),
        "confidence_score": getattr(table, "confidence_score", None),
        "first_header_sample": (table.headers[:5] if table.headers else []),
    }


async def analyze_pdf(pdf_path: str, output_json_path: str | None = None) -> dict:
    """
    Run extraction with force_ocr=True and collect analysis summary.

    Returns a dict with detection, extraction method, table shape, validation, and failure hints.
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    summary = {
        "pdf_path": str(path.resolve()),
        "pdf_name": path.name,
        "detection": None,
        "extraction_method_used": None,
        "tables_before_merge": [],
        "merged_table": None,
        "validation": None,
        "failure_mode_hints": [],
    }

    # 1) Detection (without force_ocr to see what auto-detect would do)
    detector = PDFTypeDetector()
    detection = detector.detect(str(path))
    summary["detection"] = {
        "pdf_type": detection.pdf_type.value if hasattr(detection.pdf_type, "value") else str(detection.pdf_type),
        "confidence": getattr(detection, "confidence", None),
        "image_pages": getattr(detection, "image_pages", None),
        "text_pages": getattr(detection, "text_pages", None),
    }
    logger.info(
        "PDF type: %s (confidence=%.2f)",
        summary["detection"]["pdf_type"],
        summary["detection"]["confidence"] or 0,
    )

    # 2) Extract with force_ocr=True so we always use OCR path
    processor = PDFProcessor(str(path), force_ocr=True, auto_detect=True)

    def progress_cb(progress: int, message: str):
        logger.info("  [%d%%] %s", progress, message)

    result = await processor.extract_tables(progress_callback=progress_cb, validate=True)
    summary["extraction_method_used"] = (
        result.tables[0].extraction_method if result.tables else None
    )

    # 3) Table summary (after merge we have a single table)
    for t in result.tables:
        summary["tables_before_merge"].append(_summarize_table(t))
    if result.tables:
        merged = result.tables[0]
        summary["merged_table"] = {
            "headers_count": len(merged.headers),
            "rows_count": len(merged.rows),
            "headers_sample": merged.headers[:8] if merged.headers else [],
            "extraction_method": getattr(merged, "extraction_method", ""),
            "confidence_score": getattr(merged, "confidence_score", None),
        }
        logger.info(
            "Merged table: %d columns, %d rows (method=%s)",
            summary["merged_table"]["headers_count"],
            summary["merged_table"]["rows_count"],
            summary["merged_table"]["extraction_method"],
        )

    # 4) Validation report
    if processor.validation_report:
        vr = processor.validation_report
        issues_list = getattr(vr, "issues", []) or []
        summary["validation"] = {
            "passed": getattr(vr, "is_valid", None),
            "confidence": getattr(vr, "confidence_score", None),
            "issues_count": len(issues_list),
            "issues_sample": [
                i.to_human_readable() if hasattr(i, "to_human_readable") else getattr(i, "message", str(i))
                for i in issues_list[:10]
            ],
        }
        logger.info(
            "Validation: passed=%s, confidence=%.2f, issues=%d",
            summary["validation"]["passed"],
            summary["validation"]["confidence"] or 0,
            summary["validation"]["issues_count"],
        )

    # 5) Failure-mode hints
    if result.tables:
        t = result.tables[0]
        ncols = len(t.headers) if t.headers else 0
        if ncols < 3:
            summary["failure_mode_hints"].append(
                "Very few columns (possible grid not found or header row misdetected)."
            )
        if processor.validation_report and not getattr(processor.validation_report, "is_valid", True):
            summary["failure_mode_hints"].append(
                "Validation failed or low confidence; check for OCR errors or column drift."
            )
        if (getattr(t, "extraction_method", "") or "").lower() == "ocr":
            summary["failure_mode_hints"].append(
                "OCR path was used; if grid was not detected, bbox fallback may have column drift."
            )
    else:
        summary["failure_mode_hints"].append("No tables extracted (grid and bbox fallback both failed).")

    if output_json_path:
        out = Path(output_json_path)
        out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        logger.info("Wrote analysis summary to %s", out)

    return summary


def main():
    if len(sys.argv) < 2:
        print("Usage: python analyze_complex_ocr_pdf.py <path_to_pdf> [output.json]")
        print("Example: python analyze_complex_ocr_pdf.py ../examples/AC215_sample.pdf")
        sys.exit(1)
    pdf_path = sys.argv[1]
    output_json = sys.argv[2] if len(sys.argv) > 2 else None
    summary = asyncio.run(analyze_pdf(pdf_path, output_json))
    print("\n--- Summary ---")
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
