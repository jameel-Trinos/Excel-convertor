#!/usr/bin/env python3
"""Diagnostic script to check PDF extraction."""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

import pdfplumber


def diagnose_pdf(pdf_path: str):
    """Diagnose PDF extraction issues."""
    print(f"\n{'='*60}")
    print(f"DIAGNOSING: {pdf_path}")
    print(f"{'='*60}\n")

    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        print(f"📄 Total pages: {total_pages}\n")

        total_rows = 0
        for page_num, page in enumerate(pdf.pages, 1):
            print(f"\n--- Page {page_num} ---")

            # Try different extraction strategies
            strategies = [
                ("default", {}),
                ("lines_strict", {
                    "vertical_strategy": "lines_strict",
                    "horizontal_strategy": "lines_strict",
                }),
                ("text", {
                    "vertical_strategy": "text",
                    "horizontal_strategy": "text",
                }),
            ]

            for name, settings in strategies:
                tables = page.extract_tables(settings) if settings else page.extract_tables()

                if tables:
                    for t_idx, table in enumerate(tables):
                        if table and len(table) > 1:
                            rows = len(table) - 1  # Exclude header
                            total_rows += rows
                            print(f"  [{name}] Table {t_idx + 1}: {len(table[0])} cols, {len(table)} rows (header + {rows} data)")
                            print(f"    First row: {table[0][:3]}...")  # First 3 columns
                            if len(table) > 1:
                                print(f"    Data row 1: {table[1][:3]}...")
                            break  # Use first successful strategy
                    break  # Found tables with this strategy
            else:
                print(f"  No tables found on page {page_num}")

    print(f"\n{'='*60}")
    print(f"📊 TOTAL ROWS EXTRACTED: {total_rows}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Find most recent PDF in uploads
        uploads_dir = Path("backend/uploads")
        if uploads_dir.exists():
            pdfs = list(uploads_dir.glob("*.pdf"))
            if pdfs:
                # Sort by modification time
                pdfs.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                pdf_path = str(pdfs[0])
                print(f"Using most recent upload: {pdf_path}")
            else:
                print("Usage: python diagnose_pdf.py <path_to_pdf>")
                print("Or upload a PDF first.")
                sys.exit(1)
        else:
            print("Usage: python diagnose_pdf.py <path_to_pdf>")
            sys.exit(1)
    else:
        pdf_path = sys.argv[1]

    diagnose_pdf(pdf_path)
