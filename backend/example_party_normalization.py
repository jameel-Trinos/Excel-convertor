#!/usr/bin/env python3
"""
Example: Using Party Name Normalization

This demonstrates how the party normalization feature works
when processing Tamil Nadu election data PDFs.
"""

import sys
from pathlib import Path

# Add the app directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.party_normalizer import PartyNormalizer


def example_basic_usage():
    """Example 1: Basic normalization of party names."""
    print("\n" + "=" * 70)
    print("EXAMPLE 1: Basic Party Name Normalization")
    print("=" * 70)

    normalizer = PartyNormalizer()

    # Simulate column headers from a PDF
    pdf_headers = [
        "Serial Number",
        "Candidate Name",
        "DMK",
        "AIADMK",
        "BJP",
        "Congress",
        "Independent",
        "Total Votes",
    ]

    print("\nOriginal PDF Headers:")
    print(pdf_headers)

    # Normalize the headers
    normalized = normalizer.normalize_headers(pdf_headers)

    print("\nNormalized Headers (for Excel):")
    print(normalized)

    print("\nChanges Made:")
    for orig, norm in zip(pdf_headers, normalized):
        if orig != norm:
            print(f"  ✓ {orig:20} → {norm}")


def example_multi_page_consistency():
    """Example 2: Ensuring consistency across multiple pages."""
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Multi-Page Consistency")
    print("=" * 70)

    normalizer = PartyNormalizer()

    # Simulate headers from different pages using different naming styles
    page1_headers = ["S.No.", "Name", "DMK", "AIADMK", "BJP", "Total"]
    page2_headers = [
        "Serial",
        "Candidate",
        "Dravida Munnetra Kazhagam",
        "All India Anna Dravida Munnetra Kazhagam",
        "Bharatiya Janata Party",
        "Total Votes",
    ]

    print("\nPage 1 Headers (Abbreviated):")
    print(page1_headers)
    print("\nPage 2 Headers (Full Names):")
    print(page2_headers)

    # Normalize both pages
    normalized1 = normalizer.normalize_headers(page1_headers)
    normalized2 = normalizer.normalize_headers(page2_headers)

    print("\nNormalized Page 1:")
    print(normalized1)
    print("\nNormalized Page 2:")
    print(normalized2)

    print("\nResult: Party columns are now consistent across both pages!")
    print(f"  Page 1 [2]: {normalized1[2]}")
    print(f"  Page 2 [2]: {normalized2[2]}")
    print(f"  Match: {normalized1[2] == normalized2[2]} ✓")


def example_ai_integration():
    """Example 3: Integration with AI column mapping."""
    print("\n" + "=" * 70)
    print("EXAMPLE 3: AI Column Mapping Integration")
    print("=" * 70)

    normalizer = PartyNormalizer()

    # Simulate AI-generated column mapping (before normalization)
    # AI has grouped variations but used descriptive names
    ai_mapping = {
        "Serial Number": ["S.No.", "Serial", "No."],
        "Candidate Name": ["Name", "Candidate", "Candidate Name"],
        "Dravida Munnetra Kazhagam": ["DMK", "D.M.K.", "Dravida Munnetra Kazhagam"],
        "All India Anna Dravida Munnetra Kazhagam": ["AIADMK", "A.I.A.D.M.K."],
        "Bharatiya Janata Party": ["BJP", "Bharatiya Janata Party"],
        "Total Votes": ["Total", "Total Votes", "Votes"],
    }

    print("\nAI-Generated Column Mapping (Before Normalization):")
    for standard, variants in ai_mapping.items():
        print(f"  {standard}")
        print(f"    Variants: {', '.join(variants)}")

    # Apply party normalization
    normalized_mapping = normalizer.normalize_column_mapping(ai_mapping)

    print("\nNormalized Column Mapping (After Party Normalization):")
    for standard, variants in normalized_mapping.items():
        print(f"  {standard}")
        print(f"    Variants: {', '.join(variants)}")

    print("\nNotice: Party names are now standardized to Tamil Nadu format!")


def example_edge_cases():
    """Example 4: Handling edge cases and complex names."""
    print("\n" + "=" * 70)
    print("EXAMPLE 4: Edge Cases & Complex Column Names")
    print("=" * 70)

    normalizer = PartyNormalizer()

    complex_headers = [
        "Total Votes - DMK",
        "DMK (Votes Polled)",
        "Votes for Bharatiya Janata Party",
        "Congress - Total Count",
        "Independent Candidate",
        "NOTA - None of the Above",
        "Other Parties",
    ]

    print("\nComplex Column Names:")
    for header in complex_headers:
        normalized = normalizer.normalize_column_name(header)
        status = "✓" if normalized else "○"
        result = normalized if normalized else "Not a party column"
        print(f"  {status} {header:40} → {result}")


def example_checking_party_columns():
    """Example 5: Identifying party columns."""
    print("\n" + "=" * 70)
    print("EXAMPLE 5: Identifying Party Columns")
    print("=" * 70)

    normalizer = PartyNormalizer()

    all_columns = [
        "Serial Number",
        "Ward Number",
        "Candidate Name",
        "DMK",
        "AIADMK",
        "Total Votes",
        "Percentage",
        "BJP",
        "Status",
    ]

    print("\nChecking which columns are party vote columns:")
    for column in all_columns:
        is_party = normalizer.is_party_column(column)
        marker = "★" if is_party else "○"
        print(f"  {marker} {column:20} → {'Party Column' if is_party else 'Regular Column'}")


def example_standardized_list():
    """Example 6: Getting the complete list of standardized names."""
    print("\n" + "=" * 70)
    print("EXAMPLE 6: Complete List of Standardized Party Names")
    print("=" * 70)

    normalizer = PartyNormalizer()
    parties = normalizer.get_standardized_party_names()

    print("\nAll Standardized Party Vote Column Names:")
    print("(These are the ONLY party column names in the final Excel)")
    print()
    for idx, party in enumerate(parties, 1):
        print(f"  {idx}. {party}")

    print(f"\nTotal: {len(parties)} standardized party columns")


def main():
    """Run all examples."""
    print("\n" + "=" * 70)
    print("PARTY NAME NORMALIZATION - USAGE EXAMPLES")
    print("Tamil Nadu Election Data Processing")
    print("=" * 70)

    example_basic_usage()
    example_multi_page_consistency()
    example_ai_integration()
    example_edge_cases()
    example_checking_party_columns()
    example_standardized_list()

    print("\n" + "=" * 70)
    print("END OF EXAMPLES")
    print("=" * 70)
    print("\nFor more information, see: PARTY_NORMALIZATION.md")
    print()


if __name__ == "__main__":
    main()
