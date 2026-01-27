"""Test script for party name normalization."""

import sys
from pathlib import Path

# Add the app directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.party_normalizer import PartyNormalizer


def test_basic_normalization():
    """Test basic party name normalization."""
    print("=" * 70)
    print("TEST 1: Basic Party Name Normalization")
    print("=" * 70)

    normalizer = PartyNormalizer()

    test_cases = [
        "Dravida Munnetra Kazhagam",
        "All India Anna Dravida Munnetra Kazhagam",
        "Bharatiya Janata Party",
        "Indian National Congress",
        "Viduthalai Chiruthaigal Katchi",
        "Pattali Makkal Katchi",
        "Naam Tamilar Katchi",
        "Independent",
        "NOTA",
        "Others",
    ]

    for original in test_cases:
        normalized = normalizer.normalize_column_name(original)
        print(f"  {original:45} -> {normalized}")

    print()


def test_variations():
    """Test various naming variations."""
    print("=" * 70)
    print("TEST 2: Party Name Variations")
    print("=" * 70)

    normalizer = PartyNormalizer()

    test_cases = [
        "DMK",
        "D.M.K.",
        "D M K",
        "DMK Votes",
        "Dravida Munnetra Kazhagam Votes",
        "AIADMK",
        "A.I.A.D.M.K.",
        "BJP",
        "B.J.P.",
        "Congress",
        "INC",
        "Congress (I)",
        "VCK",
        "V.C.K.",
        "PMK",
        "NTK",
        "Other",
        "Independent Votes",
    ]

    for original in test_cases:
        normalized = normalizer.normalize_column_name(original)
        print(f"  {original:45} -> {normalized}")

    print()


def test_partial_matches():
    """Test partial matching for complex column names."""
    print("=" * 70)
    print("TEST 3: Partial Matches (Complex Column Names)")
    print("=" * 70)

    normalizer = PartyNormalizer()

    test_cases = [
        "Total Votes - DMK",
        "DMK (Votes Polled)",
        "Votes for Bharatiya Janata Party",
        "Congress - Total Count",
        "Independent Candidate Votes",
        "NOTA - None of the Above",
    ]

    for original in test_cases:
        normalized = normalizer.normalize_column_name(original)
        print(f"  {original:45} -> {normalized}")

    print()


def test_non_party_columns():
    """Test that non-party columns are not normalized."""
    print("=" * 70)
    print("TEST 4: Non-Party Columns (Should Return None)")
    print("=" * 70)

    normalizer = PartyNormalizer()

    test_cases = [
        "Serial Number",
        "Candidate Name",
        "Total Votes",
        "Percentage",
        "Ward Number",
        "Constituency",
    ]

    for original in test_cases:
        normalized = normalizer.normalize_column_name(original)
        status = "✓ Correctly ignored" if normalized is None else f"✗ Incorrectly mapped to {normalized}"
        print(f"  {original:45} -> {status}")

    print()


def test_column_mapping_integration():
    """Test integration with AI column mapping."""
    print("=" * 70)
    print("TEST 5: Column Mapping Integration (AI Output)")
    print("=" * 70)

    normalizer = PartyNormalizer()

    # Simulate AI-generated column mapping with various party names
    ai_column_mapping = {
        "Serial Number": ["Serial Number", "S.No.", "No."],
        "Candidate Name": ["Candidate Name", "Name", "Candidate"],
        "Dravida Munnetra Kazhagam": ["DMK", "D.M.K.", "Dravida Munnetra Kazhagam"],
        "All India Anna Dravida Munnetra Kazhagam": ["AIADMK", "A.I.A.D.M.K."],
        "Bharatiya Janata Party": ["BJP", "B.J.P.", "Bharatiya Janata Party Votes"],
        "Indian National Congress": ["Congress", "INC", "Indian National Congress"],
        "Independent": ["Independent", "Other"],
        "Total Votes": ["Total Votes", "Total", "Votes Polled"],
    }

    print("\nOriginal AI Mapping:")
    for standard, variants in ai_column_mapping.items():
        print(f"  {standard}: {variants}")

    normalized_mapping = normalizer.normalize_column_mapping(ai_column_mapping)

    print("\nNormalized Mapping:")
    for standard, variants in normalized_mapping.items():
        print(f"  {standard}: {variants}")

    print()


def test_header_list_normalization():
    """Test normalizing a complete header list."""
    print("=" * 70)
    print("TEST 6: Header List Normalization")
    print("=" * 70)

    normalizer = PartyNormalizer()

    original_headers = [
        "Serial Number",
        "Candidate Name",
        "DMK",
        "AIADMK",
        "BJP",
        "Congress",
        "VCK",
        "PMK",
        "Independent",
        "Total Votes",
    ]

    normalized_headers = normalizer.normalize_headers(original_headers)

    print("\nOriginal Headers -> Normalized Headers:")
    for orig, norm in zip(original_headers, normalized_headers):
        changed = "✓" if orig != norm else " "
        print(f"  {changed} {orig:30} -> {norm}")

    print()


def test_standardized_party_list():
    """Test getting the list of standardized party names."""
    print("=" * 70)
    print("TEST 7: Standardized Party Names")
    print("=" * 70)

    normalizer = PartyNormalizer()
    party_names = normalizer.get_standardized_party_names()

    print("\nAll Standardized Party Vote Column Names:")
    for idx, party in enumerate(party_names, 1):
        print(f"  {idx}. {party}")

    print()


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("PARTY NAME NORMALIZER - TEST SUITE")
    print("=" * 70)
    print()

    test_basic_normalization()
    test_variations()
    test_partial_matches()
    test_non_party_columns()
    test_column_mapping_integration()
    test_header_list_normalization()
    test_standardized_party_list()

    print("=" * 70)
    print("ALL TESTS COMPLETED")
    print("=" * 70)
    print()


if __name__ == "__main__":
    main()
