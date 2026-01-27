"""Test script for header extraction from election PDFs."""

import sys
from pathlib import Path

# Add the app directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.header_extractor import HeaderExtractor, extract_election_headers, get_cached_headers
from app.election_processor import ElectionProcessor, extract_election_data
from app.party_normalizer import PartyNormalizer


def test_header_extractor_basic(pdf_path: str):
    """Test basic header extraction from PDF."""
    print("=" * 70)
    print("TEST 1: Basic Header Extraction")
    print("=" * 70)

    try:
        extractor = HeaderExtractor(pdf_path)
        party_columns, original_mapping = extractor.extract_party_headers()

        print(f"\nFound {len(party_columns)} party columns:")
        for idx, col in enumerate(party_columns, 1):
            print(f"  {idx}. {col}")

        print(f"\nOriginal to Standard Mapping ({len(original_mapping)} entries):")
        for original, standard in list(original_mapping.items())[:10]:
            print(f"  '{original}' -> '{standard}'")
        if len(original_mapping) > 10:
            print(f"  ... and {len(original_mapping) - 10} more")

    except Exception as e:
        print(f"ERROR: {e}")

    print()


def test_standardized_headers(pdf_path: str):
    """Test standardized header output."""
    print("=" * 70)
    print("TEST 2: Standardized Headers (Ordered)")
    print("=" * 70)

    try:
        extractor = HeaderExtractor(pdf_path)
        std_headers = extractor.get_standardized_headers()

        print(f"\nStandardized party columns in order:")
        for idx, col in enumerate(std_headers, 1):
            print(f"  {idx}. {col}")

    except Exception as e:
        print(f"ERROR: {e}")

    print()


def test_full_header_row(pdf_path: str):
    """Test full header row for Excel output."""
    print("=" * 70)
    print("TEST 3: Full Header Row for Excel")
    print("=" * 70)

    try:
        extractor = HeaderExtractor(pdf_path)
        full_headers = extractor.get_full_header_row()

        print(f"\nFull header row ({len(full_headers)} columns):")
        for idx, col in enumerate(full_headers, 1):
            print(f"  {idx}. {col}")

    except Exception as e:
        print(f"ERROR: {e}")

    print()


def test_election_processor(pdf_path: str):
    """Test election processor extraction."""
    print("=" * 70)
    print("TEST 4: Election Processor - Header Extraction")
    print("=" * 70)

    try:
        processor = ElectionProcessor(pdf_path)
        headers, column_mapping = processor.extract_headers()

        print(f"\nExtracted {len(headers)} column headers:")
        for idx, header in enumerate(headers, 1):
            print(f"  {idx}. {header}")

        print(f"\nParty columns found:")
        party_cols = processor.get_party_columns()
        for idx, col in enumerate(party_cols, 1):
            print(f"  {idx}. {col}")

        print(f"\nRecommended output column order:")
        output_order = processor.get_output_column_order()
        for idx, col in enumerate(output_order, 1):
            print(f"  {idx}. {col}")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

    print()


def test_extract_function(pdf_path: str):
    """Test the extract_election_data function."""
    print("=" * 70)
    print("TEST 5: extract_election_data Function")
    print("=" * 70)

    try:
        result = extract_election_data(pdf_path)

        print(f"\nHeaders ({len(result['headers'])} total):")
        for idx, h in enumerate(result['headers'][:15], 1):
            print(f"  {idx}. {h}")
        if len(result['headers']) > 15:
            print(f"  ... and {len(result['headers']) - 15} more")

        print(f"\nParty Columns ({len(result['party_columns'])} found):")
        for col in result['party_columns']:
            print(f"  - {col}")

        print(f"\nOutput Column Order:")
        for idx, col in enumerate(result['output_column_order'], 1):
            print(f"  {idx}. {col}")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

    print()


def test_party_normalization():
    """Test party name normalization."""
    print("=" * 70)
    print("TEST 6: Party Name Normalization")
    print("=" * 70)

    normalizer = PartyNormalizer()

    # Test abbreviations from the PDF
    test_cases = [
        "BJP",
        "AIADMK",
        "BSP",
        "NMK",
        "VCK",
        "NTK",
        "IND",
        "Independent",
        "NOTA",
        "KARTHIYAYI NI. P (BJP)",  # Should not match (full name with party)
        "DMK",
        "Congress",
        "PMK",
    ]

    print("\nParty abbreviation normalization:")
    for test in test_cases:
        result = normalizer.normalize_column_name(test)
        status = f"-> {result}" if result else "-> NOT MATCHED"
        print(f"  '{test}' {status}")

    print()


def test_caching(pdf_path: str):
    """Test header caching functionality."""
    print("=" * 70)
    print("TEST 7: Header Caching")
    print("=" * 70)

    try:
        # First call - should extract
        import time
        start = time.time()
        result1 = get_cached_headers(pdf_path)
        time1 = time.time() - start

        # Second call - should use cache
        start = time.time()
        result2 = get_cached_headers(pdf_path)
        time2 = time.time() - start

        print(f"\nFirst call: {time1:.3f}s ({len(result1['party_columns'])} party columns)")
        print(f"Second call (cached): {time2:.3f}s ({len(result2['party_columns'])} party columns)")
        print(f"Cache speedup: {time1/max(time2, 0.001):.1f}x")

        # Verify results are identical
        if result1['party_columns'] == result2['party_columns']:
            print("Results are identical (deterministic)")
        else:
            print("WARNING: Results differ!")

    except Exception as e:
        print(f"ERROR: {e}")

    print()


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("HEADER EXTRACTOR - TEST SUITE")
    print("=" * 70)
    print()

    # Check for PDF file argument
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        # Default test PDF path
        pdf_path = "test.pdf"

        # Look for any PDF in current directory
        pdfs = list(Path(".").glob("*.pdf"))
        if pdfs:
            pdf_path = str(pdfs[0])
            print(f"Using found PDF: {pdf_path}")
        else:
            print("No PDF file specified or found.")
            print("Usage: python test_header_extractor.py <pdf_path>")
            print()
            # Run non-PDF tests
            test_party_normalization()
            return

    if not Path(pdf_path).exists():
        print(f"PDF file not found: {pdf_path}")
        return

    print(f"Testing with PDF: {pdf_path}")
    print()

    # Run tests
    test_header_extractor_basic(pdf_path)
    test_standardized_headers(pdf_path)
    test_full_header_row(pdf_path)
    test_election_processor(pdf_path)
    test_extract_function(pdf_path)
    test_party_normalization()
    test_caching(pdf_path)

    print("=" * 70)
    print("ALL TESTS COMPLETED")
    print("=" * 70)
    print()


if __name__ == "__main__":
    main()
