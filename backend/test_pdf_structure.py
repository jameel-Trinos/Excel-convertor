#!/usr/bin/env python3
"""Quick diagnostic: what does pdfplumber see on each page?"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pdfplumber

pdf_path = sys.argv[1] if len(sys.argv) > 1 else "/Users/abc/Downloads/155-eroll/2026-EROLLGEN-S22-155-SIR-DraftRoll-Revision1-TAM-19-WI.pdf"

with pdfplumber.open(pdf_path) as pdf:
    print(f"Total pages: {len(pdf.pages)}")
    for i, page in enumerate(pdf.pages):
        text = page.extract_text() or ""
        rects = page.rects or []
        edges = page.edges or []
        tables = []
        try:
            tables = page.extract_tables() or []
        except:
            pass

        text_len = len(text.strip())
        # Count voter card-like rects (roughly 1/3 width, certain height)
        pw = float(page.width)
        ph = float(page.height)
        card_rects = [r for r in rects
                      if pw * 0.15 <= (r["x1"] - r["x0"]) <= pw * 0.5
                      and ph * 0.035 <= (r["bottom"] - r["top"]) <= ph * 0.20]

        print(f"Page {i+1:2d}: text={text_len:5d} chars, rects={len(rects):3d} (cards={len(card_rects):3d}), edges={len(edges):4d}, tables={len(tables)}")

        # Show first 100 chars of text for non-card pages
        if len(card_rects) == 0 and text_len > 0:
            print(f"         text preview: {text[:150].replace(chr(10), ' | ')!r}")

        # If this is a card page, show card details
        if card_rects:
            # Determine rows and columns
            tops = sorted(set(round(r["top"], 0) for r in card_rects))
            x0s = sorted(set(round(r["x0"], 0) for r in card_rects))
            print(f"         rows={len(tops)}, cols={len(x0s)}, cards={len(card_rects)}")
            # Show one sample card text
            r = card_rects[0]
            try:
                cropped = page.crop((r["x0"]+2, r["top"]+2, r["x1"]-2, r["bottom"]-2), strict=False)
                ct = cropped.extract_text() or ""
                print(f"         sample card: {ct[:200].replace(chr(10), ' | ')!r}")
            except Exception as e:
                print(f"         crop failed: {e}")

        if i >= 25:  # Stop after enough pages
            break
