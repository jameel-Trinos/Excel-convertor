#!/usr/bin/env python3
"""
Test script for Claude AI integration in PDF to Excel Converter.

This script tests:
1. Claude processor initialization
2. Document heading detection
3. Column header standardization
4. Fallback to OpenAI

Usage:
    python test_claude.py
"""

import os
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

from app.claude_processor import ClaudeProcessor
from app.ai_processor import AIProcessor


def print_section(title):
    """Print a section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def test_claude_initialization():
    """Test Claude processor initialization."""
    print_section("Test 1: Claude Processor Initialization")

    processor = ClaudeProcessor()

    print(f"✓ Claude processor created")
    print(f"  - Enabled: {processor.enabled}")
    print(f"  - Model: {processor.model}")
    print(f"  - API Key present: {'Yes' if processor.api_key else 'No'}")

    if processor.enabled:
        print(f"  ✅ SUCCESS: Claude is ready to use!")
    else:
        print(f"  ⚠️  WARNING: Claude not enabled (check ANTHROPIC_API_KEY)")

    return processor.enabled


def test_openai_fallback():
    """Test OpenAI fallback."""
    print_section("Test 2: OpenAI Fallback")

    processor = AIProcessor()

    print(f"✓ OpenAI processor created")
    print(f"  - Enabled: {processor.enabled}")
    print(f"  - Model: {processor.model}")
    print(f"  - API Key present: {'Yes' if processor.api_key else 'No'}")

    if processor.enabled:
        print(f"  ✅ SUCCESS: OpenAI fallback available!")
    else:
        print(f"  ⚠️  WARNING: OpenAI not enabled (check OPENAI_API_KEY)")

    return processor.enabled


def test_heading_detection():
    """Test document heading detection with Claude."""
    print_section("Test 3: Document Heading Detection")

    processor = ClaudeProcessor()

    if not processor.enabled:
        print("⏭️  SKIPPED: Claude not enabled")
        return False

    # Sample PDF text
    sample_text = """
    FORM 20 - FINAL RESULT SHEET
    PART - I

    GENERAL ELECTIONS TO LOK SABHA, 2024

    Assembly Constituency: 150 - Jayankondam
    Total Electors: 258,532
    """

    print("Sample PDF text:")
    print(sample_text)
    print("\nCalling Claude API...")

    try:
        heading, confidence = processor.extract_document_heading([sample_text])

        print(f"\n✅ SUCCESS!")
        print(f"  - Detected Heading: '{heading}'")
        print(f"  - Confidence: {confidence:.2%}")

        if "FORM 20" in heading or "FINAL RESULT" in heading:
            print(f"  ✅ Heading looks correct!")
            return True
        else:
            print(f"  ⚠️  Heading might be incorrect")
            return False

    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        return False


def test_column_standardization():
    """Test column header standardization with Claude."""
    print_section("Test 4: Column Header Standardization")

    processor = ClaudeProcessor()

    if not processor.enabled:
        print("⏭️  SKIPPED: Claude not enabled")
        return False

    # Sample headers from different pages
    headers_page1 = ["Station No.", "Party A", "Party B", "NOTA", "Total Votes"]
    headers_page2 = ["Stn No", "Party A", "Party B", "None of Above", "Total"]
    headers_page3 = ["Station Number", "Party A", "Party B", "NOTA", "Total Votes"]

    all_headers = [headers_page1, headers_page2, headers_page3]

    print("Sample headers from 3 pages:")
    for i, headers in enumerate(all_headers, 1):
        print(f"  Page {i}: {headers}")

    print("\nCalling Claude API...")

    try:
        mapping, confidence = processor.standardize_column_headers(all_headers)

        print(f"\n✅ SUCCESS!")
        print(f"  - Confidence: {confidence:.2%}")
        print(f"  - Standardized columns: {len(mapping)}")
        print("\nColumn Mapping:")

        for standard, variants in mapping.items():
            print(f"  '{standard}' ← {variants}")

        # Verify all headers were mapped
        total_headers = sum(len(h) for h in all_headers)
        mapped_headers = sum(len(v) for v in mapping.values())

        if mapped_headers >= total_headers * 0.9:  # At least 90% mapped
            print(f"\n  ✅ Mapping looks comprehensive!")
            return True
        else:
            print(f"\n  ⚠️  Some headers might be missing")
            return False

    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        return False


def test_cache_performance():
    """Test response caching."""
    print_section("Test 5: Response Caching")

    processor = ClaudeProcessor()

    if not processor.enabled:
        print("⏭️  SKIPPED: Claude not enabled")
        return False

    sample_text = ["Test document for caching"]

    print("First call (will hit API)...")
    try:
        import time

        start = time.time()
        heading1, _ = processor.extract_document_heading(sample_text)
        time1 = time.time() - start

        print(f"  - Time: {time1:.2f}s")
        print(f"  - Result: '{heading1}'")

        print("\nSecond call (should use cache)...")
        start = time.time()
        heading2, _ = processor.extract_document_heading(sample_text)
        time2 = time.time() - start

        print(f"  - Time: {time2:.2f}s")
        print(f"  - Result: '{heading2}'")

        if heading1 == heading2:
            print(f"\n✅ SUCCESS: Results match!")
            if time2 < time1 * 0.1:  # Cache should be 10x faster
                print(f"  ✅ Cache is working! ({time2:.3f}s vs {time1:.2f}s)")
                return True
            else:
                print(f"  ⚠️  Cache might not be working (similar times)")
                return False
        else:
            print(f"\n❌ FAILED: Results don't match")
            return False

    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        return False


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("  PDF to Excel Converter - Claude AI Integration Tests")
    print("="*60)

    # Check environment
    print("\n📋 Environment Check:")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    print(f"  - ANTHROPIC_API_KEY: {'✓ Set' if anthropic_key else '✗ Not set'}")
    print(f"  - OPENAI_API_KEY: {'✓ Set' if openai_key else '✗ Not set'}")

    if not anthropic_key and not openai_key:
        print("\n⚠️  WARNING: No API keys found!")
        print("   Set ANTHROPIC_API_KEY or OPENAI_API_KEY in backend/.env")
        print("   Most tests will be skipped.\n")

    # Run tests
    results = {
        "Claude Initialization": test_claude_initialization(),
        "OpenAI Fallback": test_openai_fallback(),
        "Heading Detection": test_heading_detection(),
        "Column Standardization": test_column_standardization(),
        "Cache Performance": test_cache_performance(),
    }

    # Summary
    print_section("Test Summary")

    passed = sum(1 for result in results.values() if result)
    total = len(results)

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}  {test_name}")

    print(f"\n{'='*60}")
    print(f"  Results: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
    print(f"{'='*60}\n")

    if passed == total:
        print("🎉 All tests passed! Claude integration is working perfectly!")
        return 0
    elif passed > 0:
        print("⚠️  Some tests passed. Check the failures above.")
        return 1
    else:
        print("❌ All tests failed. Check your API keys and configuration.")
        return 2


if __name__ == "__main__":
    sys.exit(main())
