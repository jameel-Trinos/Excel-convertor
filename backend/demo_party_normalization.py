#!/usr/bin/env python3
"""
Demo script for party name normalization.

This demonstrates how the PartyNormalizer converts various party name formats
to standardized names and aggregates minor parties into OTHERS.
"""

import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.party_normalizer import PartyNormalizer


def demo_basic_normalization():
    """Demo: Basic party name normalization."""
    print("=" * 80)
    print("DEMO 1: BASIC PARTY NAME NORMALIZATION")
    print("=" * 80)
    print()
    
    normalizer = PartyNormalizer()
    
    test_cases = [
        "Dravida Munnetra Kazhagam",
        "All India Anna Dravida Munnetra Kazhagam",
        "BHARATIYA JANATA PARTY",
        "Bharatiya Janata Party",
        "Indian National Congress",
        "VIDUTHALAI CHIRUTHAIGAL KATCHI",
        "Viduthalai Chiruthaigal Katchi",
        "PATTALI MAKKAL KATCHI",
        "Pattali Makkal Katchi",
        "NAAM TAMILAR KATCHI",
        "Naam Tamilar Katchi",
        "Bahujan Samaj Party",
        "Communist Party of India",
        "Independent",
        "NOTA",
        "Others",
    ]
    
    print("Input Column Name                              →  Normalized Name")
    print("-" * 80)
    for original in test_cases:
        normalized = normalizer.normalize_column_name(original)
        arrow = "→" if normalized else "→"
        print(f"{original:45}  {arrow}  {normalized or 'None (not a party column)'}")
    
    print()


def demo_variations():
    """Demo: Different naming variations."""
    print("=" * 80)
    print("DEMO 2: PARTY NAME VARIATIONS")
    print("=" * 80)
    print()
    
    normalizer = PartyNormalizer()
    
    test_cases = [
        ("DMK", "DMK"),
        ("D.M.K.", "DMK"),
        ("D M K", "DMK"),
        ("DMK Votes", "DMK"),
        ("Dravida Munnetra Kazhagam Votes", "DMK"),
        ("AIADMK", "AIADMK"),
        ("A.I.A.D.M.K.", "AIADMK"),
        ("BJP", "BJP"),
        ("B.J.P.", "BJP"),
        ("Congress", "CONGRESS"),
        ("INC", "CONGRESS"),
        ("VCK", "VCK"),
        ("V.C.K.", "VCK"),
        ("PMK", "PMK"),
        ("NTK", "NTK"),
    ]
    
    print("Input Variation                                →  Expected        Actual")
    print("-" * 80)
    for original, expected in test_cases:
        normalized = normalizer.normalize_column_name(original)
        match = "✅" if normalized == expected else "❌"
        print(f"{original:45}  →  {expected:15} {normalized:15} {match}")
    
    print()


def demo_column_aggregation():
    """Demo: Column aggregation with OTHERS."""
    print("=" * 80)
    print("DEMO 3: COLUMN AGGREGATION (OTHERS)")
    print("=" * 80)
    print()
    
    normalizer = PartyNormalizer()
    
    # Sample headers from a PDF
    headers = [
        "S.No.",
        "Polling Station",
        "DMK",
        "AIADMK",
        "BJP",
        "Congress",
        "VCK",
        "PMK",
        "NTK",
        "BSP",
        "CPI",
        "CPM",
        "Independent",
        "NOTA",
        "Total Votes",
    ]
    
    # Sample data rows
    data_rows = [
        ["1", "Station 001", "500", "450", "200", "150", "100", "80", "50", "30", "25", "20", "40", "10", "1655"],
        ["2", "Station 002", "520", "430", "210", "140", "95", "75", "55", "28", "22", "18", "35", "8", "1636"],
        ["3", "Station 003", "510", "440", "205", "145", "98", "78", "52", "32", "24", "19", "38", "12", "1653"],
    ]
    
    print("Original Headers:")
    print(f"  {headers}")
    print(f"  Total: {len(headers)} columns")
    print()
    
    print("Original Data (sample rows):")
    for row in data_rows[:2]:
        print(f"  {row}")
    print()
    
    # Normalize and aggregate
    normalized_headers, normalized_data = normalizer.normalize_and_aggregate_columns(
        headers,
        data_rows
    )
    
    print("Normalized Headers:")
    print(f"  {normalized_headers}")
    print(f"  Total: {len(normalized_headers)} columns")
    print()
    
    print("Normalized Data (BSP + CPI + CPM + Independent + NOTA → OTHERS):")
    for row in normalized_data[:2]:
        print(f"  {row}")
    print()
    
    # Show the aggregation breakdown for first row
    print("Aggregation Breakdown (Row 1):")
    print("  BSP (30) + CPI (25) + CPM (20) + Independent (40) + NOTA (10) = OTHERS (125)")
    print()


