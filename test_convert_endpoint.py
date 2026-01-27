#!/usr/bin/env python3
"""
Test script for the /convert endpoint

This demonstrates how to use the new POST /convert endpoint
to convert PDF files to Excel with Claude AI integration.

Usage:
    python test_convert_endpoint.py <path_to_pdf>

Example:
    python test_convert_endpoint.py sample.pdf
"""

import sys
import requests
import json
from pathlib import Path


def test_convert_endpoint(pdf_path: str, api_url: str = "http://localhost:8000"):
    """
    Test the /convert endpoint with a PDF file.

    Args:
        pdf_path: Path to the PDF file to convert
        api_url: Base URL of the API (default: http://localhost:8000)
    """
    pdf_file = Path(pdf_path)

    if not pdf_file.exists():
        print(f"Error: File not found: {pdf_path}")
        return

    if not pdf_file.suffix.lower() == '.pdf':
        print(f"Error: File must be a PDF: {pdf_path}")
        return

    print(f"Converting PDF: {pdf_file.name}")
    print(f"API endpoint: {api_url}/convert")
    print("-" * 60)

    # Prepare the file for upload
    with open(pdf_file, 'rb') as f:
        files = {'file': (pdf_file.name, f, 'application/pdf')}

        # Make the request
        try:
            response = requests.post(f"{api_url}/convert", files=files, timeout=300)

            if response.status_code == 200:
                data = response.json()

                print("✓ Conversion successful!")
                print()
                print(f"Excel file path: {data['excel_file_path']}")
                print(f"Document title: {data.get('document_title', 'N/A')}")
                print(f"Total rows: {data['total_rows']}")
                print(f"Total columns: {data['total_columns']}")
                print()
                print("Column names:")
                for i, col in enumerate(data['column_names'], 1):
                    print(f"  {i}. {col}")
                print()

                if data.get('party_columns'):
                    print("Party vote columns identified:")
                    for col in data['party_columns']:
                        print(f"  - {col}")
                    print()

                if data.get('ai_metadata'):
                    ai = data['ai_metadata']
                    print("AI Processing:")
                    print(f"  Provider: {ai.get('ai_provider', 'N/A')}")
                    print(f"  Model: {ai.get('ai_model_used', 'N/A')}")
                    print(f"  Heading detected: {ai.get('heading_detected', False)}")
                    print(f"  Columns standardized: {ai.get('columns_standardized', False)}")
                    print()

                print("-" * 60)
                print("Full response:")
                print(json.dumps(data, indent=2))

            else:
                print(f"✗ Error: HTTP {response.status_code}")
                print(response.text)

        except requests.exceptions.ConnectionError:
            print(f"✗ Error: Cannot connect to {api_url}")
            print("Make sure the backend server is running:")
            print("  cd backend && uvicorn app.main:app --reload --port 8000")
        except requests.exceptions.Timeout:
            print("✗ Error: Request timeout (>5 minutes)")
            print("The PDF might be too large or complex")
        except Exception as e:
            print(f"✗ Error: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_convert_endpoint.py <path_to_pdf>")
        print()
        print("Example:")
        print("  python test_convert_endpoint.py sample.pdf")
        sys.exit(1)

    pdf_path = sys.argv[1]
    api_url = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8000"

    test_convert_endpoint(pdf_path, api_url)
