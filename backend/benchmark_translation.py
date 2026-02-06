#!/usr/bin/env python3
"""
Translation Performance Benchmark

Tests the concurrent translation implementation to verify performance improvements.
Expected: 1000 texts in <30 seconds (first run), <1 second (cached run)
"""

import asyncio
import time
import sys
import os

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.translation_service import TranslationService


async def benchmark_translation(num_texts: int = 1000):
    """
    Benchmark translation performance.

    Args:
        num_texts: Number of texts to translate (default: 1000)
    """
    print(f"\n{'='*70}")
    print(f"Translation Performance Benchmark")
    print(f"{'='*70}")
    print(f"Testing with {num_texts} texts...\n")

    # Create service
    service = TranslationService()

    if not service.enabled:
        print("❌ Translation service not enabled!")
        return

    # Generate test texts
    test_texts = [
        f"Test text number {i} for translation benchmark"
        for i in range(num_texts)
    ]

    # Add some variety
    test_texts.extend([
        "Hello world",
        "Good morning",
        "Thank you",
        "Please",
        "Welcome",
        "Goodbye",
        "How are you",
        "Nice to meet you",
        "See you later",
        "Have a good day",
    ] * (num_texts // 100))

    print(f"📝 Generated {len(test_texts)} test texts")

    # First run (no cache)
    print(f"\n{'─'*70}")
    print("Test 1: First Run (No Cache)")
    print(f"{'─'*70}")

    completed = [0]

    def progress_callback(current: int, total: int):
        completed[0] = current
        if current % 100 == 0 or current == total:
            percent = (current / total) * 100 if total > 0 else 0
            print(f"Progress: {current}/{total} ({percent:.1f}%)")

    start_time = time.time()
    results = await service.translate_batch(
        test_texts,
        "tamil",
        progress_callback=progress_callback
    )
    elapsed = time.time() - start_time

    print(f"\n✅ First run completed!")
    print(f"   Time: {elapsed:.2f} seconds")
    print(f"   Throughput: {len(test_texts)/elapsed:.1f} texts/second")
    print(f"   Translated: {len(results)} texts")

    # Check if target met
    target_time = 30.0
    if elapsed < target_time:
        print(f"   🎯 Target met! (<{target_time}s)")
    else:
        print(f"   ⚠️  Target missed (expected <{target_time}s)")

    # Second run (cached)
    print(f"\n{'─'*70}")
    print("Test 2: Second Run (Cached)")
    print(f"{'─'*70}")

    start_time = time.time()
    results2 = await service.translate_batch(
        test_texts,
        "tamil",
        progress_callback=progress_callback
    )
    elapsed2 = time.time() - start_time

    print(f"\n✅ Cached run completed!")
    print(f"   Time: {elapsed2:.2f} seconds")
    print(f"   Throughput: {len(test_texts)/elapsed2:.1f} texts/second")

    # Check if target met
    cache_target = 2.0
    if elapsed2 < cache_target:
        print(f"   🎯 Cache target met! (<{cache_target}s)")
    else:
        print(f"   ⚠️  Cache target missed (expected <{cache_target}s)")

    # Calculate speedup
    speedup = elapsed / elapsed2 if elapsed2 > 0 else 0
    print(f"   Speedup: {speedup:.1f}x faster")

    # Cleanup
    await service.close()

    # Summary
    print(f"\n{'='*70}")
    print("Summary")
    print(f"{'='*70}")
    print(f"Total texts translated: {len(test_texts)}")
    print(f"First run: {elapsed:.2f}s ({len(test_texts)/elapsed:.1f} texts/s)")
    print(f"Cached run: {elapsed2:.2f}s ({len(test_texts)/elapsed2:.1f} texts/s)")
    print(f"Performance improvement: {speedup:.1f}x")

    # Baseline comparison
    baseline = len(test_texts) * 0.3  # 300ms per text (old sequential)
    print(f"\nBaseline (sequential): ~{baseline:.1f}s")
    print(f"Actual (concurrent): {elapsed:.1f}s")
    print(f"Overall speedup: {baseline/elapsed:.1f}x")

    print(f"\n{'='*70}\n")


if __name__ == "__main__":
    num_texts = 1000
    if len(sys.argv) > 1:
        try:
            num_texts = int(sys.argv[1])
        except ValueError:
            print(f"Invalid number: {sys.argv[1]}")
            sys.exit(1)

    asyncio.run(benchmark_translation(num_texts))
