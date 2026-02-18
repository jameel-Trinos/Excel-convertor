#!/usr/bin/env python3
"""Debug EPIC extraction from header strips of voter cards."""

import sys
import os
import re
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cv2
import pytesseract
from pdf2image import convert_from_path
from app.voters_pdf_processor import VotersPDFProcessor

_EPIC_RE = re.compile(r'\b([A-Z]{3}\d{7})\b')

def debug_epics(pdf_path: str, page_num: int = 4):
    """Debug EPIC extraction for cards on a specific page."""
    print(f"Converting page {page_num} to image...")
    images = convert_from_path(pdf_path, dpi=300, first_page=page_num, last_page=page_num)
    pil_img = images[0]

    img = np.array(pil_img)
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

    # Detect card grid
    card_bboxes = VotersPDFProcessor._detect_card_grid_from_image(gray)
    print(f"Detected {len(card_bboxes)} cards on page {page_num}")

    row_tops = sorted(set(c[1] for c in card_bboxes))
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))

    for idx, (x, y, w, h) in enumerate(card_bboxes):
        # Calculate header extension (same logic as in voters_pdf_processor.py)
        row_idx = row_tops.index(y) if y in row_tops else 0
        if row_idx == 0:
            header_extend = min(55, y - 5)
        else:
            prev_row_y = row_tops[row_idx - 1]
            prev_row_h = h
            for cx, cy, cw, ch in card_bboxes:
                if cy == prev_row_y:
                    prev_row_h = ch
                    break
            gap = y - (prev_row_y + prev_row_h)
            header_extend = min(int(gap * 0.9), y - 5) if gap > 10 else 55

        inset = 4
        y_start = max(0, y - header_extend)

        # Header strip only
        header_strip = gray[y_start:y, x + inset:x + w - inset]
        header_strip_h = y - y_start

        # Full card with header
        card_img = gray[y_start:y + h - inset, x + inset:x + w - inset]
        card_enhanced = clahe.apply(card_img)

        # PSM 6 on full card
        try:
            psm6_text = pytesseract.image_to_string(card_enhanced, lang="tam+eng", config="--oem 3 --psm 6")
            epic_psm6 = _EPIC_RE.search(psm6_text)
        except:
            psm6_text = ""
            epic_psm6 = None

        # PSM 7 on header strip (eng only)
        epic_psm7_eng = None
        if header_strip.size > 0 and header_strip_h > 15:
            header_enhanced = clahe.apply(header_strip)
            try:
                psm7_eng = pytesseract.image_to_string(header_enhanced, lang="eng", config="--oem 3 --psm 7")
                epic_psm7_eng = _EPIC_RE.search(psm7_eng)
            except:
                psm7_eng = ""
        else:
            psm7_eng = "(no strip)"

        # PSM 7 on header strip (tam+eng)
        epic_psm7_tam = None
        if header_strip.size > 0 and header_strip_h > 15:
            header_enhanced = clahe.apply(header_strip)
            try:
                psm7_tam = pytesseract.image_to_string(header_enhanced, lang="tam+eng", config="--oem 3 --psm 7")
                epic_psm7_tam = _EPIC_RE.search(psm7_tam)
            except:
                psm7_tam = ""
        else:
            psm7_tam = "(no strip)"

        # PSM 3 on full card
        try:
            psm3_text = pytesseract.image_to_string(card_enhanced, lang="tam+eng", config="--oem 3 --psm 3")
            epic_psm3 = _EPIC_RE.search(psm3_text)
        except:
            psm3_text = ""
            epic_psm3 = None

        # PSM 8 (single word) on header strip - eng only
        epic_psm8 = None
        if header_strip.size > 0 and header_strip_h > 15:
            header_enhanced = clahe.apply(header_strip)
            # Try with threshold to make text clearer
            _, header_bin = cv2.threshold(header_enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            try:
                psm8_text = pytesseract.image_to_string(header_bin, lang="eng", config="--oem 3 --psm 6")
                epic_psm8 = _EPIC_RE.search(psm8_text)
            except:
                psm8_text = ""
        else:
            psm8_text = "(no strip)"

        found_any = epic_psm6 or epic_psm7_eng or epic_psm7_tam or epic_psm3 or epic_psm8

        if not found_any:
            print(f"\n--- Card {idx+1} (row {row_idx}) - NO EPIC FOUND ---")
            print(f"  Header strip height: {header_strip_h}px, card: ({x},{y},{w},{h})")
            print(f"  PSM 7 eng: {repr(psm7_eng.strip()[:80])}")
            print(f"  PSM 7 tam: {repr(psm7_tam.strip()[:80])}")
            print(f"  PSM 8 bin: {repr(psm8_text.strip()[:80])}")
            print(f"  PSM 6 (first 80): {repr(psm6_text.strip()[:80])}")
            print(f"  PSM 3 (first 80): {repr(psm3_text.strip()[:80])}")
        else:
            epic_val = (epic_psm6 or epic_psm7_eng or epic_psm7_tam or epic_psm3 or epic_psm8).group(1)
            found_by = []
            if epic_psm6: found_by.append("PSM6")
            if epic_psm7_eng: found_by.append("PSM7-eng")
            if epic_psm7_tam: found_by.append("PSM7-tam")
            if epic_psm3: found_by.append("PSM3")
            if epic_psm8: found_by.append("PSM8-bin")
            print(f"  Card {idx+1} (row {row_idx}): EPIC={epic_val} via {', '.join(found_by)}")


if __name__ == "__main__":
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else "/Users/abc/Downloads/155-eroll/2026-EROLLGEN-S22-155-SIR-DraftRoll-Revision1-TAM-19-WI.pdf"
    page = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    debug_epics(pdf_path, page)
