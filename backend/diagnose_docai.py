"""Diagnostic: Dump raw Document AI output to understand table structure."""

import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv()

from google.cloud import documentai_v1 as documentai
from google.oauth2 import service_account


def diagnose(pdf_path: str):
    creds = service_account.Credentials.from_service_account_file(
        os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "./google-cloud-credentials.json")
    )
    client = documentai.DocumentProcessorServiceClient(credentials=creds)

    project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
    processor_id = os.getenv("GOOGLE_DOCUMENT_AI_PROCESSOR_ID")
    location = os.getenv("GOOGLE_DOCUMENT_AI_LOCATION", "us")

    processor_name = f"projects/{project_id}/locations/{location}/processors/{processor_id}"

    with open(pdf_path, "rb") as f:
        content = f.read()

    request = documentai.ProcessRequest(
        name=processor_name,
        raw_document=documentai.RawDocument(content=content, mime_type="application/pdf")
    )

    print(f"Processing: {pdf_path}")
    print(f"Processor: {processor_name}")
    print("Calling Document AI...")
    result = client.process_document(request=request)
    doc = result.document

    print(f"\n{'='*70}")
    print(f"DOCUMENT: {len(doc.pages)} pages, {len(doc.text)} chars of text")
    print(f"{'='*70}")

    for page_idx, page in enumerate(doc.pages):
        print(f"\n--- PAGE {page_idx + 1} ---")
        print(f"  Tables found: {len(page.tables)}")

        for t_idx, table in enumerate(page.tables):
            print(f"\n  TABLE {t_idx + 1}:")
            print(f"    Header rows: {len(table.header_rows)}")
            print(f"    Body rows:   {len(table.body_rows)}")

            # Print header rows
            for h_idx, hrow in enumerate(table.header_rows):
                cells = []
                for cell in hrow.cells:
                    text = get_text(cell, doc.text).replace("\n", " ").strip()
                    span = ""
                    if cell.row_span > 1 or cell.col_span > 1:
                        span = f" [span={cell.row_span}x{cell.col_span}]"
                    cells.append(f"'{text}'{span}")
                print(f"    HEADER ROW {h_idx + 1} ({len(hrow.cells)} cells): {' | '.join(cells)}")

            # Print first 5 body rows
            for b_idx, brow in enumerate(table.body_rows[:5]):
                cells = []
                for cell in brow.cells:
                    text = get_text(cell, doc.text).replace("\n", " ").strip()
                    span = ""
                    if cell.row_span > 1 or cell.col_span > 1:
                        span = f" [span={cell.row_span}x{cell.col_span}]"
                    cells.append(f"'{text}'{span}")
                print(f"    BODY ROW {b_idx + 1} ({len(brow.cells)} cells): {' | '.join(cells)}")

            if len(table.body_rows) > 5:
                print(f"    ... ({len(table.body_rows) - 5} more body rows)")

    # Also dump first 2000 chars of raw text
    print(f"\n{'='*70}")
    print("RAW TEXT (first 2000 chars):")
    print(f"{'='*70}")
    print(doc.text[:2000])


def get_text(cell, full_text):
    segments = []
    if cell.layout.text_anchor.text_segments:
        for seg in cell.layout.text_anchor.text_segments:
            start = int(seg.start_index) if seg.start_index else 0
            end = int(seg.end_index) if seg.end_index else len(full_text)
            segments.append(full_text[start:end])
    return " ".join(segments).strip()


if __name__ == "__main__":
    pdf = sys.argv[1] if len(sys.argv) > 1 else "uploads/3_Tiruttani.pdf"
    diagnose(pdf)
