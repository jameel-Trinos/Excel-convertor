"""Diagnostic script to understand EPIC extraction issues.

Usage: python diagnose_epic.py <path_to_voter_pdf> [page_number]

This prints detailed info about what pdfplumber sees for EPICs on a page.
"""
import re
import sys
import pdfplumber

_EPIC_RE = re.compile(r'(?<![A-Z])([A-Z]{3}\d{7})(?!\d)')

def diagnose(pdf_path: str, target_page: int = 7):
    with pdfplumber.open(pdf_path) as pdf:
        if target_page > len(pdf.pages):
            print(f"PDF only has {len(pdf.pages)} pages")
            return

        page = pdf.pages[target_page - 1]  # 0-indexed
        page_text = page.extract_text() or ""

        # 1. Show all EPICs found in full page text
        epics_in_text = _EPIC_RE.findall(page_text)
        print(f"\n=== Page {target_page} ===")
        print(f"Page text length: {len(page_text)} chars")
        print(f"\n--- EPICs found in full page text ({len(epics_in_text)}): ---")
        for e in epics_in_text:
            print(f"  {e}")

        # 2. Show EPICs found in words
        raw_words = page.extract_words(keep_blank_chars=False)
        epic_words = []
        for pw in raw_words:
            m = _EPIC_RE.search(pw["text"])
            if m:
                epic_words.append({
                    "epic": m.group(1),
                    "text": pw["text"],
                    "x0": float(pw["x0"]),
                    "x1": float(pw["x1"]),
                    "top": float(pw["top"]),
                })

        print(f"\n--- EPICs found in words ({len(epic_words)}): ---")
        for ew in epic_words:
            print(f"  {ew['epic']} text='{ew['text']}' pos=({ew['x0']:.1f}, {ew['top']:.1f})-({ew['x1']:.1f})")

        # 3. Show serial number + EPIC pairs in text
        print(f"\n--- Serial+EPIC patterns in page text: ---")
        for m in re.finditer(r'(\d{1,4})\s*([A-Z]{3}\d{7})', page_text):
            print(f"  Serial {m.group(1)} -> EPIC {m.group(2)}")

        # 4. Show lines containing serial numbers 190-210 (the range with issues)
        print(f"\n--- Lines with serial numbers 184-210: ---")
        for line in page_text.split('\n'):
            for sn in range(184, 211):
                if re.search(r'(?:^|\s)' + str(sn) + r'(?:\s|$)', line):
                    print(f"  [{sn}] {line.strip()}")
                    break

        # 5. Show card rects detected
        rects = page.rects or []
        page_w = float(page.width)
        page_h = float(page.height)
        min_card_w = page_w * 0.15
        max_card_w = page_w * 0.5
        min_card_h = page_h * 0.035
        max_card_h = page_h * 0.20

        cards = []
        for r in rects:
            w = r["x1"] - r["x0"]
            h = r["bottom"] - r["top"]
            if min_card_w <= w <= max_card_w and min_card_h <= h <= max_card_h:
                cards.append((r["x0"], r["top"], r["x1"], r["bottom"]))
        cards.sort(key=lambda c: (round(c[1], 0), c[0]))

        print(f"\n--- Card bounding boxes ({len(cards)}): ---")
        for i, (x0, top, x1, bot) in enumerate(cards):
            print(f"  Card {i}: x0={x0:.1f} top={top:.1f} x1={x1:.1f} bot={bot:.1f} (w={x1-x0:.1f} h={bot-top:.1f})")

        # 6. Show ALL words in the EPIC strip areas (between rows)
        row_tops = sorted(set(round(c[1], 0) for c in cards))
        row_bottoms = {}
        for c in cards:
            rt = round(c[1], 0)
            row_bottoms[rt] = max(row_bottoms.get(rt, 0), c[3])

        print(f"\n--- Row boundaries: ---")
        for i, rt in enumerate(row_tops):
            rb = row_bottoms.get(rt, 0)
            gap_above = rt - row_bottoms.get(row_tops[i-1], 0) if i > 0 else rt
            print(f"  Row {i}: top={rt:.0f} bottom={rb:.0f} gap_above={gap_above:.0f}pt")

        # 7. Show words in the strip zones
        print(f"\n--- Words in EPIC strip zones (between card rows): ---")
        for i, rt in enumerate(row_tops):
            if i == 0:
                strip_top = max(0, rt - 80)
            else:
                strip_top = row_bottoms.get(row_tops[i-1], rt)
            strip_bottom = rt + 5  # just into the card top

            strip_words = [
                w for w in raw_words
                if float(w["top"]) >= strip_top and float(w["top"]) <= strip_bottom
            ]
            strip_words.sort(key=lambda w: (float(w["top"]), float(w["x0"])))

            if strip_words:
                texts = [f"'{w['text']}' ({float(w['x0']):.0f},{float(w['top']):.0f})" for w in strip_words]
                print(f"  Strip above row {i} ({strip_top:.0f}-{strip_bottom:.0f}): {' | '.join(texts)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python diagnose_epic.py <path_to_voter_pdf> [page_number]")
        sys.exit(1)

    pdf_path = sys.argv[1]
    page_num = int(sys.argv[2]) if len(sys.argv) > 2 else 7
    diagnose(pdf_path, page_num)
