#!/usr/bin/env python3
"""
Test script for HuggingFace-based translation service.
"""

import sys
import os

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.translation_service import TranslationService


def test_basic_functionality():
    """Test that the service initializes and basic methods work."""
    print("=" * 60)
    print("Testing HuggingFace Translation Service")
    print("=" * 60)

    # Initialize service
    print("\n1. Initializing TranslationService...")
    service = TranslationService(model_type="auto")
    print(f"   - Enabled: {service.enabled}")
    print(f"   - Model type: {service.model_type}")
    print(f"   - Device: {service.device}")

    # Test should_translate logic (no model loading needed)
    print("\n2. Testing should_translate() logic...")
    test_cases = [
        ("Hello World", True),
        ("12345", False),  # Pure number
        ("DMK", False),    # Short abbreviation
        ("வாக்குச்சாவடி", False),  # Already Tamil
        ("Polling Station", True),
        ("S.No", False),   # Pattern match
        ("", False),       # Empty
    ]
    for text, expected in test_cases:
        result = service.should_translate(text)
        status = "✓" if result == expected else "✗"
        print(f"   {status} '{text}' -> should_translate={result} (expected={expected})")

    # Test common translations (cached, no model loading)
    print("\n3. Testing common translations (cached)...")
    common_tests = [
        ("Polling Station", "to_tamil", "வாக்குச்சாவடி"),
        ("Total", "to_tamil", "மொத்தம்"),
        ("District", "to_tamil", "மாவட்டம்"),
    ]
    for text, direction, expected in common_tests:
        result = service.translate_text(text, direction)
        status = "✓" if result == expected else "✗"
        print(f"   {status} '{text}' -> '{result}' (expected='{expected}')")

    print("\n4. Model info (before loading):")
    info = service.get_model_info()
    for k, v in info.items():
        print(f"   - {k}: {v}")

    print("\n" + "=" * 60)
    print("Basic tests completed!")
    print("=" * 60)

    return True


def test_model_loading():
    """Test that models can be loaded (requires dependencies)."""
    print("\n" + "=" * 60)
    print("Testing Model Loading (requires HuggingFace deps)")
    print("=" * 60)

    try:
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        import torch
        print(f"✓ transformers imported successfully")
        print(f"✓ torch version: {torch.__version__}")
        print(f"✓ CUDA available: {torch.cuda.is_available()}")
    except ImportError as e:
        print(f"✗ Missing dependencies: {e}")
        print("\nInstall with: pip install transformers sentencepiece torch")
        return False

    # Test with a simple translation
    print("\n5. Testing actual translation (this will download models)...")
    service = TranslationService(model_type="marian")  # MarianMT is smaller

    try:
        # This will trigger model loading
        result = service.translate_text("Election Commission", "to_tamil")
        print(f"   'Election Commission' -> '{result}'")

        info = service.get_model_info()
        print("\n6. Model info (after loading):")
        for k, v in info.items():
            print(f"   - {k}: {v}")

        print("\n✓ Model loading and translation successful!")
        return True

    except Exception as e:
        print(f"\n✗ Translation failed: {e}")
        return False


if __name__ == "__main__":
    # Run basic tests (no model loading)
    basic_ok = test_basic_functionality()

    # Optionally test model loading
    if len(sys.argv) > 1 and sys.argv[1] == "--full":
        model_ok = test_model_loading()
    else:
        print("\nSkipping model loading tests. Run with --full to test model loading.")
        model_ok = True

    sys.exit(0 if basic_ok and model_ok else 1)
