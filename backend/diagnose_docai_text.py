"""Diagnostic: Check Document AI raw text quality (not tables)."""

import os
import sys
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
    result = client.process_document(request=request)
    doc = result.document

    print(f"Pages: {len(doc.pages)}")
    print(f"Total text length: {len(doc.text)} chars")
    print()

    # Show raw text per page (first 500 chars each)
    for page_idx, page in enumerate(doc.pages):
        print(f"--- PAGE {page_idx + 1} RAW TEXT (first 800 chars) ---")
        # Get text for this page using layout
        page_text = ""
        if page.layout and page.layout.text_anchor and page.layout.text_anchor.text_segments:
            for seg in page.layout.text_anchor.text_segments:
                start = int(seg.start_index) if seg.start_index else 0
                end = int(seg.end_index) if seg.end_index else len(doc.text)
                page_text += doc.text[start:end]

        if page_text:
            print(page_text[:800])
        else:
            print("(no text extracted for this page)")
        print()

        if page_idx >= 2:  # Only show first 3 pages
            print(f"... ({len(doc.pages) - 3} more pages)")
            break


if __name__ == "__main__":
    pdf = sys.argv[1] if len(sys.argv) > 1 else "uploads/3_Tiruttani.pdf"
    diagnose(pdf)
