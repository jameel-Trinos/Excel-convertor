#!/usr/bin/env python3
"""Test voter PDF extraction - run with a voter PDF file path as argument.

Usage:
    python test_voter_extraction.py /path/to/voter.pdf

Outputs detailed stats about extraction quality.
"""

import sys
import logging
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.voters_pdf_processor import VotersPDFProcessor

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s',
)

def test_extraction(pdf_path: str):
    print(f"\n{'='*70}")
    print(f"Testing voter extraction: {pdf_path}")
    print(f"{'='*70}\n")

    processor = VotersPDFProcessor(pdf_path)

    def progress_cb(pct, msg):
        print(f"  [{pct:3d}%] {msg}")

    result = processor.extract(progress_callback=progress_cb)

    voters = result["voters"]
    headers = result["headers"]
    header_info = result["header_info"]
    total_pages = result["total_pages"]

    print(f"\n{'='*70}")
    print(f"RESULTS")
    print(f"{'='*70}")
    print(f"Total pages: {total_pages}")
    print(f"Total voters extracted: {len(voters)}")
    print(f"AC No: {header_info.ac_no}")
    print(f"Part No: {header_info.part_no}")
    print(f"Address: {header_info.address}")
    print(f"Total voters (from header): {header_info.total_voters}")

    # Check for missing fields
    missing_stats = {h: 0 for h in headers}
    for row in voters:
        for i, val in enumerate(row):
            if not val or not val.strip():
                missing_stats[headers[i]] += 1

    print(f"\n--- Missing Field Stats ---")
    for h, count in missing_stats.items():
        pct = count / max(len(voters), 1) * 100
        status = "OK" if count == 0 else f"MISSING {count} ({pct:.1f}%)"
        print(f"  {h:25s}: {status}")

    # Show first 5 and last 5 voters
    print(f"\n--- First 5 voters ---")
    for row in voters[:5]:
        print(f"  {row}")

    print(f"\n--- Last 5 voters ---")
    for row in voters[-5:]:
        print(f"  {row}")

    # Check serial number continuity
    print(f"\n--- Serial Number Check ---")
    expected_total = int(header_info.total_voters) if header_info.total_voters else 0
    if expected_total:
        diff = expected_total - len(voters)
        if diff == 0:
            print(f"  PERFECT: Extracted {len(voters)} == Expected {expected_total}")
        else:
            print(f"  MISMATCH: Extracted {len(voters)} vs Expected {expected_total} (missing {diff})")

    # Show voters with most missing fields
    print(f"\n--- Voters with empty fields (showing first 20) ---")
    count_shown = 0
    for row in voters:
        empties = [headers[i] for i, v in enumerate(row) if not v or not v.strip()]
        if empties:
            # Skip serial no - it's always filled by renumbering
            empties = [e for e in empties if e != "Serial No"]
            if empties:
                print(f"  #{row[0]:>4s} | {row[1]:20s} | missing: {', '.join(empties)}")
                count_shown += 1
                if count_shown >= 20:
                    remaining = sum(1 for r in voters if any(not v or not v.strip() for i, v in enumerate(r) if headers[i] != "Serial No"))
                    print(f"  ... and {remaining - 20} more voters with missing fields")
                    break

    return len(voters), expected_total


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_voter_extraction.py /path/to/voter.pdf")
        sys.exit(1)

    pdf_path = sys.argv[1]
    if not os.path.exists(pdf_path):
        print(f"File not found: {pdf_path}")
        sys.exit(1)

    extracted, expected = test_extraction(pdf_path)
    if expected and extracted == expected:
        print(f"\n✅ SUCCESS: All {expected} voters extracted!")
    elif expected:
        print(f"\n❌ INCOMPLETE: {extracted}/{expected} voters extracted (missing {expected - extracted})")
    else:
        print(f"\n⚠️  Extracted {extracted} voters (no expected count in header to compare)")