def demo_header_normalization():
    """Demo: Full header list normalization."""
    print("=" * 80)
    print("DEMO 4: COMPLETE HEADER NORMALIZATION")
    print("=" * 80)
    print()
    
    normalizer = PartyNormalizer()
    
    original_headers = [
        "Serial Number",
        "Polling Station Name",
        "Dravida Munnetra Kazhagam",
        "All India Anna Dravida Munnetra Kazhagam",
        "BHARATIYA JANATA PARTY",
        "Indian National Congress",
        "VIDUTHALAI CHIRUTHAIGAL KATCHI",
        "PATTALI MAKKAL KATCHI",
        "NAAM TAMILAR KATCHI",
        "Bahujan Samaj Party",
        "Communist Party of India",
        "Others",
        "Total Valid Votes",
    ]
    
    normalized_headers = normalizer.normalize_headers(original_headers)
    
    print("BEFORE → AFTER")
    print("-" * 80)
    for orig, norm in zip(original_headers, normalized_headers):
        changed = "✓" if orig != norm else " "
        print(f"{changed}  {orig:50} → {norm}")
    
    print()


def demo_standardized_party_list():
    """Demo: List all standardized party names."""
    print("=" * 80)
    print("DEMO 5: STANDARDIZED PARTY NAMES")
    print("=" * 80)
    print()
    
    normalizer = PartyNormalizer()
    party_names = normalizer.get_standardized_party_names()
    
    print("All standardized party names in the system:")
    print()
    for idx, party in enumerate(party_names, 1):
        variations = normalizer.PARTY_MAPPINGS.get(party, [])
        print(f"{idx}. {party}")
        print(f"   Recognizes: {', '.join(variations[:5])}")
        if len(variations) > 5:
            print(f"   ... and {len(variations) - 5} more variations")
        print()


def main():
    """Run all demos."""
    print()
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "PARTY NAME NORMALIZER - DEMO" + " " * 30 + "║")
    print("╚" + "=" * 78 + "╝")
    print()
    
    demo_basic_normalization()
    demo_variations()
    demo_column_aggregation()
    demo_header_normalization()
    demo_standardized_party_list()
    
    print("=" * 80)
    print("✅ ALL DEMOS COMPLETED")
    print("=" * 80)
    print()
    print("Party Mapping Summary:")
    print("  ✓ Dravida Munnetra Kazhagam → DMK")
    print("  ✓ All India Anna Dravida Munnetra Kazhagam → AIADMK")
    print("  ✓ BHARATIYA JANATA PARTY → BJP")
    print("  ✓ Indian National Congress → CONGRESS")
    print("  ✓ VIDUTHALAI CHIRUTHAIGAL KATCHI → VCK")
    print("  ✓ PATTALI MAKKAL KATCHI → PMK")
    print("  ✓ NAAM TAMILAR KATCHI → NTK")
    print("  ✓ BSP, CPI, CPM, Independent, NOTA, Others → OTHERS")
    print()


if __name__ == "__main__":
    main()







