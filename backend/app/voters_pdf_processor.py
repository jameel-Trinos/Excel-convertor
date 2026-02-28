"""Voter list PDF processor.

Extracts voter data from Indian electoral roll PDFs (Tamil + English).
Uses pdfplumber for text-based PDFs and pytesseract OCR for scanned/image PDFs.

Expected voter fields:
  Serial No, Name, Father/Husband Name, House No, Age, Gender, Voter ID (EPIC)

Also extracts header metadata:
  AC No, Booth No (Part No), Booth Address, Total Voters
"""

import logging
import os
import re
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np
import pdfplumber
from pdf2image import convert_from_path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Regex patterns for voter data extraction
# ---------------------------------------------------------------------------

# EPIC (voter ID) pattern: 3 uppercase letters followed by 7 digits
# Use lookaround instead of \b to handle Tamil characters adjacent to EPIC
_EPIC_RE = re.compile(r'(?<![A-Z])([A-Z]{3}\d{7})(?!\d)')

# Fuzzy EPIC pattern: OCR often reads digits as letters in the digit portion.
# Common OCR confusions: 0↔O, 1↔I/l, 4↔A, 5↔S, 6↔G, 8↔B
# Matches 3 uppercase letters followed by 7 alphanumeric chars (mostly digits)
_EPIC_FUZZY_RE = re.compile(r'(?<![A-Z])([A-Z]{3}[0-9A-Za-z]{7})(?![0-9A-Za-z])')

# OCR-tolerant EPIC pattern: $ is commonly misread as S, so match
# patterns like $SL1234567, S$SL1234567, $8L1234567 etc.
_EPIC_OCR_TOLERANT_RE = re.compile(r'[\$S]{1,2}([A-Z$]{2}\d{7})')


_OCR_LETTER_TO_DIGIT = str.maketrans('OoIlTtASGBZb', '001114568820')


def _fix_ocr_epic(text: str) -> str:
    """Fix common OCR misreads in text before EPIC extraction.

    Handles:
    - $ misread as S: $SL → SSL
    - S$SL prefix bloat: SSSL → SSL
    - Spurious O/o duplication: SSLO0957704 → SSL0957704 (OCR reads 0 as O AND keeps 0)
    - 4-letter prefix where 4th char is a misread digit: NNKT099068 → NNK1099068
    """
    text = text.replace('$', 'S')
    # Collapse runs like SSSL → SSL (OCR doubling the S prefix)
    text = re.sub(r'S{2,}([A-Z]\d{7})', r'SS\1', text)
    # Fix OCR duplication: 0 misread as O while original 0 is also kept,
    # producing 11-char strings like SSLO0957704 instead of SSL0957704.
    text = re.sub(r'([A-Z]{3})[Oo](\d{7})\b', r'\g<1>\2', text)
    # Fix 4-letter EPIC prefix where the 4th letter is a misread digit.
    # e.g. NNKT099068 → NNK1099068 (T misread as 1)
    def _fix_4letter_prefix(m: re.Match) -> str:
        prefix3 = m.group(1)
        misread_char = m.group(2)
        digits6 = m.group(3)
        fixed_digit = misread_char.translate(_OCR_LETTER_TO_DIGIT)
        if fixed_digit.isdigit():
            return prefix3 + fixed_digit + digits6
        return m.group(0)  # can't fix, return as-is
    text = re.sub(r'([A-Z]{3})([A-Za-z])(\d{6})\b', _fix_4letter_prefix, text)
    return text


def _normalize_epic(raw: str) -> str:
    """Normalize a fuzzy EPIC match by fixing common OCR digit substitutions."""
    prefix = raw[:3]  # 3 letters — keep as-is
    digits = raw[3:]  # 7 chars that should be digits
    # Replace common OCR misreads in digit portion
    _OCR_DIGIT_MAP = str.maketrans('OIlASGBZb', '011456820')
    digits = digits.translate(_OCR_DIGIT_MAP)
    # Only accept if result is all digits
    if digits.isdigit():
        return prefix + digits
    return ""

# Age pattern: 1-3 digit number (we filter 18-120 later)
_AGE_RE = re.compile(r'\b(\d{1,3})\b')

# Gender patterns (English + Tamil)
_GENDER_MALE = re.compile(r'(?<![a-zA-Z\u0B80-\u0BFF])(Male|ஆண்|M)(?![a-zA-Z\u0B80-\u0BFF])', re.IGNORECASE)
_GENDER_FEMALE = re.compile(r'(?<![a-zA-Z\u0B80-\u0BFF])(Female|பெண்|F)(?![a-zA-Z\u0B80-\u0BFF])', re.IGNORECASE)
_GENDER_OTHER = re.compile(r'(?<![a-zA-Z\u0B80-\u0BFF])(மூன்றாம்\s*பாலினம்|O)(?![a-zA-Z\u0B80-\u0BFF])', re.IGNORECASE)

# Serial number at start of a voter entry
_SERIAL_RE = re.compile(r'^\s*(\d{1,4})\s')

# AC / Part number patterns (handles both English and Tamil OCR variants)
_AC_NO_RE = re.compile(
    r'(?:'
    r'AC\s*No[:\s]*(\d+)'
    r'|சட்டமன்றத்\s*தொகுதி(?:யின்)?\s*எண்[.\s]*.*?(?:நிலை\s*)?:\s*(\d+)'
    r'|constituency\s*no[:\s]*(\d+)'
    r')',
    re.IGNORECASE,
)
_PART_NO_RE = re.compile(
    r'(?:'
    r'Part\s*No[:\s]*(\d+)'
    r'|பகுதி\s*எண்[:\s]*(\d+)'
    r'|Booth\s*No[:\s]*(\d+)'
    r'|பாகம்\s*எண்\s*:\s*(\d+)'
    r'|சாவடியின்\s*எண்[:\s]*(\d+)'
    r')',
    re.IGNORECASE,
)
_TOTAL_VOTERS_RE = re.compile(
    r'(?:'
    r'Total\s*(?:Electors|Voters)'
    r'|மொத்த\s*வாக்காளர்கள்'
    r'|மொத்தம்'
    r')[:\s]*(\d+)',
    re.IGNORECASE,
)

# Deleted voter detection: cards marked with "DELETED" watermark/stamp only
_DELETED_RE = re.compile(
    r'\bDELETED\b|\bD\s*E\s*L\s*E\s*T\s*E\s*D\b|நீக்கப்பட்டது',
    re.IGNORECASE,
)

# Address label pattern — matches "வாக்குச் சாவடியின் முகவரி" and English variants
# The address text follows the label after a colon (same line or next line)
_ADDRESS_LABEL_RE = re.compile(
    r'(?:'
    r'வாக்குச்\s*சாவடியின்\s*முகவரி'
    r'|Polling\s*Station\s*Address'
    r'|Address\s*of\s*(?:the\s*)?Polling\s*Station'
    r'|சாவடி\s*முகவரி'
    r')\s*[:：]?\s*(.*)',
    re.IGNORECASE,
)

# Section name / street name pattern — per page header
# Matches: "பிரிவு எண் மற்றும் பெயர்" followed by the section/street text
_SECTION_NAME_RE = re.compile(
    r'(?:'
    r'பிரிவு\s*எண்\s*மற்றும்\s*பெயர்'
    r'|Section\s*(?:Number|No\.?)\s*(?:and|&)\s*Name'
    r')\s*[:：]?\s*(.*)',
    re.IGNORECASE,
)

# Tamil field label patterns for splitting concatenated voter text
_NAME_LABEL_RE = re.compile(
    r'(?:பெயர்\s*:|Name\s*:|Elector\s*Name\s*:)', re.IGNORECASE
)
_FATHER_LABEL_RE = re.compile(
    r'(?:தந்தை(?:யின்)?\s*பெயர்\s*:|கணவர்\s*பெயர்\s*:|'
    r"Father(?:'s)?\s*Name\s*:|Husband(?:'s)?\s*Name\s*:|"
    r'F/H\s*Name\s*:|S/W/D\s*of\s*:|Relation\s*Name\s*:)',
    re.IGNORECASE,
)
_HOUSE_LABEL_RE = re.compile(
    r'(?:வீட்டு\s*எண்\s*:|House\s*No\s*:?|H\.?No\s*:?)', re.IGNORECASE
)
_AGE_LABEL_RE = re.compile(
    r'(?:வயது\s*:|Age\s*:)', re.IGNORECASE
)
_GENDER_LABEL_RE = re.compile(
    r'(?:பாலினம்\s*:|Gender\s*:)', re.IGNORECASE
)
# Photo marker often appears between voter entries
_PHOTO_MARKER_RE = re.compile(r'Photo\s+is', re.IGNORECASE)

# Zero-width Unicode characters that Tamil OCR commonly inserts
_ZW_CHARS = re.compile(r'[\u200b\u200c\u200d\ufeff]')


def _strip_zw(text: str) -> str:
    """Remove zero-width Unicode characters (ZWJ, ZWNJ, ZWSP, BOM)."""
    return _ZW_CHARS.sub('', text)


# ---------------------------------------------------------------------------
# Spatial helpers
# ---------------------------------------------------------------------------

def _cluster_positions(positions: list[float], tolerance: float = 5.0) -> list[float]:
    """Cluster nearby coordinate values, returning representative (mean) positions.

    Used to find column/row boundaries from scattered line coordinates.
    Same pattern as GridLineDetector._cluster_lines() in grid_ocr_processor.py.
    """
    if not positions:
        return []

    sorted_pos = sorted(positions)
    clusters: list[float] = []
    current_cluster = [sorted_pos[0]]

    for pos in sorted_pos[1:]:
        if pos - current_cluster[-1] <= tolerance:
            current_cluster.append(pos)
        else:
            clusters.append(sum(current_cluster) / len(current_cluster))
            current_cluster = [pos]

    clusters.append(sum(current_cluster) / len(current_cluster))
    return clusters


def _words_to_text(words: list[dict], line_tolerance: float = 3.0) -> str:
    """Reconstruct text from pdfplumber word dicts, grouped into lines.

    Words with similar ``top`` values (within tolerance) are placed on the
    same line, sorted left-to-right and joined with spaces.  Lines are
    joined with newlines.

    The tolerance adapts to 30% of median word height (floored at the
    default) so that larger fonts don't cause same-line words to split
    into separate lines.
    """
    if not words:
        return ""

    # Adaptive tolerance based on actual word heights in this card
    heights = [w["bottom"] - w["top"] for w in words
               if w.get("bottom") is not None and w.get("top") is not None]
    if heights:
        median_h = sorted(heights)[len(heights) // 2]
        adaptive_tol = max(line_tolerance, median_h * 0.30)
    else:
        adaptive_tol = line_tolerance

    sorted_words = sorted(words, key=lambda w: (w["top"], w["x0"]))
    lines: list[list[dict]] = []
    current_line: list[dict] = [sorted_words[0]]
    for w in sorted_words[1:]:
        if abs(w["top"] - current_line[0]["top"]) <= adaptive_tol:
            current_line.append(w)
        else:
            lines.append(current_line)
            current_line = [w]
    lines.append(current_line)
    text_lines: list[str] = []
    for line in lines:
        line.sort(key=lambda w: w["x0"])
        text_lines.append(" ".join(w["text"] for w in line))
    return "\n".join(text_lines)


class VoterRecord:
    """A single voter entry."""

    def __init__(
        self,
        serial_no: str = "",
        name: str = "",
        father_husband_name: str = "",
        house_no: str = "",
        age: str = "",
        gender: str = "",
        voter_id: str = "",
        street_name: str = "",
        relation_type: str = "",
    ):
        self.serial_no = serial_no
        self.name = name
        self.father_husband_name = father_husband_name
        self.house_no = house_no
        self.age = age
        self.gender = gender
        self.voter_id = voter_id
        self.street_name = street_name
        self.relation_type = relation_type  # "F" = Father, "H" = Husband
        self.is_deleted = False

    def to_row(self) -> list[str]:
        return [
            self.serial_no,
            self.name,
            self.father_husband_name,
            self.relation_type,
            self.house_no,
            self.age,
            self.gender,
            self.voter_id,
            self.street_name,
        ]

    @property
    def is_valid(self) -> bool:
        """Minimal validity: must have at least a name or voter ID."""
        return bool(self.name.strip() or self.voter_id.strip())


class VoterHeaderInfo:
    """Metadata extracted from the voter list header."""

    def __init__(self):
        self.ac_no: str = ""
        self.part_no: str = ""  # booth number
        self.address: str = ""
        self.total_voters: str = ""


class VotersPDFProcessor:
    """Extract voter records from an electoral roll PDF."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.header_info = VoterHeaderInfo()
        self.voters: list[VoterRecord] = []
        self._is_scanned = False
        self._learned_img_grid: list[tuple[int, int, int, int]] = []
        self._deleted_voter_count = 0

    @staticmethod
    def _detect_relation_type(text: str) -> str:
        """Detect relation type from label text.

        Returns 'H' if Husband/கணவர், 'F' if Father/தந்தை/Mother/Other,
        '' if unknown.
        """
        # Check S/W/D first — it contains both Wife (H) and Son/Daughter (F)
        # In Indian voter rolls "S/W/D of" typically precedes father's name
        # so default to "F" for this pattern
        if re.search(r'S/W/D', text, re.IGNORECASE):
            return "F"
        # Husband — specific keywords
        if re.search(r'கணவ[ர்]?|Husband|Wife\b', text, re.IGNORECASE):
            return "H"
        # Father / Mother / Other — all parent/guardian relations → "F"
        # Also catches OCR-garbled forms like தந்த ன் (truncated தந்தையின்)
        if re.search(r'தந்த|தாயின்|இதர(?:ர்)?|Father|Mother|Guardian|Son\b|Daughter\b', text, re.IGNORECASE):
            return "F"
        return ""

    def extract(
        self,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> dict[str, Any]:
        """
        Extract voter data from PDF.

        Returns dict with keys: header_info, voters (list of row lists),
        headers, total_pages.
        """
        path = Path(self.file_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {self.file_path}")

        if progress_callback:
            progress_callback(5, "Opening PDF...")

        # Early detection: quick probe of first few pages to determine text vs scanned PDF.
        # This avoids wasting time on strategies that will fail.
        # Check up to 3 pages (some PDFs have a text cover page but scanned data pages).
        is_text_pdf = False
        try:
            with pdfplumber.open(str(path)) as probe_pdf:
                total_pages = len(probe_pdf.pages)
                total_probe_text = 0
                pages_to_check = min(3, total_pages)
                for pi in range(pages_to_check):
                    probe_text = probe_pdf.pages[pi].extract_text() or ""
                    total_probe_text += len(probe_text.strip())
                is_text_pdf = total_probe_text >= 200
        except Exception:
            total_pages = 0

        if is_text_pdf:
            # Fast-track: text-based PDF — try text strategies first
            spatial_voters, total_pages, first_page_text = self._extract_via_spatial_cards(
                path, progress_callback
            )
            if spatial_voters:
                self.voters = spatial_voters
                if first_page_text:
                    self._parse_header(first_page_text)
            else:
                table_voters, total_pages, first_page_text = self._extract_via_tables(
                    path, progress_callback
                )
                if table_voters:
                    self.voters = table_voters
                    if first_page_text:
                        self._parse_header(first_page_text)
                else:
                    # Text extraction + parsing (no OCR needed for text PDFs)
                    text_pages = self._extract_text(path)
                    if not self.voters:
                        total_pages = len(text_pages)
                        if progress_callback:
                            progress_callback(30, f"Parsing {total_pages} pages...")
                        for hp in text_pages[:5]:
                            if hp:
                                self._parse_header(hp)
                                if self.header_info.ac_no and self.header_info.part_no:
                                    break
                        for i, page_text in enumerate(text_pages):
                            page_voters = self._parse_voters_from_text(page_text)
                            # Assign per-page section/street name
                            page_section_name = self._extract_section_name(page_text)
                            if page_section_name:
                                for v in page_voters:
                                    v.street_name = page_section_name
                            self.voters.extend(page_voters)
                            if progress_callback:
                                pct = 30 + int((i + 1) / max(total_pages, 1) * 50)
                                progress_callback(pct, f"Parsed page {i + 1}/{total_pages} ({len(self.voters)} voters found)")
        else:
            # Scanned/image PDF — go straight to OCR strategies
            logger.info("Scanned PDF detected, skipping text-based strategies")
            self._is_scanned = True

            # Strategy 1: Image-based card-by-card OCR (most accurate for grid layouts)
            card_ocr_voters, total_pages = self._extract_via_image_card_ocr(
                path, progress_callback
            )
            if card_ocr_voters:
                self.voters = card_ocr_voters
            else:
                # Strategy 2: Whole-page OCR fallback
                logger.info("Card OCR failed, falling back to whole-page OCR")
                text_pages = self._ocr_extract(path, progress_callback)
                total_pages = len(text_pages)

                if progress_callback:
                    progress_callback(30, f"Parsing {total_pages} pages...")

                for hp in text_pages[:5]:
                    if hp:
                        self._parse_header(hp)
                        if self.header_info.ac_no and self.header_info.part_no:
                            break

                epic_maps = getattr(self, '_page_epic_maps', [])
                for i, page_text in enumerate(text_pages):
                    epic_map = epic_maps[i] if i < len(epic_maps) else {}
                    page_voters = self._parse_voters_from_text(page_text, epic_map)
                    # Assign per-page section/street name
                    page_section_name = self._extract_section_name(page_text)
                    if page_section_name:
                        for v in page_voters:
                            v.street_name = page_section_name
                    self.voters.extend(page_voters)
                    if progress_callback:
                        pct = 30 + int((i + 1) / max(total_pages, 1) * 50)
                        progress_callback(pct, f"Parsed page {i + 1}/{total_pages} ({len(self.voters)} voters found)")

        # Filter out deleted/struck-off voters (safety net — most are caught earlier)
        deleted_count = sum(1 for v in self.voters if v.is_deleted)
        if deleted_count > 0:
            logger.info(f"[DELETED FILTER] Removing {deleted_count} deleted voters")
            self.voters = [v for v in self.voters if not v.is_deleted]
        # Track total deleted for reconciliation (includes those skipped at card level)
        self._deleted_voter_count = getattr(self, '_deleted_voter_count', 0) + deleted_count

        # Filter out false-positive voters (header/metadata misidentified as voter)
        pre_filter_count = len(self.voters)
        dropped_voters = [v for v in self.voters if self._is_false_positive_voter(v)]
        for dv in dropped_voters:
            logger.warning(
                f"[FALSE-POS FILTER] Dropped: name='{dv.name}' "
                f"father='{dv.father_husband_name}' house='{dv.house_no}' "
                f"age='{dv.age}' gender='{dv.gender}' voter_id='{dv.voter_id}'"
            )
        self.voters = [
            v for v in self.voters
            if not self._is_false_positive_voter(v)
        ]
        # Clean OCR artifacts from names of kept voters (stray |, }, {, [ chars)
        for v in self.voters:
            if v.name:
                v.name = re.sub(r'[{}\[\]|]', '', v.name).strip().rstrip(' -.:;')
                # Strip header metadata that leaked into voter names
                # (e.g., "1-அரியலூர் (0" → strip the "1-அரியலூர் (0" prefix)
                v.name = re.sub(r'^\d+\s*[-–]\s*[\u0B80-\u0BFF]+.*?\)\s*', '', v.name).strip()
                v.name = re.sub(r'^\d+\s*[-–]\s*[\u0B80-\u0BFF]+\s*\(.*$', '', v.name).strip()
                # Clear garbage OCR names: pure short lowercase ASCII or single chars
                if re.fullmatch(r'[a-z]{1,5}', v.name) or len(v.name) <= 1:
                    v.name = ""
            if v.father_husband_name:
                v.father_husband_name = re.sub(r'[{}\[\]|]', '', v.father_husband_name).strip().rstrip(' -.:;')
        # For voters whose name became empty after cleaning but have EPIC, use EPIC as name
        for v in self.voters:
            if (not v.name or not v.name.strip()) and v.voter_id:
                v.name = v.voter_id
                logger.info(f"[NAME-RECOVERY] Voter with empty name but EPIC {v.voter_id} — using EPIC as name")
        # Only remove voters that have BOTH empty name AND empty voter_id
        self.voters = [v for v in self.voters if (v.name and v.name.strip()) or v.voter_id]
        logger.info(f"[FILTER STATS] Before={pre_filter_count}, After={len(self.voters)}, Dropped={pre_filter_count - len(self.voters)}")

        # Re-number serial numbers sequentially
        for i, voter in enumerate(self.voters, 1):
            voter.serial_no = str(i)

        # Normalize gender to short form: M / F / O
        for voter in self.voters:
            g = voter.gender.strip().lower()
            if g in ("male", "m", "ஆண்"):
                voter.gender = "M"
            elif g in ("female", "f", "பெண்"):
                voter.gender = "F"
            elif g in ("மூன்றாம் பாலினம்", "மூன்றாம்பாலினம்", "o"):
                voter.gender = "O"
            elif g:
                voter.gender = "O"

        # Store expected total from header before overwriting
        expected_total = self.header_info.total_voters
        extracted_total = str(len(self.voters))

        # Update total voters from actual count if header didn't have it
        if not self.header_info.total_voters and self.voters:
            self.header_info.total_voters = extracted_total

        # Reconciliation: compare expected vs extracted (accounting for deleted voters)
        deleted_total = self._deleted_voter_count
        if expected_total and expected_total.isdigit() and self.voters:
            expected_int = int(expected_total)
            extracted_int = len(self.voters)
            epic_count = sum(1 for v in self.voters if v.voter_id)
            # The header total includes deleted voters, so adjust expected
            expected_after_deleted = expected_int - deleted_total
            if deleted_total > 0:
                logger.info(
                    f"[RECONCILIATION] {deleted_total} deleted voters removed. "
                    f"Header total: {expected_int}, After deletion: {expected_after_deleted}"
                )
            if expected_after_deleted != extracted_int:
                logger.warning(
                    f"[RECONCILIATION] Expected {expected_after_deleted} voters "
                    f"(header={expected_int} minus {deleted_total} deleted), "
                    f"extracted {extracted_int} — "
                    f"{expected_after_deleted - extracted_int} missing! "
                    f"EPIC fill rate: {epic_count}/{extracted_int}"
                )
            else:
                logger.info(
                    f"[RECONCILIATION] All {expected_after_deleted} voters extracted successfully "
                    f"({deleted_total} deleted excluded). "
                    f"EPIC fill rate: {epic_count}/{extracted_int}"
                )

        if progress_callback:
            progress_callback(85, f"Extraction complete: {len(self.voters)} voters")

        headers = [
            "Serial No", "Name", "Father/Husband Name",
            "Relation Type", "House No", "Age", "Gender", "Voter ID",
            "Street Name",
        ]

        return {
            "header_info": self.header_info,
            "voters": [v.to_row() for v in self.voters],
            "headers": headers,
            "total_pages": total_pages,
            "expected_total": expected_total,
            "extracted_total": extracted_total,
            "deleted_count": self._deleted_voter_count,
        }

    # ------------------------------------------------------------------
    # Spatial card extraction (pdfplumber rects/edges + crop)
    # ------------------------------------------------------------------

    def _extract_via_spatial_cards(
        self,
        path: Path,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> tuple[list["VoterRecord"], int, str]:
        """Extract voter data by detecting card boundaries and cropping each card.

        Tamil Nadu electoral roll PDFs use a 3-column card layout. This method
        detects the bordered rectangles using page.rects / page.edges, crops
        each card individually, and extracts text from it.

        Returns (voters, total_pages, first_page_text) or ([], 0, "") on failure.
        """
        voters: list[VoterRecord] = []
        first_page_text = ""
        learned_grid: Optional[dict] = None  # reuse grid geometry across pages
        all_page_texts: list[str] = []  # for quality gate EPIC count

        try:
            with pdfplumber.open(str(path)) as pdf:
                total_pages = len(pdf.pages)

                if progress_callback:
                    progress_callback(8, f"Detecting voter cards on {total_pages} pages...")

                for page_idx, page in enumerate(pdf.pages):
                    # Get plain text for header parsing and EPIC counting
                    page_text = page.extract_text() or ""
                    all_page_texts.append(page_text)
                    # Collect text from early pages for header parsing
                    # (covers, signature pages, maps may precede voter data)
                    if page_idx < 4:
                        first_page_text += ("\n" + page_text) if first_page_text else page_text

                    # Extract section/street name for this page
                    page_section_name = self._extract_section_name(page_text)

                    # Detect card bounding boxes
                    card_bboxes = self._detect_card_grid(page)

                    # If this page has no cards but we learned grid from a previous page,
                    # try applying the learned geometry
                    if not card_bboxes and learned_grid is not None:
                        card_bboxes = self._apply_learned_grid(page, learned_grid)

                    if not card_bboxes:
                        # Allow first few pages to be non-card pages (cover, maps, etc.)
                        # Only give up if we've checked enough pages without finding any cards
                        if page_idx >= 5 and not voters and learned_grid is None:
                            logger.info("No voter card grid detected in first 6 pages, skipping spatial strategy")
                            return [], 0, ""
                        continue

                    # Learn grid geometry from first successful page
                    if learned_grid is None and len(card_bboxes) >= 3:
                        xs = sorted(set(b[0] for b in card_bboxes) | set(b[2] for b in card_bboxes))
                        heights = [b[3] - b[1] for b in card_bboxes]
                        learned_grid = {
                            "v_boundaries": _cluster_positions(xs, tolerance=5.0),
                            "avg_card_height": sum(heights) / len(heights),
                        }

                    # Build row-top lookup to compute header extension per card.
                    # The EPIC voter ID and serial number are printed ABOVE each
                    # card box, in the strip between the previous row's bottom
                    # and the current card's top. We must extend the crop upward
                    # to capture the EPIC.
                    row_tops_sorted = sorted(set(round(b[1], 0) for b in card_bboxes))
                    row_bottoms: dict[float, float] = {}
                    for b in card_bboxes:
                        rt = round(b[1], 0)
                        row_bottoms[rt] = max(row_bottoms.get(rt, 0), b[3])

                    def _header_extend(card_top: float) -> float:
                        """Compute how far above card_top to extend for EPIC strip."""
                        rt = round(card_top, 0)
                        ri = row_tops_sorted.index(rt) if rt in row_tops_sorted else -1
                        if ri <= 0:
                            # First row: extend up to 80pt (EPIC strip above first row)
                            return min(80.0, card_top - 2)
                        prev_bottom = row_bottoms.get(row_tops_sorted[ri - 1], card_top)
                        gap = card_top - prev_bottom
                        # Extend by full gap + 10pt buffer (captures EPIC strip reliably)
                        return max(0.0, gap + 10)

                    # --- Extract all words from the page once for accurate text
                    #     reconstruction and EPIC position matching ---
                    try:
                        raw_words = page.extract_words(
                            keep_blank_chars=False,
                            x_tolerance=5,   # Group chars within 5pt horizontally
                            y_tolerance=5,   # Group chars within 5pt vertically
                        )
                        # Pre-convert to float once for fast filtering
                        page_words = []
                        for pw in raw_words:
                            page_words.append({
                                "text": pw.get("text", ""),
                                "x0": float(pw["x0"]),
                                "x1": float(pw["x1"]),
                                "top": float(pw["top"]),
                                "bottom": float(pw["bottom"]),
                            })
                    except Exception:
                        page_words = []

                    # --- Detect "DELETED" words with positions ---
                    # Deleted voter cards have "DELETED" text overlaid.
                    # Also check page.chars for rotated/diagonal DELETED text
                    # that extract_words() may miss.
                    deleted_card_zones: list[tuple[float, float, float, float]] = []
                    # Check extract_words result
                    for pw in page_words:
                        if _DELETED_RE.search(pw["text"]):
                            deleted_card_zones.append((
                                pw["x0"], pw["top"], pw["x1"], pw["bottom"]
                            ))
                    # Also check page.chars for DELETED (catches rotated text)
                    if not deleted_card_zones:
                        try:
                            chars = page.chars
                            for ci_c, ch in enumerate(chars):
                                ch_text = ch.get("text", "")
                                if ch_text.upper() != "D":
                                    continue
                                # Try to form "DELETED" from consecutive chars
                                seq_chars = []
                                for offset in range(7):
                                    idx = ci_c + offset
                                    if idx < len(chars):
                                        seq_chars.append(chars[idx])
                                seq_text = ''.join(
                                    c.get('text', '') for c in seq_chars
                                )
                                if seq_text.upper() == "DELETED":
                                    # Use bounding box of the full word
                                    d_x0 = min(c.get('x0', 0) for c in seq_chars)
                                    d_top = min(c.get('top', 0) for c in seq_chars)
                                    d_x1 = max(c.get('x1', 0) for c in seq_chars)
                                    d_bot = max(c.get('bottom', 0) for c in seq_chars)
                                    deleted_card_zones.append((d_x0, d_top, d_x1, d_bot))
                        except Exception:
                            pass
                    # Also check full page text
                    if not deleted_card_zones and _DELETED_RE.search(page_text):
                        # DELETED is in the page text but we couldn't locate it
                        # spatially. Flag entire page for card-level text checking.
                        pass

                    # --- Collect ALL EPICs from the full page text ---
                    # Using full page text is more reliable than word-level
                    # matching because EPICs may be concatenated with serial
                    # numbers or split across word boundaries.
                    all_page_epics_ordered: list[str] = []
                    if page_text:
                        # Extract EPICs from the full page text (preserves reading order)
                        for m in _EPIC_RE.finditer(page_text):
                            epic_val = m.group(1)
                            if epic_val not in all_page_epics_ordered:
                                all_page_epics_ordered.append(epic_val)
                        # Also try fuzzy matching for OCR-garbled EPICs
                        for fm in _EPIC_FUZZY_RE.finditer(page_text):
                            raw = fm.group(1)
                            if _EPIC_RE.match(raw):
                                continue  # Already captured by strict pattern
                            norm = _normalize_epic(raw)
                            if norm and norm not in all_page_epics_ordered:
                                all_page_epics_ordered.append(norm)

                    # Also build word-level EPIC list for positional matching
                    page_epic_words: list[dict] = []
                    for pw in page_words:
                        pw_text = pw["text"]
                        m = _EPIC_RE.search(pw_text)
                        if m:
                            page_epic_words.append({
                                "epic": m.group(1),
                                "x0": pw["x0"],
                                "x1": pw["x1"],
                                "top": pw["top"],
                            })
                        else:
                            fm = _EPIC_FUZZY_RE.search(pw_text)
                            if fm:
                                norm = _normalize_epic(fm.group(1))
                                if norm:
                                    page_epic_words.append({
                                        "epic": norm,
                                        "x0": pw["x0"],
                                        "x1": pw["x1"],
                                        "top": pw["top"],
                                    })

                    # --- Build serial-number → EPIC mapping ---
                    # In voter rolls, serial number and EPIC appear together
                    # in the strip above each card: "7 SSL1183771" or nearby.
                    # Use word positions to pair serial numbers with EPICs.
                    serial_to_epic: dict[int, str] = {}
                    if page_epic_words:
                        # Find serial number words (1-4 digit numbers)
                        serial_words = [
                            pw for pw in page_words
                            if re.fullmatch(r'\d{1,4}', pw["text"])
                            and 1 <= int(pw["text"]) <= 2000
                        ]
                        for sw in serial_words:
                            serial_num = int(sw["text"])
                            # Find closest EPIC word on the same horizontal line
                            # (within 12pt vertical tolerance for slight misalignment)
                            for ew in page_epic_words:
                                if abs(ew["top"] - sw["top"]) < 12:
                                    serial_to_epic[serial_num] = ew["epic"]
                                    break

                    # Supplement serial-to-EPIC from page text patterns
                    # Catches cases where word-level extraction misses the pairing
                    if page_text:
                        for sm in re.finditer(r'(?:^|\s)(\d{1,4})\s+([A-Z]{3}\d{7})(?:\s|$)', page_text, re.MULTILINE):
                            sn = int(sm.group(1))
                            epic = sm.group(2)
                            if 1 <= sn <= 2000 and sn not in serial_to_epic:
                                serial_to_epic[sn] = epic

                    logger.info(
                        f"[SPATIAL] Page {page_idx+1}: found {len(all_page_epics_ordered)} EPICs "
                        f"in full text, {len(page_epic_words)} with word positions, "
                        f"{len(serial_to_epic)} serial-to-EPIC pairs"
                    )

                    # Extract text from each card using word-level reconstruction
                    page_voters: list[VoterRecord] = []
                    card_positions: list[tuple[float, float, float, float]] = []
                    skipped_cards: list[str] = []  # track skipped card texts for retry
                    used_epics: set[str] = set()

                    for x0, top, x1, bottom in card_bboxes:
                        # Extend crop UPWARD to capture EPIC voter ID printed
                        # above the card box
                        extend_up = _header_extend(top)
                        crop_top = max(0, top - extend_up)

                        # --- Word-based text reconstruction ---
                        # Use page_words to build card text instead of
                        # page.crop().extract_text() which can split words
                        # at crop boundaries and garble Tamil names.
                        # Use overlap-based filtering: a word belongs to a card
                        # if its horizontal center falls within the card column
                        # (tolerant of words that start/end slightly outside).
                        x0_lo = x0 - 8
                        x1_hi = x1 + 8
                        bot_hi = bottom + 2
                        card_words = [
                            w for w in page_words
                            if (w["x0"] + w["x1"]) / 2 >= x0_lo
                            and (w["x0"] + w["x1"]) / 2 <= x1_hi
                            and w["top"] >= crop_top
                            and w["bottom"] <= bot_hi
                        ]
                        # Also grab any EPIC-containing words in a wider zone
                        # (EPICs may be positioned slightly outside the card column)
                        epic_zone_words = [
                            w for w in page_words
                            if _EPIC_RE.search(w["text"])
                            and w["top"] >= crop_top - 10
                            and w["top"] <= top + 30
                            and (w["x0"] + w["x1"]) / 2 >= x0 - 25
                            and (w["x0"] + w["x1"]) / 2 <= x1 + 25
                        ]
                        # Add any EPIC words not already in card_words
                        card_word_ids = {(round(w["x0"], 1), round(w["top"], 1)) for w in card_words}
                        for ew in epic_zone_words:
                            if (round(ew["x0"], 1), round(ew["top"], 1)) not in card_word_ids:
                                card_words.append(ew)

                        card_text = _words_to_text(card_words)

                        # If word-based extraction gives too little text,
                        # fall back to crop-based extraction
                        if len(card_text.strip()) < 5:
                            try:
                                cropped = page.crop(
                                    (x0 + 2, crop_top, x1 - 2, bottom - 2),
                                    strict=False,
                                )
                                card_text = cropped.extract_text() or ""
                            except Exception:
                                continue

                        if len(card_text.strip()) < 5:
                            continue

                        # Card must contain voter-like content to be valid
                        has_name_field = bool(
                            re.search(r'பெயர்\s*:?|Name\s*:', card_text, re.IGNORECASE)
                        )
                        has_age_gender = bool(
                            re.search(r'வயது\s*:?|Age\s*:?|பாலினம்\s*:?|Gender\s*:?', card_text, re.IGNORECASE)
                        )
                        has_epic = bool(_EPIC_RE.search(card_text))
                        tamil_chars = len(re.findall(r'[\u0B80-\u0BFF]', card_text))

                        # Accept card if it has any voter-like content:
                        # name+age/gender, name+EPIC, EPIC+age, or just name label with Tamil text
                        has_voter_fields = (has_name_field and has_age_gender) or \
                                           (has_name_field and has_epic) or \
                                           (has_epic and has_age_gender) or \
                                           (has_name_field and tamil_chars >= 3)

                        if not has_voter_fields:
                            if has_epic or has_name_field or tamil_chars >= 5:
                                skipped_cards.append(card_text)
                            continue

                        # Skip deleted/struck-off voters
                        # 1. Check card text for "DELETED" keyword
                        # 2. Check if card overlaps a detected DELETED zone
                        is_del = self._is_deleted_voter_card(card_text)
                        if not is_del and deleted_card_zones:
                            for dz_x0, dz_top, dz_x1, dz_bot in deleted_card_zones:
                                # Require the CENTER of the DELETED zone to fall
                                # within this card — prevents a stamp on one card
                                # from bleeding into a neighboring card's bbox.
                                dz_cx = (dz_x0 + dz_x1) / 2
                                dz_cy = (dz_top + dz_bot) / 2
                                if (x0 <= dz_cx <= x1 and top <= dz_cy <= bottom):
                                    is_del = True
                                    break
                        if is_del:
                            self._deleted_voter_count += 1
                            logger.info(
                                f"[SPATIAL] Page {page_idx+1}: "
                                f"DELETED voter skipped — text: {card_text[:80]!r}"
                            )
                            continue

                        voter = self._extract_voter_from_segment(card_text)

                        # Log card text for debugging EPIC issues
                        _card_idx = len(page_voters)
                        if not voter.voter_id:
                            logger.debug(
                                f"[EPIC-DEBUG] Page {page_idx+1} card {_card_idx} "
                                f"serial={voter.serial_no!r} NO EPIC from segment. "
                                f"card_bbox=({x0:.0f},{top:.0f},{x1:.0f},{bottom:.0f}) "
                                f"crop_top={crop_top:.0f} extend_up={extend_up:.0f}\n"
                                f"  card_text first 200 chars: {card_text[:200]!r}"
                            )

                        # --- Multi-strategy EPIC extraction ---
                        # Strategy A: Serial-to-EPIC mapping (most reliable)
                        if not voter.voter_id and voter.serial_no:
                            try:
                                sn = int(voter.serial_no)
                                if sn in serial_to_epic:
                                    epic_candidate = serial_to_epic[sn]
                                    if epic_candidate not in used_epics:
                                        voter.voter_id = epic_candidate
                            except ValueError:
                                pass

                        # Strategy B: Word-level positional matching
                        if not voter.voter_id:
                            for ew in page_epic_words:
                                if ew["epic"] in used_epics:
                                    continue
                                # Horizontal: EPIC word center must fall within the card column
                                ew_cx = (ew["x0"] + ew["x1"]) / 2
                                if ew_cx >= x0 - 10 and ew_cx <= x1 + 10:
                                    # Vertical: EPIC is in the strip above the card
                                    # or at the very top of the card
                                    if ew["top"] >= crop_top - 15 and ew["top"] <= top + 25:
                                        voter.voter_id = ew["epic"]
                                        break

                        # Strategy C: Try crop-based text for EPIC only
                        # Widen the crop area to capture EPICs that may be
                        # slightly outside the card column or further into the gap
                        if not voter.voter_id:
                            try:
                                cropped = page.crop(
                                    (max(0, x0 - 15), max(0, crop_top - 5), min(float(page.width), x1 + 15), top + 25),
                                    strict=False,
                                )
                                strip_text = cropped.extract_text() or ""
                                epic_m = _EPIC_RE.search(strip_text)
                                if epic_m and epic_m.group(1) not in used_epics:
                                    voter.voter_id = epic_m.group(1)
                                elif not epic_m:
                                    fuzzy_m = _EPIC_FUZZY_RE.search(strip_text)
                                    if fuzzy_m:
                                        norm = _normalize_epic(fuzzy_m.group(1))
                                        if norm and norm not in used_epics:
                                            voter.voter_id = norm
                            except Exception:
                                pass

                        # Strategy C2: Search INSIDE the card body for EPIC
                        # Some formats print the EPIC inside the card, not above it
                        if not voter.voter_id:
                            try:
                                cropped_body = page.crop(
                                    (max(0, x0 - 5), top, min(float(page.width), x1 + 5), bottom),
                                    strict=False,
                                )
                                body_text = cropped_body.extract_text() or ""
                                epic_m = _EPIC_RE.search(body_text)
                                if epic_m and epic_m.group(1) not in used_epics:
                                    voter.voter_id = epic_m.group(1)
                                elif not epic_m:
                                    fuzzy_m = _EPIC_FUZZY_RE.search(body_text)
                                    if fuzzy_m:
                                        norm = _normalize_epic(fuzzy_m.group(1))
                                        if norm and norm not in used_epics:
                                            voter.voter_id = norm
                            except Exception:
                                pass

                        # Strategy D: Search full page text for serial+EPIC pattern
                        # In many PDFs, the serial number and EPIC appear together
                        # like "416 BBJ1112035" or "416BBJ1112035" (concatenated).
                        if not voter.voter_id and voter.serial_no and page_text:
                            sn = voter.serial_no.strip()
                            # Look for serial number followed by EPIC (with or without space)
                            sn_epic_pattern = re.compile(
                                r'(?:^|\s)' + re.escape(sn) + r'\s*([A-Z]{3}\d{7})(?:\s|$)',
                                re.MULTILINE,
                            )
                            sn_m = sn_epic_pattern.search(page_text)
                            if sn_m and sn_m.group(1) not in used_epics:
                                voter.voter_id = sn_m.group(1)
                            if not voter.voter_id:
                                # Try EPIC followed by serial number
                                epic_sn_pattern = re.compile(
                                    r'([A-Z]{3}\d{7})\s*' + re.escape(sn) + r'(?:\s|$|[^\d])',
                                    re.MULTILINE,
                                )
                                rev_m = epic_sn_pattern.search(page_text)
                                if rev_m and rev_m.group(1) not in used_epics:
                                    voter.voter_id = rev_m.group(1)

                        if voter.is_valid:
                            if voter.voter_id:
                                used_epics.add(voter.voter_id)
                            else:
                                logger.info(
                                    f"[EPIC-MISS] Page {page_idx+1} voter serial={voter.serial_no!r} "
                                    f"name={voter.name!r}: ALL per-card strategies failed. "
                                    f"serial_in_map={voter.serial_no.strip() in [str(k) for k in serial_to_epic] if voter.serial_no else False}"
                                )
                            card_positions.append((x0, top, x1, bottom))
                            page_voters.append(voter)
                        else:
                            logger.warning(f"[SPATIAL] Card extracted but invalid on page {page_idx+1}: text={card_text[:100]!r}")

                    # Retry skipped cards with relaxed extraction
                    for card_text in skipped_cards:
                        voter = self._extract_voter_from_segment(card_text)
                        if voter.is_valid:
                            logger.info(f"[SPATIAL RETRY] Recovered voter: {voter.name}")
                            page_voters.append(voter)

                    # --- EPIC recovery: comprehensive multi-strategy ---
                    # Strategy 1: Position-based matching from word-level EPICs
                    voters_missing_epic = [
                        (i, v) for i, v in enumerate(page_voters) if not v.voter_id
                    ]
                    if voters_missing_epic and page_epic_words:
                        available_epic_words = [
                            ew for ew in page_epic_words
                            if ew["epic"] not in used_epics
                        ]
                        available_epic_words.sort(key=lambda e: (e["top"], e["x0"]))
                        recovered_count = 0
                        for vi, voter in voters_missing_epic:
                            if vi < len(card_positions):
                                cx0, ctop, cx1, _ = card_positions[vi]
                            else:
                                continue
                            best_epic = None
                            best_dist = float("inf")
                            for ew in available_epic_words:
                                if ew["epic"] in used_epics:
                                    continue
                                # Use center-point for horizontal matching
                                ew_cx = (ew["x0"] + ew["x1"]) / 2
                                if ew_cx < cx0 - 20 or ew_cx > cx1 + 20:
                                    continue
                                dist = abs(ew["top"] - ctop)
                                if dist < best_dist:
                                    best_dist = dist
                                    best_epic = ew
                            if best_epic and best_dist < 100:
                                voter.voter_id = best_epic["epic"]
                                used_epics.add(best_epic["epic"])
                                recovered_count += 1
                        if recovered_count > 0:
                            logger.info(
                                f"[SPATIAL EPIC-RECOVERY] Page {page_idx+1}: "
                                f"recovered {recovered_count} EPICs via word-position matching"
                            )

                    # Strategy 2: Use full-page EPIC list with 1:1 mapping
                    # In a 3-column card layout, voters and EPICs appear in the
                    # same reading order. Build a mapping: for N voters on the
                    # page, the N EPICs in reading order correspond 1:1.
                    still_missing = [
                        (i, v) for i, v in enumerate(page_voters) if not v.voter_id
                    ]
                    if still_missing and all_page_epics_ordered:
                        # Get all EPICs for this page not used by any voter globally
                        available_epics = [
                            e for e in all_page_epics_ordered
                            if e not in used_epics
                        ]

                        if available_epics:
                            # Build the full mapping: voter index → expected EPIC
                            # Each voter on the page corresponds to an EPIC in order.
                            # Voters that already have EPICs help us align the mapping.
                            epic_queue = list(all_page_epics_ordered)
                            voter_epic_map: dict[int, str] = {}
                            eq_idx = 0
                            for vi, voter in enumerate(page_voters):
                                if eq_idx >= len(epic_queue):
                                    break
                                if voter.voter_id:
                                    # Find this EPIC in the queue to stay aligned
                                    try:
                                        pos = epic_queue.index(voter.voter_id, eq_idx)
                                        eq_idx = pos + 1
                                    except ValueError:
                                        eq_idx += 1
                                else:
                                    # Assign next available EPIC from queue
                                    voter_epic_map[vi] = epic_queue[eq_idx]
                                    eq_idx += 1

                            recovered2 = 0
                            for vi, epic in voter_epic_map.items():
                                if epic not in used_epics:
                                    page_voters[vi].voter_id = epic
                                    used_epics.add(epic)
                                    recovered2 += 1

                            if recovered2 > 0:
                                logger.info(
                                    f"[SPATIAL EPIC-RECOVERY] Page {page_idx+1}: "
                                    f"recovered {recovered2} EPICs via 1:1 page mapping"
                                )

                    # Strategy 2.5: Direct full-card crop extraction
                    # For each voter still missing EPIC, crop the ENTIRE area
                    # (strip above + card body) and extract text. This catches
                    # EPICs that word-level extraction splits or misses entirely.
                    still_missing_2 = [
                        (i, v) for i, v in enumerate(page_voters) if not v.voter_id
                    ]
                    if still_missing_2:
                        recovered_crop = 0
                        for vi, voter in still_missing_2:
                            if vi >= len(card_positions):
                                continue
                            cx0, ctop, cx1, cbottom = card_positions[vi]
                            # Compute the strip above this card
                            crt = round(ctop, 0)
                            cri = row_tops_sorted.index(crt) if crt in row_tops_sorted else -1
                            if cri <= 0:
                                c_crop_top = max(0, ctop - 80)
                            else:
                                prev_bot = row_bottoms.get(row_tops_sorted[cri - 1], ctop)
                                c_crop_top = max(0, prev_bot - 5)
                            try:
                                # Crop entire strip + card body
                                full_crop = page.crop(
                                    (max(0, cx0 - 10), c_crop_top,
                                     min(float(page.width), cx1 + 10), cbottom),
                                    strict=False,
                                )
                                full_crop_text = full_crop.extract_text() or ""
                                # Find ALL EPICs in this region
                                crop_epics = _EPIC_RE.findall(full_crop_text)
                                for ce in crop_epics:
                                    if ce not in used_epics:
                                        voter.voter_id = ce
                                        used_epics.add(ce)
                                        recovered_crop += 1
                                        break
                                if not voter.voter_id:
                                    # Try fuzzy
                                    for fm in _EPIC_FUZZY_RE.finditer(full_crop_text):
                                        norm = _normalize_epic(fm.group(1))
                                        if norm and norm not in used_epics:
                                            voter.voter_id = norm
                                            used_epics.add(norm)
                                            recovered_crop += 1
                                            break
                            except Exception:
                                pass
                        if recovered_crop > 0:
                            logger.info(
                                f"[SPATIAL EPIC-RECOVERY] Page {page_idx+1}: "
                                f"recovered {recovered_crop} EPICs via full-card crop extraction"
                            )

                    # Strategy 3: Last resort — assign any remaining unmatched EPICs
                    final_missing = [
                        (i, v) for i, v in enumerate(page_voters) if not v.voter_id
                    ]
                    if final_missing:
                        remaining = [
                            e for e in all_page_epics_ordered
                            if e not in used_epics
                        ]
                        for idx, (vi, voter) in enumerate(final_missing):
                            if idx < len(remaining):
                                voter.voter_id = remaining[idx]
                                used_epics.add(remaining[idx])

                    epic_fill = sum(1 for v in page_voters if v.voter_id)
                    if page_voters:
                        logger.info(
                            f"[SPATIAL] Page {page_idx+1}: EPIC fill {epic_fill}/{len(page_voters)}"
                        )

                    logger.info(
                        f"[SPATIAL] Page {page_idx+1}: {len(card_bboxes)} cards detected, "
                        f"{len(page_voters)} voters extracted, {len(skipped_cards)} skipped"
                    )

                    # Assign serial numbers: use parsed serial if found, else auto-increment
                    serial_counter = len(voters)
                    for voter in page_voters:
                        if voter.serial_no:
                            try:
                                serial_counter = int(voter.serial_no)
                            except ValueError:
                                serial_counter += 1
                        else:
                            serial_counter += 1
                            voter.serial_no = str(serial_counter)

                    # Fix house numbers with OCR digit↔letter confusion using page context
                    self._fix_house_numbers_contextual(page_voters)

                    # Assign per-page section/street name to all voters on this page
                    if page_section_name:
                        for v in page_voters:
                            v.street_name = page_section_name

                    voters.extend(page_voters)

                    if progress_callback:
                        pct = 8 + int((page_idx + 1) / max(total_pages, 1) * 45)
                        progress_callback(
                            pct,
                            f"Parsed page {page_idx + 1}/{total_pages} ({len(voters)} voters found)",
                        )

                # Quality check: compare voter count vs EPIC count (warning only, never discard voters)
                if voters:
                    total_epics = sum(
                        len(_EPIC_RE.findall(pt)) for pt in all_page_texts
                    )
                    if total_epics > 0 and len(voters) < total_epics * 0.4:
                        logger.warning(
                            f"Spatial extraction found {len(voters)} voters vs "
                            f"{total_epics} EPICs in text — low match rate but KEEPING voters"
                        )

                    logger.info(
                        f"Spatial card extraction: {len(voters)} voters "
                        f"from {total_pages} pages"
                    )
                    return voters, total_pages, first_page_text

        except Exception as e:
            logger.warning(f"Spatial card extraction failed: {e}")

        return [], 0, ""

    def _detect_card_grid(
        self,
        page,
    ) -> list[tuple[float, float, float, float]]:
        """Detect voter card bounding boxes from page geometry.

        Sub-strategy A: use page.rects (explicit rectangles drawn in PDF).
        Sub-strategy B: reconstruct grid from page.edges (line segments).

        Returns list of (x0, top, x1, bottom) sorted top-to-bottom, left-to-right.
        """
        page_w = float(page.width)
        page_h = float(page.height)

        # Card size constraints (each card is roughly 1/3 width, 1/10 height)
        min_card_w = page_w * 0.15
        max_card_w = page_w * 0.5
        min_card_h = page_h * 0.035
        max_card_h = page_h * 0.20

        # --- Sub-strategy A: Direct rectangles ---
        rects = page.rects or []
        candidate_cards = []
        for r in rects:
            w = r["x1"] - r["x0"]
            h = r["bottom"] - r["top"]
            if min_card_w <= w <= max_card_w and min_card_h <= h <= max_card_h:
                candidate_cards.append((r["x0"], r["top"], r["x1"], r["bottom"]))

        if len(candidate_cards) >= 3:
            candidate_cards.sort(key=lambda c: (round(c[1], 0), c[0]))
            return candidate_cards

        # --- Sub-strategy B: Reconstruct grid from edges ---
        edges = page.edges or []
        if not edges:
            return []

        h_edges: list[dict] = []
        v_edges: list[dict] = []
        line_tol = 2.0

        for e in edges:
            dx = abs(e["x1"] - e["x0"])
            dy = abs(e["bottom"] - e["top"])
            if dy <= line_tol and dx > page_w * 0.10:
                h_edges.append(e)
            elif dx <= line_tol and dy > page_h * 0.03:
                v_edges.append(e)

        # Cluster vertical edges by x-coordinate
        v_x_vals = [(e["x0"] + e["x1"]) / 2 for e in v_edges]
        v_clusters = _cluster_positions(v_x_vals, tolerance=8.0)

        # Cluster horizontal edges by y-coordinate
        h_y_vals = [(e["top"] + e["bottom"]) / 2 for e in h_edges]
        h_clusters = _cluster_positions(h_y_vals, tolerance=8.0)

        # Need at least 4 vertical (for 3 columns) and 2 horizontal boundaries
        if len(v_clusters) < 4 or len(h_clusters) < 2:
            return []

        v_clusters.sort()
        h_clusters.sort()

        cards: list[tuple[float, float, float, float]] = []
        for row_idx in range(len(h_clusters) - 1):
            for col_idx in range(len(v_clusters) - 1):
                x0 = v_clusters[col_idx]
                x1 = v_clusters[col_idx + 1]
                top = h_clusters[row_idx]
                bottom = h_clusters[row_idx + 1]

                cell_w = x1 - x0
                cell_h = bottom - top
                if cell_w >= min_card_w and cell_h >= min_card_h:
                    cards.append((x0, top, x1, bottom))

        if cards:
            cards.sort(key=lambda c: (round(c[1], 0), c[0]))

        return cards

    def _apply_learned_grid(
        self,
        page,
        learned_grid: dict,
    ) -> list[tuple[float, float, float, float]]:
        """Apply grid geometry learned from a previous page to this page.

        Uses the column boundaries and average card height from a successful
        detection to generate expected card positions.
        """
        page_h = float(page.height)
        v_bounds = learned_grid.get("v_boundaries", [])
        avg_h = learned_grid.get("avg_card_height", 0)

        if len(v_bounds) < 4 or avg_h < 10:
            return []

        # Estimate row boundaries using average card height
        # Start from a small offset (header area varies), go until page bottom
        start_y = avg_h * 0.5  # rough start offset
        h_positions: list[float] = []
        y = start_y
        while y < page_h - avg_h * 0.1:
            h_positions.append(y)
            y += avg_h
        # Always add the final bottom boundary so the last row of cards is included
        # (the card generation loop uses h_positions[i] to h_positions[i+1])
        if h_positions and y <= page_h + avg_h * 0.5:
            h_positions.append(min(y, page_h))

        if len(h_positions) < 2:
            return []

        min_card_w = float(page.width) * 0.15
        min_card_h = float(page.height) * 0.035

        cards: list[tuple[float, float, float, float]] = []
        for row_idx in range(len(h_positions) - 1):
            for col_idx in range(len(v_bounds) - 1):
                x0 = v_bounds[col_idx]
                x1 = v_bounds[col_idx + 1]
                top = h_positions[row_idx]
                bottom = h_positions[row_idx + 1]
                if (x1 - x0) >= min_card_w and (bottom - top) >= min_card_h:
                    cards.append((x0, top, x1, bottom))

        cards.sort(key=lambda c: (round(c[1], 0), c[0]))
        return cards

    # ------------------------------------------------------------------
    # Table-based extraction (pdfplumber) — fallback for non-card PDFs
    # ------------------------------------------------------------------

    def _extract_via_tables(
        self,
        path: Path,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> tuple[list["VoterRecord"], int, str]:
        """Try extracting voter data using pdfplumber's table detection.

        Indian electoral roll PDFs often have a card-based layout where each
        voter is in a bordered rectangle. pdfplumber.extract_tables() can
        detect these cells, giving us much cleaner per-voter data.

        Returns (voters, total_pages, first_page_text) or ([], 0, "") on failure.
        """
        voters: list[VoterRecord] = []
        first_page_text = ""

        try:
            with pdfplumber.open(str(path)) as pdf:
                total_pages = len(pdf.pages)

                if progress_callback:
                    progress_callback(10, f"Trying table extraction on {total_pages} pages...")

                for page_idx, page in enumerate(pdf.pages):
                    # Get plain text for header parsing and street name
                    page_text = page.extract_text() or ""
                    if page_idx == 0:
                        first_page_text = page_text

                    # Extract section/street name for this page
                    page_section_name = self._extract_section_name(page_text)

                    # Try multiple table extraction strategies
                    tables = None
                    for strategy in [
                        {"vertical_strategy": "lines", "horizontal_strategy": "lines"},
                        {"vertical_strategy": "lines_strict", "horizontal_strategy": "lines_strict"},
                        {"vertical_strategy": "text", "horizontal_strategy": "text"},
                    ]:
                        try:
                            tables = page.extract_tables(table_settings=strategy)
                            if tables and any(len(t) > 1 for t in tables):
                                break
                        except Exception:
                            continue
                    else:
                        tables = None

                    if not tables:
                        continue

                    for table in tables:
                        if not table or len(table) < 2:
                            continue
                        page_voters = self._parse_table_rows(table)
                        # Assign per-page section/street name
                        if page_section_name:
                            for v in page_voters:
                                v.street_name = page_section_name
                        voters.extend(page_voters)

                    if progress_callback:
                        pct = 10 + int((page_idx + 1) / max(total_pages, 1) * 40)
                        progress_callback(
                            pct,
                            f"Parsed page {page_idx + 1}/{total_pages} ({len(voters)} voters found)",
                        )

                if voters:
                    logger.info(f"Table extraction: {len(voters)} voters from {total_pages} pages")
                    return voters, total_pages, first_page_text

        except Exception as e:
            logger.warning(f"Table extraction failed, falling back to text: {e}")

        return [], 0, ""

    def _parse_table_rows(self, table: list[list[Optional[str]]]) -> list["VoterRecord"]:
        """Parse voter records from a pdfplumber-extracted table.

        Each row in the table may represent a voter or part of a voter card.
        Cells may contain concatenated field data like "Name: X\\nFather: Y".
        """
        voters: list[VoterRecord] = []

        for row in table:
            if not row:
                continue

            # Join all cells in the row into one text blob, then parse fields
            cell_texts = [str(c).strip() for c in row if c]
            if not cell_texts:
                continue

            combined = " ".join(cell_texts)

            # Skip header/metadata rows
            if any(kw in combined.lower() for kw in [
                "electoral roll", "voter list", "வாக்காளர் பட்டியல்",
                "serial no", "வ.எண்", "photo",
            ]):
                continue

            # Try to extract one or more voters from this row
            row_voters = self._parse_voters_from_cell_text(combined)
            voters.extend(row_voters)

        return voters

    # ------------------------------------------------------------------
    # Image-based card OCR (OpenCV grid detection + per-card OCR)
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Batch card OCR: stitch cards into one image, OCR once, split text
    # ------------------------------------------------------------------

    _CARD_SEPARATOR = "═" * 40  # Unique separator between cards in stitched image

    @staticmethod
    def _stitch_cards_for_batch_ocr(
        gray: np.ndarray,
        card_crops: list[tuple[int, np.ndarray]],
    ) -> tuple[np.ndarray, list[int]]:
        """Stitch multiple card images into one vertical strip with separators.

        Inserts a thick white gap (20px) between cards so tesseract sees them
        as separate blocks. Returns (stitched_image, y_offsets_per_card).
        """
        import cv2

        GAP_H = 20  # White gap between cards
        max_w = max(c.shape[1] for _, c in card_crops) if card_crops else 100
        parts: list[np.ndarray] = []
        y_offsets: list[int] = []
        current_y = 0

        for ci, card_img in card_crops:
            # Pad card to max_w if narrower
            h_c, w_c = card_img.shape[:2]
            if w_c < max_w:
                pad = np.full((h_c, max_w - w_c), 255, dtype=np.uint8)
                card_img = np.hstack([card_img, pad])

            y_offsets.append(current_y)
            parts.append(card_img)
            current_y += h_c

            # Add white gap separator
            gap = np.full((GAP_H, max_w), 255, dtype=np.uint8)
            parts.append(gap)
            current_y += GAP_H

        if not parts:
            return np.full((10, 100), 255, dtype=np.uint8), []

        return np.vstack(parts), y_offsets

    @staticmethod
    def _split_batch_ocr_text(
        text: str, num_cards: int
    ) -> list[str]:
        """Split the OCR text from a stitched image into per-card segments.

        The stitched image has white gaps between cards which tesseract renders
        as blank lines / page breaks. We split on runs of 2+ blank lines.
        Falls back to field-label-based splitting before even distribution.
        """
        # Split on multiple blank lines (the white gap between cards)
        segments = re.split(r'\n\s*\n\s*\n', text)

        # If we got fewer segments than cards, try splitting on double-newline
        if len(segments) < num_cards:
            segments = re.split(r'\n\s*\n', text)

        # If still fewer, try field-label-based splitting (each card starts with "பெயர் :")
        if len(segments) < num_cards * 0.7:
            label_segments = re.split(r'(?=(?:^|\n)\s*(?:\d+\s+)?பெயர்\s*:)', text)
            label_segments = [s for s in label_segments if s.strip()]
            if len(label_segments) >= num_cards * 0.7:
                segments = label_segments

        # Last resort: distribute text evenly (least reliable)
        if len(segments) < num_cards * 0.7:
            all_lines = text.split('\n')
            lines_per_card = max(1, len(all_lines) // max(num_cards, 1))
            segments = []
            for i in range(0, len(all_lines), lines_per_card):
                segments.append('\n'.join(all_lines[i:i + lines_per_card]))

        # Pad with empty strings if we still have fewer
        while len(segments) < num_cards:
            segments.append("")

        return segments[:num_cards]

    @staticmethod
    def _is_header_card_text(text: str) -> bool:
        """Check if card text is a page header cell, not a voter card.

        The first row of the voter card grid often contains booth metadata:
        AC name, part number, address, "voter list" title etc.
        Cover/summary pages also have table cells with category labels
        (ஆண், பெண், மொத்தம், பொது, etc.) that must be skipped.
        These should be skipped, not parsed as voter records.
        """
        text_stripped = text.strip()
        if not text_stripped:
            return False

        # --- Cover page summary table cell detection ---
        # Cover pages have small cells with category labels like:
        # "ஆண்" (Male), "பெண்" (Female), "மூன்றாம் பாலினம்" (Third gender),
        # "பொது" (General), "மொத்தம்" (Total), "வரிசை எண்" (Serial No)
        # These are short texts (< 40 chars) with NO voter field labels
        _summary_cell_keywords = (
            'மூன்றாம் பாலினம்', 'மொத்தம்', 'பொது', 'வரிசை',
            'எண்ணிக்கை', 'தொடங்கும்', 'முடியும்',
            'திருத்த', 'தீவிர', 'சிறப்பு', 'supplement',
            'amendment', 'revision', 'deletion', 'நிகர',
            'nazri', 'naksha', 'google', 'map',
            'cad view', 'key map', 'front view',
            'கையொப்பம்', 'அலுவலரின்', 'பதிவு',
        )
        text_lower = text_stripped.lower()
        for kw in _summary_cell_keywords:
            if kw in text_lower:
                return True

        # Bare gender words as standalone cell text (from summary tables)
        # "ஆண்" or "பெண்" alone (not inside a voter card with other fields)
        bare_text = re.sub(r'\s+', '', text_stripped)
        if bare_text in ('ஆண்', 'பெண்', 'ஆண', 'பெண', 'Male', 'Female', 'மூன்றாம்பாலினம்'):
            return True

        # Very short cells (≤ 15 chars) with only a number — summary table data cell
        if len(text_stripped) <= 15 and re.fullmatch(r'\d[\d,.\s]*', text_stripped):
            return True

        # Common header indicators
        _header_indicators = (
            # Tamil labels found in page headers
            'சட்டமன்ற', 'தொகுதி', 'பாகம்', 'பகுதி எண்',
            'வாக்காளர்', 'பட்டியல்', 'ஊராட்சி',
            # Cover page / summary keywords
            'முக்கிய', 'கிராமம்', 'நகரம்', 'மற்றும்',
            'வருவாய்', 'மாவட்ட', 'சுருக்கம்', 'விவரம்',
            # Municipality / town abbreviations in brackets
            '(மா)', '(ந)', '(பே)', '(மா.நிர்)',
            # English equivalents
            'constituency', 'polling', 'part no', 'electoral',
            'assembly', 'voter list', 'supplement',
        )
        indicator_count = sum(1 for kw in _header_indicators if kw in text_lower)
        if indicator_count >= 2:
            return True
        if indicator_count == 1:
            # Single indicator: only flag as header if no voter field labels present
            has_voter_label = bool(re.search(
                r'பெயர்|Name|வயது|Age|பாலினம்|Gender|வீட்டு|House|[A-Z]{3}\d{7}',
                text_stripped, re.IGNORECASE,
            ))
            if not has_voter_label:
                return True

        # Pattern: starts with "digit-" or "digit." followed by text (e.g. "1-கடலூர் (மா), 6")
        if re.match(r'^\d+\s*[-–.]\s*[^\d]', text_stripped):
            # But "1-A" or "1-12" could be house numbers in a voter card
            # Only flag if followed by Tamil text or city-like content
            after_digit = re.sub(r'^\d+\s*[-–.]\s*', '', text_stripped)
            tamil_chars = len(re.findall(r'[\u0B80-\u0BFF]', after_digit))
            if tamil_chars >= 3:
                return True

        # If text has NO voter-like labels (no Name/Age/Gender/EPIC patterns)
        # and has address-like content, it's probably a header
        has_voter_label = bool(re.search(
            r'பெயர்|Name|வயது|Age|பாலினம்|Gender|வீட்டு|House|[A-Z]{3}\d{7}',
            text_stripped, re.IGNORECASE,
        ))
        if not has_voter_label and len(text_stripped) > 5:
            # Check if it looks like an address/location (lots of commas, numbers)
            comma_count = text_stripped.count(',')
            if comma_count >= 2:
                return True
            # Short text with Tamil content but no voter fields — likely header cell
            tamil_chars = len(re.findall(r'[\u0B80-\u0BFF]', text_stripped))
            if tamil_chars >= 2 and len(text_stripped) <= 40:
                return True

        return False

    @staticmethod
    def _is_deleted_voter_card(card_text: str) -> bool:
        """Check if a voter card text contains a 'DELETED' marker."""
        return bool(_DELETED_RE.search(card_text))

    @staticmethod
    def _is_deleted_voter_card_image(card_img_color: np.ndarray) -> bool:
        """Detect 'DELETED' watermark on a voter card using image analysis.

        The DELETED stamp is a red-colored diagonal text overlaid on the card.
        We detect it by looking for significant red-colored pixel regions,
        which are distinctive because normal card content is black text on
        white background with no red.
        """
        import cv2

        if card_img_color is None or card_img_color.size == 0:
            return False

        # Convert to HSV to detect red color
        # The DELETED stamp is red — unique in voter cards which are black/white
        if len(card_img_color.shape) < 3:
            return False  # Grayscale image, can't detect red

        # Image comes from PIL (RGB format), convert to HSV
        hsv = cv2.cvtColor(card_img_color, cv2.COLOR_RGB2HSV)

        # Red in HSV wraps around 0/180, so we need two ranges
        # Lower red: H=0-10, S=70-255, V=50-255
        lower_red1 = np.array([0, 70, 50])
        upper_red1 = np.array([10, 255, 255])
        # Upper red: H=160-180, S=70-255, V=50-255
        lower_red2 = np.array([160, 70, 50])
        upper_red2 = np.array([180, 255, 255])

        mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
        mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
        red_mask = mask1 | mask2

        # Count red pixels as fraction of total card area
        total_pixels = card_img_color.shape[0] * card_img_color.shape[1]
        red_pixels = cv2.countNonZero(red_mask)
        red_ratio = red_pixels / max(total_pixels, 1)

        # A DELETED stamp typically covers a significant portion of the card
        # with red text. Normal cards have essentially 0 red pixels.
        # Threshold: >0.5% red pixels indicates a red stamp/watermark
        if red_ratio > 0.005:
            logger.debug(
                f"[DELETED-IMG] Red ratio: {red_ratio:.4f} "
                f"({red_pixels}/{total_pixels} pixels) — DELETED detected"
            )
            return True

        return False

    @staticmethod
    def _is_deleted_voter_card_diagonal(card_img_gray: np.ndarray) -> bool:
        """Detect 'DELETED' watermark using diagonal line analysis.

        The DELETED stamp is diagonal text (roughly 30-50 degrees) overlaid
        on the card.  Normal voter card content is strictly horizontal text,
        so diagonal strokes are a strong signal of a watermark.

        Uses Canny edge detection + Hough line transform to count diagonal
        line segments within the left 60 percent of the card (right side has
        the "Photo is available" box which is all horizontal/vertical).

        The detection threshold is normalised to card dimensions so it is
        DPI-independent.
        """
        import cv2

        if card_img_gray is None or card_img_gray.size == 0:
            return False

        h, w = card_img_gray.shape[:2]
        if h < 20 or w < 20:
            return False

        # Only analyse left 60% of card to avoid photo box interference
        left_w = int(w * 0.6)
        roi = card_img_gray[:, :left_w]

        edges = cv2.Canny(roi, 50, 150)
        lines = cv2.HoughLinesP(
            edges, 1, np.pi / 180, 30,
            minLineLength=max(15, h // 15),
            maxLineGap=5,
        )

        if lines is None:
            return False

        diag_count = 0
        total_diag_length = 0.0

        for line in lines:
            x1, y1, x2, y2 = line[0]
            dx = x2 - x1
            if dx == 0:
                continue
            angle = abs(np.degrees(np.arctan2(y2 - y1, dx)))
            if 20 <= angle <= 70:
                length = np.sqrt(dx * dx + (y2 - y1) ** 2)
                diag_count += 1
                total_diag_length += length

        # Normalise total diagonal length relative to card diagonal so the
        # threshold is DPI-independent.  The DELETED watermark spans a
        # significant fraction of the card diagonal.
        card_diag = np.sqrt(float(h * h + left_w * left_w))
        diag_ratio = total_diag_length / max(card_diag, 1.0)

        # True DELETED stamps yield ratio > 1.0 (many overlapping diagonal
        # strokes), normal cards yield < 0.6.
        if diag_ratio >= 1.0 and diag_count >= 15:
            logger.debug(
                f"[DELETED-DIAG] diag_lines={diag_count}, "
                f"total_len={total_diag_length:.0f}, "
                f"ratio={diag_ratio:.2f} — DELETED detected"
            )
            return True

        return False

    def _ocr_single_page_cards(
        self,
        page_idx: int,
        gray: np.ndarray,
        do_header_ocr: bool,
        color_img: np.ndarray | None = None,
    ) -> dict[str, Any]:
        """OCR a single page: detect card grid, per-card OCR, return voters.

        Uses per-card OCR for accurate text extraction (one pytesseract call
        per card) plus a dedicated EPIC strip OCR per card for voter ID
        recovery. Falls back to whole-page EPIC pass for remaining gaps.

        Returns dict with keys: page_idx, voters, header_text, card_count.
        """
        import pytesseract
        import cv2

        result: dict[str, Any] = {
            "page_idx": page_idx,
            "voters": [],
            "header_text": "",
            "card_count": 0,
            "section_name": "",
        }

        # Extract section/street name from top header strip of every page
        try:
            h_img, w_img = gray.shape[:2]
            header_strip = gray[0:int(h_img * 0.12), :]
            header_strip_text = pytesseract.image_to_string(
                header_strip, lang="tam+eng", config="--oem 3 --psm 6"
            )
            section_name = self._extract_section_name(header_strip_text)
            if section_name:
                result["section_name"] = section_name
        except Exception:
            pass

        # Try to get header text from first few pages
        if do_header_ocr:
            try:
                header_text = pytesseract.image_to_string(
                    gray, lang="tam+eng", config="--oem 3 --psm 3"
                )
                if header_text.strip():
                    result["header_text"] = header_text
            except Exception:
                pass

        # Detect card grid using OpenCV
        card_bboxes = self._detect_card_grid_from_image(gray)

        # If grid detection fails, try applying learned grid from previous pages
        if not card_bboxes and hasattr(self, '_learned_img_grid') and self._learned_img_grid:
            card_bboxes = self._apply_learned_img_grid(gray, self._learned_img_grid)
            if card_bboxes:
                logger.info(
                    f"[IMG-CARD-OCR] Page {page_idx+1}: applied learned grid — "
                    f"{len(card_bboxes)} cards"
                )

        if not card_bboxes:
            # Try full-page OCR fallback for pages without grid
            try:
                page_text = pytesseract.image_to_string(
                    gray, lang="tam+eng", config="--oem 3 --psm 3"
                )
                page_text_fixed = _fix_ocr_epic(page_text) if page_text else ""
                if page_text_fixed and (_EPIC_RE.search(page_text_fixed)
                                        or _EPIC_FUZZY_RE.search(page_text_fixed)):
                    fallback_voters = self._parse_voters_from_text(page_text_fixed)
                    result["voters"] = [v for v in fallback_voters if v.is_valid]
                    if result["voters"]:
                        logger.info(
                            f"[IMG-CARD-OCR] Page {page_idx+1}: no grid, "
                            f"recovered {len(result['voters'])} voters via full-page OCR"
                        )
            except Exception:
                pass
            return result

        # Learn grid template from first successful detection (only from
        # pages with a full grid, not partial pages with 1-2 cards)
        if (not hasattr(self, '_learned_img_grid') or not self._learned_img_grid) \
                and len(card_bboxes) >= 9:
            self._learned_img_grid = card_bboxes

        result["card_count"] = len(card_bboxes)
        logger.info(f"[IMG-CARD-OCR] Page {page_idx+1}: {len(card_bboxes)} cards detected")

        row_tops = sorted(set(c[1] for c in card_bboxes))

        # Build mapping: row_top -> bottom_y of cards in the previous row
        # Used to locate the EPIC strip between rows
        row_prev_bottom: dict[int, int | None] = {}
        for rt_idx, rt in enumerate(row_tops):
            if rt_idx == 0:
                row_prev_bottom[rt] = None
            else:
                prev_rt = row_tops[rt_idx - 1]
                # Find height of a card in the previous row
                prev_h = next(
                    ch for cx, cy, cw, ch in card_bboxes if cy == prev_rt
                )
                row_prev_bottom[rt] = prev_rt + prev_h

        # Reusable CLAHE enhancer
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))

        # --- Step 0: Single whole-page EPIC scan (1 pytesseract call) ---
        # Much faster than per-card EPIC strip OCR (saves up to 18 calls/card)
        page_epic_by_pos: list[dict] = []
        try:
            epic_data = pytesseract.image_to_data(
                gray, lang="eng",
                config="--oem 3 --psm 3",
                output_type=pytesseract.Output.DICT,
            )
            for wi in range(len(epic_data["text"])):
                word = epic_data["text"][wi].strip()
                if not word:
                    continue
                # Fix common OCR misread: $ → S
                word_fixed = _fix_ocr_epic(word)
                m = _EPIC_RE.search(word_fixed)
                if m:
                    page_epic_by_pos.append({
                        "epic": m.group(1),
                        "x": epic_data["left"][wi] + epic_data["width"][wi] // 2,
                        "y": epic_data["top"][wi],
                    })
                else:
                    fm = _EPIC_FUZZY_RE.search(word_fixed)
                    if fm:
                        norm = _normalize_epic(fm.group(1))
                        if norm:
                            page_epic_by_pos.append({
                                "epic": norm,
                                "x": epic_data["left"][wi] + epic_data["width"][wi] // 2,
                                "y": epic_data["top"][wi],
                            })
        except Exception:
            pass

        # --- Per-card OCR (single OCR call per card) ---
        page_voters: list[VoterRecord] = []
        card_to_voter: dict[int, int] = {}
        has_missing_epic = False
        skipped_header_cards = 0
        used_epics: set[str] = set()

        for ci, (x, y, w, h) in enumerate(card_bboxes):
            row_idx = row_tops.index(y) if y in row_tops else 0
            inset = 4

            # --- Step A: Single OCR of card body (left 65%) ---
            # OCR only the left portion to avoid "Photo is available" box
            # interference. Only OCR full card if left portion fails.
            card_img = gray[y + inset:y + h - inset, x + inset:x + w - inset]
            if card_img.size == 0:
                continue

            left_w = int(w * 0.65)
            left_img = gray[y + inset:y + h - inset, x + inset:x + left_w]
            card_text = ""
            if left_img.size > 0:
                try:
                    card_text = pytesseract.image_to_string(
                        clahe.apply(left_img), lang="tam+eng",
                        config="--oem 3 --psm 6",
                    )
                except Exception:
                    pass

            # Fallback: full card OCR only if left portion gave nothing
            full_text = ""
            if not card_text.strip():
                try:
                    full_text = pytesseract.image_to_string(
                        clahe.apply(card_img), lang="tam+eng",
                        config="--oem 3 --psm 6",
                    )
                    card_text = full_text
                except Exception:
                    continue

            # Strip header metadata lines that may leak into first-row cards
            card_text = re.sub(
                r'^.*?(?:சட்டமன்ற|தொகுதி|பிரிவு எண்|பகுதி எண்|பாகம் எண்).*?\n',
                '', card_text, count=2,
            )

            if self._is_header_card_text(card_text):
                skipped_header_cards += 1
                continue

            # Skip deleted/struck-off voters
            # Strategy 1: Check card text for "DELETED" keyword
            is_deleted = self._is_deleted_voter_card(card_text)
            # Strategy 2: Diagonal watermark detection (dark/gray DELETED stamp)
            # This catches black diagonal "DELETED" text that OCR misses.
            if not is_deleted:
                inset_d = 4
                card_gray_roi = gray[y + inset_d:y + h - inset_d,
                                     x + inset_d:x + w - inset_d]
                is_deleted = self._is_deleted_voter_card_diagonal(card_gray_roi)
            # Strategy 3: Check color image for red watermark stamp
            if not is_deleted and color_img is not None and len(color_img.shape) == 3:
                inset_c = 4
                card_color = color_img[y + inset_c:y + h - inset_c, x + inset_c:x + w - inset_c]
                is_deleted = self._is_deleted_voter_card_image(card_color)
            if is_deleted:
                self._deleted_voter_count += 1
                logger.info(
                    f"[IMG-CARD-OCR] Page {page_idx+1} card {ci}: "
                    f"DELETED voter skipped"
                )
                continue

            if len(card_text.strip()) < 3:
                continue

            voter = self._extract_voter_from_segment(card_text)

            # If missing house_no, try full card OCR (only if not already done)
            if not voter.house_no and not full_text and card_img.size > 0:
                try:
                    full_text = pytesseract.image_to_string(
                        clahe.apply(card_img), lang="tam+eng",
                        config="--oem 3 --psm 6",
                    )
                except Exception:
                    full_text = ""
            if not voter.house_no and full_text.strip():
                full_voter = self._extract_voter_from_segment(full_text)
                if full_voter.house_no:
                    voter.house_no = full_voter.house_no

            # --- Step B: Assign EPIC from whole-page EPIC scan ---
            # Match by position: EPIC word should be above/near the card
            # and within the card's horizontal range.
            if not voter.voter_id:
                # Compute the EPIC strip region for this card
                if row_idx == 0:
                    epic_y_top = max(0, y - 80)
                else:
                    prev_bottom = row_prev_bottom.get(y)
                    epic_y_top = max(0, prev_bottom - 10) if prev_bottom else max(0, y - 80)
                epic_y_bot = y + 30

                best_epic = None
                best_dist = float("inf")
                for ep in page_epic_by_pos:
                    if ep["epic"] in used_epics:
                        continue
                    # Must be within card's horizontal range
                    if ep["x"] < x - 10 or ep["x"] > x + w + 10:
                        continue
                    # Must be in the EPIC strip zone (above card to just inside top)
                    if ep["y"] < epic_y_top or ep["y"] > epic_y_bot:
                        continue
                    dist = abs(ep["y"] - y)
                    if dist < best_dist:
                        best_dist = dist
                        best_epic = ep
                if best_epic:
                    voter.voter_id = best_epic["epic"]

            # --- Step C: Per-card EPIC strip OCR (only if still missing) ---
            # The EPIC is printed in the strip above each card. Tamil text on
            # the left of the strip can confuse eng-only OCR, so we try both
            # full-width and right-half crops with multiple preprocessing.
            if not voter.voter_id:
                epic_strip_y1 = None
                epic_strip_y2 = None
                if row_idx == 0:
                    epic_strip_y1 = max(0, y - 80)
                    epic_strip_y2 = y + 30
                else:
                    prev_bottom = row_prev_bottom.get(y)
                    if prev_bottom is not None:
                        epic_strip_y1 = max(0, prev_bottom - 10)
                        epic_strip_y2 = min(gray.shape[0], y + 30)
                    else:
                        epic_strip_y1 = max(0, y - 80)
                        epic_strip_y2 = y

                if epic_strip_y1 is not None:
                    # Build crop variants: full-width strip, then right-half
                    # (EPIC is on the right side; Tamil serial/text on the left
                    # often garbles the OCR when included)
                    strip_crops = []
                    full_strip = gray[epic_strip_y1:epic_strip_y2, x:x + w]
                    if full_strip.size > 0:
                        strip_crops.append(full_strip)
                    right_strip = gray[epic_strip_y1:epic_strip_y2, x + w // 2:x + w]
                    if right_strip.size > 0:
                        strip_crops.append(right_strip)

                    for strip_img in strip_crops:
                        if voter.voter_id:
                            break
                        # Try multiple preprocessing per crop
                        preprocess_variants = []
                        try:
                            _, binary_strip = cv2.threshold(
                                strip_img, 0, 255,
                                cv2.THRESH_BINARY + cv2.THRESH_OTSU,
                            )
                            preprocess_variants.append(binary_strip)
                            preprocess_variants.append(clahe.apply(strip_img))
                            adaptive_strip = cv2.adaptiveThreshold(
                                strip_img, 255,
                                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                cv2.THRESH_BINARY, 31, 10,
                            )
                            preprocess_variants.append(adaptive_strip)
                            sh, sw = strip_img.shape
                            resized = cv2.resize(strip_img, (sw * 2, sh * 2), interpolation=cv2.INTER_CUBIC)
                            _, resized_bin = cv2.threshold(resized, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                            preprocess_variants.append(resized_bin)
                        except Exception:
                            pass

                        # Try PSM 7 (single line) and PSM 6 (block) modes
                        for psm_config in ["--oem 3 --psm 7", "--oem 3 --psm 6"]:
                            if voter.voter_id:
                                break
                            for variant_img in preprocess_variants:
                                if voter.voter_id:
                                    break
                                try:
                                    epic_text = pytesseract.image_to_string(
                                        variant_img, lang="eng",
                                        config=psm_config,
                                    )
                                    # Fix common OCR misread: $ → S
                                    epic_text = _fix_ocr_epic(epic_text)
                                    epic_m = _EPIC_RE.search(epic_text)
                                    if epic_m and epic_m.group(1) not in used_epics:
                                        voter.voter_id = epic_m.group(1)
                                    elif not epic_m:
                                        fuzzy_m = _EPIC_FUZZY_RE.search(epic_text)
                                        if fuzzy_m:
                                            normalized = _normalize_epic(fuzzy_m.group(1))
                                            if normalized and normalized not in used_epics:
                                                voter.voter_id = normalized
                                except Exception:
                                    pass

            if voter.is_valid:
                voter_idx = len(page_voters)
                card_to_voter[ci] = voter_idx
                if voter.voter_id:
                    used_epics.add(voter.voter_id)
                else:
                    has_missing_epic = True
                page_voters.append(voter)

        # --- Whole-page EPIC fallback: reuse page_epic_by_pos (no extra OCR) ---
        if has_missing_epic and page_epic_by_pos:
            # Sort remaining EPICs by vertical position
            remaining_epics = [
                ep for ep in page_epic_by_pos if ep["epic"] not in used_epics
            ]
            remaining_epics.sort(key=lambda e: (e["y"], e["x"]))

            # Assign remaining EPICs to voters without EPIC in order
            missing_voters = [
                (vi, v) for vi, v in enumerate(page_voters)
                if not v.voter_id
            ]
            for idx, (vi, voter) in enumerate(missing_voters):
                if idx < len(remaining_epics):
                    voter.voter_id = remaining_epics[idx]["epic"]
                    used_epics.add(remaining_epics[idx]["epic"])

        # Quality check: detect cover/summary pages vs actual data pages.
        # Real data pages have voters with EPICs + age + gender.
        # Cover pages may produce "voters" from summary table cells with
        # no EPICs and no real voter fields.
        voters_with_epic = sum(1 for v in page_voters if v.voter_id)
        voters_with_full_evidence = sum(
            1 for v in page_voters
            if (v.voter_id or v.age) and v.gender and v.name
            and (v.father_husband_name or v.house_no)
        )
        voters_with_any_evidence = sum(
            1 for v in page_voters
            if v.voter_id or v.age or v.gender
        )
        if page_voters and voters_with_any_evidence == 0:
            logger.info(
                f"[IMG-CARD-OCR] Page {page_idx+1}: discarding {len(page_voters)} "
                f"voters — no EPIC/age/gender evidence (cover/summary page)"
            )
            page_voters.clear()
        elif page_voters and voters_with_epic == 0 and voters_with_full_evidence == 0:
            # No EPICs and no fully-evidenced voters: likely cover/summary page
            # Real data pages always have at least some EPICs
            logger.info(
                f"[IMG-CARD-OCR] Page {page_idx+1}: discarding {len(page_voters)} "
                f"voters — no EPICs and no fully-evidenced records (cover/summary page)"
            )
            page_voters.clear()

        if skipped_header_cards:
            logger.info(
                f"[IMG-CARD-OCR] Page {page_idx+1}: skipped {skipped_header_cards} header cards"
            )
        logger.info(
            f"[IMG-CARD-OCR] Page {page_idx+1}: {len(page_voters)} voters "
            f"from {len(card_bboxes)} cards"
        )

        # Fix house numbers with OCR digit↔letter confusion using page context
        VotersPDFProcessor._fix_house_numbers_contextual(page_voters)

        result["voters"] = page_voters
        return result

    def _extract_via_image_card_ocr(
        self,
        path: Path,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> tuple[list["VoterRecord"], int]:
        """Extract voter data by detecting card grids and OCR-ing each card.

        For scanned/image-based PDFs where pdfplumber can't extract text.
        Uses OpenCV to detect card grids, OCRs each card individually (1 call
        per card for accurate text), plus 1 whole-page EPIC pass for recovery.

        Optimizations over original approach:
        - Removed expensive EPIC fallback strategies 2-4 (was 2-4 extra calls/card)
        - 1 whole-page EPIC pass replaces per-card EPIC retries
        - Page batching: converts 8 pages at a time to limit memory
        - Adaptive DPI: starts at 200, falls back to 300 if quality is low

        Returns (voters, total_pages) or ([], 0) on failure.
        """
        try:
            import pytesseract
            import cv2
        except ImportError:
            logger.warning("pytesseract or cv2 not available for image card OCR")
            return [], 0

        if progress_callback:
            progress_callback(10, "Converting PDF to images for card detection...")

        # Get total page count without converting all pages
        try:
            with pdfplumber.open(str(path)) as pdf:
                total_pages = len(pdf.pages)
        except Exception as e:
            logger.warning(f"Failed to open PDF for page count: {e}")
            return [], 0

        if total_pages == 0:
            return [], 0

        # Adaptive DPI: start at 300 for Tamil accuracy, fall back to 400 if quality is poor
        INITIAL_DPI = int(os.environ.get("VOTER_OCR_DPI", "300"))
        FALLBACK_DPI = 400
        current_dpi = INITIAL_DPI
        dpi_upgraded = False

        # Configurable page batch size and thread count
        BATCH_SIZE = int(os.environ.get("VOTER_PAGE_BATCH", "8"))
        PAGE_THREADS = int(os.environ.get("VOTER_PAGE_THREADS",
                                          str(min(os.cpu_count() or 4, 8))))

        if progress_callback:
            progress_callback(15, f"OCR-ing {total_pages} pages ({current_dpi} DPI)...")

        from concurrent.futures import ThreadPoolExecutor, as_completed

        page_results: list[dict | None] = [None] * total_pages
        completed_count = 0

        # Process pages in batches to limit memory usage
        for batch_start in range(0, total_pages, BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, total_pages)

            # Convert this batch of pages to images (1-indexed for pdf2image)
            try:
                batch_images = convert_from_path(
                    str(path), dpi=current_dpi,
                    first_page=batch_start + 1,
                    last_page=batch_end,
                )
            except Exception as e:
                logger.warning(f"pdf2image batch {batch_start+1}-{batch_end} failed: {e}")
                continue

            # Convert to grayscale and color numpy arrays
            gray_batch: list[np.ndarray] = []
            color_batch: list[np.ndarray] = []
            for pil_img in batch_images:
                img = np.array(pil_img)
                color_batch.append(img)
                if len(img.shape) == 3:
                    gray_batch.append(cv2.cvtColor(img, cv2.COLOR_RGB2GRAY))
                else:
                    gray_batch.append(img)
            del batch_images  # Free PIL images immediately

            # Process batch in parallel
            batch_threads = min(PAGE_THREADS, len(gray_batch))
            with ThreadPoolExecutor(max_workers=batch_threads) as executor:
                futures = {}
                for i, gray in enumerate(gray_batch):
                    page_idx = batch_start + i
                    do_header = page_idx < 2  # Only first 2 pages for header
                    color_img = color_batch[i]
                    future = executor.submit(
                        self._ocr_single_page_cards, page_idx, gray, do_header,
                        color_img,
                    )
                    futures[future] = page_idx

                for future in as_completed(futures):
                    page_idx = futures[future]
                    try:
                        page_results[page_idx] = future.result(timeout=120)
                    except Exception as e:
                        logger.warning(f"[IMG-CARD-OCR] Page {page_idx+1} failed: {e}")
                        page_results[page_idx] = {
                            "page_idx": page_idx, "voters": [],
                            "header_text": "", "card_count": 0,
                            "section_name": "",
                        }
                    completed_count += 1
                    if progress_callback:
                        pct = 15 + int(completed_count / max(total_pages, 1) * 65)
                        progress_callback(
                            pct,
                            f"Card OCR: {completed_count}/{total_pages} pages done"
                        )

            del gray_batch  # Free numpy arrays

            # After first batch: check quality and upgrade DPI if needed
            if (batch_start == 0 and current_dpi < FALLBACK_DPI
                    and not dpi_upgraded):
                batch_voters = []
                for pr in page_results[:batch_end]:
                    if pr and pr.get("voters"):
                        batch_voters.extend(pr["voters"])
                if len(batch_voters) >= 5:
                    voters_with_epic = sum(
                        1 for v in batch_voters if v.voter_id
                    )
                    epic_rate = voters_with_epic / len(batch_voters)
                    if epic_rate < 0.5:
                        logger.info(
                            f"[IMG-CARD-OCR] EPIC rate {epic_rate:.0%} at "
                            f"{current_dpi} DPI — upgrading to {FALLBACK_DPI} DPI"
                        )
                        current_dpi = FALLBACK_DPI
                        dpi_upgraded = True
                        # Re-process first batch at higher DPI
                        page_results[:batch_end] = [None] * batch_end
                        completed_count = 0
                        try:
                            retry_images = convert_from_path(
                                str(path), dpi=FALLBACK_DPI,
                                first_page=1, last_page=batch_end,
                            )
                            retry_gray: list[np.ndarray] = []
                            retry_color: list[np.ndarray] = []
                            for pil_img in retry_images:
                                img = np.array(pil_img)
                                retry_color.append(img)
                                if len(img.shape) == 3:
                                    retry_gray.append(
                                        cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
                                    )
                                else:
                                    retry_gray.append(img)
                            del retry_images

                            with ThreadPoolExecutor(
                                max_workers=batch_threads
                            ) as executor:
                                futures = {}
                                for i, gray in enumerate(retry_gray):
                                    do_hdr = i < 2
                                    future = executor.submit(
                                        self._ocr_single_page_cards,
                                        i, gray, do_hdr,
                                        retry_color[i],
                                    )
                                    futures[future] = i
                                for future in as_completed(futures):
                                    pidx = futures[future]
                                    try:
                                        page_results[pidx] = future.result(
                                            timeout=120
                                        )
                                    except Exception:
                                        page_results[pidx] = {
                                            "page_idx": pidx, "voters": [],
                                            "header_text": "", "card_count": 0,
                                            "section_name": "",
                                        }
                                    completed_count += 1
                            del retry_gray, retry_color
                        except Exception as e:
                            logger.warning(
                                f"[IMG-CARD-OCR] DPI upgrade retry failed: {e}"
                            )

        # Collect results in page order
        voters: list[VoterRecord] = []
        header_ocr_done = False

        for pr in page_results:
            if pr is None:
                continue

            # Parse header from early pages (sequentially to avoid races)
            if not header_ocr_done and pr["header_text"]:
                self._parse_header(pr["header_text"])
                if self.header_info.ac_no and self.header_info.part_no:
                    header_ocr_done = True

            # Assign section/street name and serial numbers, then collect voters
            page_section_name = pr.get("section_name", "")
            for voter in pr["voters"]:
                if page_section_name:
                    voter.street_name = page_section_name
                serial_counter = len(voters) + 1
                voter.serial_no = str(serial_counter)
                voters.append(voter)

        # --- Second-pass EPIC recovery (expensive: re-converts pages) ---
        # Only attempt if missing rate is high (>30%) to avoid slow re-OCR
        if voters:
            missing_epic_count = sum(1 for v in voters if not v.voter_id)
            epic_rate = 1.0 - (missing_epic_count / len(voters)) if voters else 1.0
            if missing_epic_count > 0 and epic_rate < 0.7:
                logger.info(
                    f"[EPIC-RECOVERY] {missing_epic_count}/{len(voters)} voters "
                    f"missing EPIC ({epic_rate:.0%} fill) — attempting second-pass recovery"
                )
                all_used_epics = set(v.voter_id for v in voters if v.voter_id)
                recovered = 0
                for pr in page_results:
                    if pr is None:
                        continue
                    page_voters_with_missing = [
                        v for v in pr["voters"] if not v.voter_id
                    ]
                    if not page_voters_with_missing:
                        continue
                    try:
                        page_idx = pr["page_idx"]
                        retry_imgs = convert_from_path(
                            str(path), dpi=current_dpi,
                            first_page=page_idx + 1,
                            last_page=page_idx + 1,
                        )
                        if not retry_imgs:
                            continue
                        import cv2
                        retry_gray = np.array(retry_imgs[0])
                        if len(retry_gray.shape) == 3:
                            retry_gray = cv2.cvtColor(retry_gray, cv2.COLOR_RGB2GRAY)
                        del retry_imgs

                        retry_clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4, 4))
                        enhanced = retry_clahe.apply(retry_gray)
                        try:
                            import pytesseract
                            epic_data = pytesseract.image_to_data(
                                enhanced, lang="eng",
                                config="--oem 3 --psm 3",
                                output_type=pytesseract.Output.DICT,
                            )
                            page_epic_words_retry = []
                            for wi in range(len(epic_data["text"])):
                                word = _fix_ocr_epic(epic_data["text"][wi].strip())
                                if not word:
                                    continue
                                m = _EPIC_RE.search(word)
                                if m and m.group(1) not in all_used_epics:
                                    page_epic_words_retry.append(m.group(1))
                                else:
                                    fm = _EPIC_FUZZY_RE.search(word)
                                    if fm:
                                        norm = _normalize_epic(fm.group(1))
                                        if norm and norm not in all_used_epics:
                                            page_epic_words_retry.append(norm)
                            # Sequential assignment of recovered EPICs
                            epic_idx = 0
                            for v in page_voters_with_missing:
                                if v.voter_id or epic_idx >= len(page_epic_words_retry):
                                    continue
                                v.voter_id = page_epic_words_retry[epic_idx]
                                all_used_epics.add(page_epic_words_retry[epic_idx])
                                epic_idx += 1
                                recovered += 1
                        except Exception:
                            pass
                        del retry_gray
                    except Exception:
                        continue
                if recovered > 0:
                    logger.info(
                        f"[EPIC-RECOVERY] Recovered {recovered} EPICs in second pass"
                    )
            elif missing_epic_count > 0:
                logger.info(
                    f"[EPIC-RECOVERY] {missing_epic_count}/{len(voters)} voters "
                    f"missing EPIC ({epic_rate:.0%} fill) — skipping expensive second pass"
                )

            logger.info(
                f"[IMG-CARD-OCR] Total: {len(voters)} voters from "
                f"{total_pages} pages at {current_dpi} DPI "
                f"(EPICs: {sum(1 for v in voters if v.voter_id)}/{len(voters)})"
            )

        return voters, total_pages

    @staticmethod
    def _detect_card_grid_from_image(gray: np.ndarray) -> list[tuple[int, int, int, int]]:
        """Detect voter card bounding boxes from a grayscale page image.

        Uses OpenCV morphological operations to find grid lines, then
        intersects horizontal and vertical lines to find card rectangles.

        Returns list of (x, y, w, h) tuples for each detected card.
        """
        import cv2

        h_img, w_img = gray.shape[:2]

        # Card size constraints for 3-column layout at 300 DPI
        # A4 at 300 DPI = ~2480 × 3508 pixels
        min_card_w = w_img * 0.15
        max_card_w = w_img * 0.50
        min_card_h = h_img * 0.035
        max_card_h = h_img * 0.20

        # Binarize
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # Detect horizontal lines
        h_kernel_len = max(w_img // 10, 50)
        h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (h_kernel_len, 1))
        h_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, h_kernel)

        # Detect vertical lines
        v_kernel_len = max(h_img // 15, 30)
        v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, v_kernel_len))
        v_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, v_kernel)

        # Find horizontal line y-positions
        h_proj = np.sum(h_lines, axis=1)
        h_threshold = w_img * 0.07 * 255  # at least 7% of page width (relaxed for faint lines)
        h_positions = []
        in_line = False
        line_start = 0
        for y_pos in range(len(h_proj)):
            if h_proj[y_pos] > h_threshold:
                if not in_line:
                    line_start = y_pos
                    in_line = True
            else:
                if in_line:
                    h_positions.append((line_start + y_pos) // 2)
                    in_line = False
        if in_line:
            h_positions.append((line_start + len(h_proj)) // 2)

        # Find vertical line x-positions
        v_proj = np.sum(v_lines, axis=0)
        v_threshold = h_img * 0.035 * 255  # at least 3.5% of page height (relaxed for faint lines)
        v_positions = []
        in_line = False
        line_start = 0
        for x_pos in range(len(v_proj)):
            if v_proj[x_pos] > v_threshold:
                if not in_line:
                    line_start = x_pos
                    in_line = True
            else:
                if in_line:
                    v_positions.append((line_start + x_pos) // 2)
                    in_line = False
        if in_line:
            v_positions.append((line_start + len(v_proj)) // 2)

        # Build card rectangles from grid intersections
        cards: list[tuple[int, int, int, int]] = []
        if len(v_positions) >= 4 and len(h_positions) >= 2:
            # Standard 3-column grid
            for row_idx in range(len(h_positions) - 1):
                for col_idx in range(len(v_positions) - 1):
                    x0 = v_positions[col_idx]
                    x1 = v_positions[col_idx + 1]
                    y0 = h_positions[row_idx]
                    y1 = h_positions[row_idx + 1]

                    card_w = x1 - x0
                    card_h = y1 - y0

                    if min_card_w <= card_w <= max_card_w and min_card_h <= card_h <= max_card_h:
                        cards.append((x0, y0, card_w, card_h))

        # Fallback: contour-based detection for pages with few cards (e.g. last
        # page with only 1-2 voters). Grid-based detection fails here because
        # there aren't enough grid lines.
        if not cards:
            contours, _ = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            seen = set()
            for cnt in contours:
                x, y, w, h = cv2.boundingRect(cnt)
                if min_card_w <= w <= max_card_w and min_card_h <= h <= max_card_h:
                    # De-duplicate near-identical rectangles (contours often
                    # yield inner + outer border for the same card)
                    key = (round(x / 20), round(y / 20), round(w / 20), round(h / 20))
                    if key not in seen:
                        seen.add(key)
                        cards.append((x, y, w, h))

        # Sort: top-to-bottom, left-to-right
        cards.sort(key=lambda c: (c[1], c[0]))
        return cards

    @staticmethod
    def _apply_learned_img_grid(
        gray: np.ndarray,
        template_cards: list[tuple[int, int, int, int]],
    ) -> list[tuple[int, int, int, int]]:
        """Apply a grid template learned from a previous page to this page.

        Uses the column x-positions and row heights from a successful detection
        on another page. Pages in voter PDFs have consistent grid layouts.
        """
        h_img, w_img = gray.shape[:2]

        # Extract column x-positions and typical card dimensions from template
        col_xs = sorted(set(x for x, y, w, h in template_cards))
        row_ys = sorted(set(y for x, y, w, h in template_cards))

        if not col_xs or not row_ys:
            return []

        # Get typical card dimensions
        avg_w = int(sum(w for _, _, w, _ in template_cards) / len(template_cards))
        avg_h = int(sum(h for _, _, _, h in template_cards) / len(template_cards))

        # Build grid using template column positions and evenly spaced rows
        cards: list[tuple[int, int, int, int]] = []
        row_spacing = row_ys[1] - row_ys[0] if len(row_ys) > 1 else avg_h + 20

        # Use template row y-positions directly (they should be consistent)
        for ry in row_ys:
            if ry + avg_h > h_img:
                continue
            for cx in col_xs:
                if cx + avg_w > w_img:
                    continue
                cards.append((cx, ry, avg_w, avg_h))

        cards.sort(key=lambda c: (c[1], c[0]))
        return cards

    # ------------------------------------------------------------------
    # Text extraction (pdfplumber) — fallback
    # ------------------------------------------------------------------

    def _extract_text(self, path: Path) -> list[str]:
        """Extract text from each page using pdfplumber."""
        pages_text: list[str] = []
        try:
            with pdfplumber.open(str(path)) as pdf:
                for page in pdf.pages:
                    text = page.extract_text() or ""
                    pages_text.append(text)
        except Exception as e:
            logger.error(f"pdfplumber extraction failed: {e}")
        return pages_text

    # ------------------------------------------------------------------
    # OCR extraction (pytesseract + pdf2image)
    # ------------------------------------------------------------------

    def _preprocess_image(self, pil_img) -> np.ndarray:
        """Preprocess a PIL image for better OCR accuracy.

        Pipeline: grayscale → contrast (CLAHE) → sharpen → denoise.
        """
        import cv2

        img = np.array(pil_img)
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        else:
            gray = img

        # Contrast enhancement
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        # Sharpen (unsharp mask)
        blurred = cv2.GaussianBlur(enhanced, (0, 0), sigmaX=3)
        sharpened = cv2.addWeighted(enhanced, 1.5, blurred, -0.5, 0)

        # Denoise
        denoised = cv2.fastNlMeansDenoising(sharpened, h=10)

        return denoised

    def _ocr_single_page_text(self, page_idx: int, pil_img) -> dict[str, Any]:
        """OCR a single page with dual-pass strategy. Runs in ThreadPoolExecutor.

        Pass 1 (PSM 6): Card text (names, ages, etc.)
        Pass 2 (PSM 3): EPIC voter IDs (same 300 DPI image, no duplicate conversion).

        Returns dict with page_idx, text, epic_map, failed.
        """
        import pytesseract

        page_num = page_idx + 1
        result: dict[str, Any] = {
            "page_idx": page_idx,
            "text": "",
            "epic_map": {},
            "failed": False,
        }

        # Pass 1: PSM 6 for card text
        try:
            processed = self._preprocess_image(pil_img)
            result["text"] = pytesseract.image_to_string(
                processed, lang="tam+eng",
                config="--oem 3 --psm 6",
            )
        except Exception as e:
            logger.warning("Page %d: OCR pass 1 failed — %s", page_num, e)
            result["failed"] = True

        # Pass 2: PSM 3 for EPIC voter IDs (reuse same image — no 400 DPI needed)
        try:
            text_psm3 = pytesseract.image_to_string(
                pil_img, lang="tam+eng",
                config="--oem 3 --psm 3",
            )
            result["epic_map"] = self._extract_name_epic_map(text_psm3)
            if result["epic_map"]:
                logger.info(
                    "Page %d: found %d name→EPIC mappings via PSM 3",
                    page_num, len(result["epic_map"]),
                )
        except Exception as e:
            logger.warning("Page %d: EPIC extraction failed — %s", page_num, e)

        return result

    def _ocr_extract(
        self,
        path: Path,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> list[str]:
        """Extract text via OCR for scanned PDFs.

        Dual-pass OCR strategy per page (both at 300 DPI — single conversion):
          Pass 1 (PSM 6): Card text (names, father names, house numbers, ages, genders)
          Pass 2 (PSM 3): EPIC voter IDs

        Pages are processed in parallel using ThreadPoolExecutor.
        EPIC IDs are stored in self._page_epic_maps for later assignment.
        """
        try:
            import pytesseract
        except ImportError:
            raise RuntimeError(
                "pytesseract is required for scanned PDFs. "
                "Install with: pip install pytesseract"
            )

        if progress_callback:
            progress_callback(10, "Converting PDF to images...")

        try:
            images = convert_from_path(str(path), dpi=300)
        except Exception as e:
            raise RuntimeError(f"pdf2image conversion failed: {e}. Ensure poppler is installed.")

        total = len(images)

        if progress_callback:
            progress_callback(15, f"OCR-ing {total} pages in parallel...")

        # Process pages in parallel — pytesseract spawns subprocesses so GIL is not a bottleneck
        from concurrent.futures import ThreadPoolExecutor, as_completed

        page_results: list[dict] = [None] * total  # type: ignore[list-item]
        completed_count = 0

        page_threads = int(os.environ.get("VOTER_PAGE_THREADS",
                                              str(min(os.cpu_count() or 4, 8))))
        with ThreadPoolExecutor(max_workers=page_threads) as page_executor:
            futures = {
                page_executor.submit(self._ocr_single_page_text, i, img): i
                for i, img in enumerate(images)
            }
            for future in as_completed(futures):
                page_idx = futures[future]
                try:
                    page_results[page_idx] = future.result(timeout=120)
                except Exception as e:
                    logger.warning("Page %d: OCR timed out or failed — %s", page_idx + 1, e)
                    page_results[page_idx] = {
                        "page_idx": page_idx, "text": "", "epic_map": {}, "failed": True,
                    }
                completed_count += 1
                if progress_callback:
                    pct = 15 + int(completed_count / max(total, 1) * 15)
                    progress_callback(pct, f"OCR: {completed_count}/{total} pages done")

        # Collect results in page order
        pages_text: list[str] = []
        self._page_epic_maps: list[dict[str, str]] = []
        failed_pages: list[int] = []

        for pr in page_results:
            if pr is None:
                pages_text.append("")
                self._page_epic_maps.append({})
                continue
            pages_text.append(pr["text"])
            self._page_epic_maps.append(pr["epic_map"])
            if pr["failed"]:
                failed_pages.append(pr["page_idx"] + 1)

        if failed_pages:
            logger.warning(
                "OCR: %d/%d page(s) failed: %s", len(failed_pages), total, failed_pages
            )

        return pages_text

    # ------------------------------------------------------------------
    # Section / street name extraction (per-page)
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_section_name(page_text: str) -> str:
        """Extract section/street name from a page's header text.

        Looks for "பிரிவு எண் மற்றும் பெயர்" (Section Number and Name)
        and captures everything after it on that line (and optionally the
        next line if it continues).

        Returns the section name string, or "" if not found.
        """
        page_text = _strip_zw(page_text)
        lines = page_text.split("\n")

        for i, line in enumerate(lines):
            m = _SECTION_NAME_RE.search(line.strip())
            if m:
                section_text = m.group(1).strip()
                # If the captured text is very short, the value might
                # continue on the next line
                if len(section_text) < 5 and i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if (next_line
                            and not _AC_NO_RE.search(next_line)
                            and not _PART_NO_RE.search(next_line)
                            and not _TOTAL_VOTERS_RE.search(next_line)
                            and not _ADDRESS_LABEL_RE.search(next_line)
                            and not _SERIAL_RE.match(next_line)):
                        section_text = (section_text + " " + next_line).strip()
                # Strip leading numbering like "1-", "2-" from each
                # comma/semicolon-separated address segment.
                # e.g. "1-தெரு பெயர், 2-வேறு தெரு" → "தெரு பெயர், வேறு தெரு"
                parts = re.split(r'[,;]\s*', section_text)
                cleaned = [re.sub(r'^\d+\s*[-–—.]\s*', '', p).strip() for p in parts]
                section_text = ', '.join(c for c in cleaned if c)
                return section_text

        return ""

    # ------------------------------------------------------------------
    # Header parsing
    # ------------------------------------------------------------------

    def _parse_header(self, page_text: str):
        """Extract AC No, Part No, address, total voters from page text.

        Only sets values that haven't been found yet, so it's safe to call
        on multiple pages to accumulate header info.
        """
        page_text = _strip_zw(page_text)

        if not self.header_info.ac_no:
            m = _AC_NO_RE.search(page_text)
            if m:
                self.header_info.ac_no = next((g for g in m.groups() if g), "")

        if not self.header_info.part_no:
            m = _PART_NO_RE.search(page_text)
            if m:
                self.header_info.part_no = next((g for g in m.groups() if g), "")

        if not self.header_info.total_voters:
            m = _TOTAL_VOTERS_RE.search(page_text)
            if m:
                self.header_info.total_voters = m.group(1)

        # Try to extract address from the "வாக்குச் சாவடியின் முகவரி" field
        if self.header_info.address:
            return

        lines = page_text.split("\n")

        # Strategy 1: Look for the explicit address label
        # (வாக்குச் சாவடியின் முகவரி / Polling Station Address)
        for i, line in enumerate(lines):
            stripped = line.strip()
            m = _ADDRESS_LABEL_RE.search(stripped)
            if m:
                # Address may be on the same line after the label
                addr_text = m.group(1).strip()
                addr_parts = []
                if addr_text:
                    addr_parts.append(addr_text)
                # Also collect continuation lines (next 1-3 lines until we hit
                # another known field or voter data)
                for j in range(i + 1, min(i + 4, len(lines))):
                    next_line = lines[j].strip()
                    if not next_line:
                        continue
                    # Stop if we hit voter data, another field label, or known patterns
                    if _SERIAL_RE.match(next_line):
                        break
                    if _AC_NO_RE.search(next_line):
                        break
                    if _PART_NO_RE.search(next_line):
                        break
                    if _TOTAL_VOTERS_RE.search(next_line):
                        break
                    if _ADDRESS_LABEL_RE.search(next_line):
                        break
                    if any(kw in next_line.lower() for kw in [
                        "electoral roll", "voter list", "வாக்காளர்", "பட்டியல்",
                        "section", "பிரிவு", "main town", "municipality",
                    ]):
                        break
                    addr_parts.append(next_line)
                if addr_parts:
                    self.header_info.address = ", ".join(addr_parts)
                    return

        # Strategy 2 (fallback): collect lines after Part No and before voter data
        address_lines = []
        in_header = True
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            # Stop collecting address once we hit voter data (serial number pattern)
            if in_header and _SERIAL_RE.match(stripped):
                in_header = False
                break
            # After finding part number, collect address-like lines
            if self.header_info.part_no and self.header_info.part_no in stripped:
                continue
            if in_header and len(address_lines) < 3:
                # Skip lines that look like headers/titles
                if any(kw in stripped.lower() for kw in ["electoral roll", "voter list", "வாக்காளர்", "பட்டியல்"]):
                    continue
                if stripped and not _AC_NO_RE.search(stripped) and not _TOTAL_VOTERS_RE.search(stripped):
                    address_lines.append(stripped)

        if address_lines:
            self.header_info.address = ", ".join(address_lines[-2:])

    # ------------------------------------------------------------------
    # Voter record parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _is_false_positive_voter(voter: "VoterRecord") -> bool:
        """Check if a voter record is actually metadata/header text misidentified.

        IMPORTANT: Never drop a record that has a valid EPIC (voter ID) or
        strong secondary evidence. Real voters must NEVER be discarded.
        """
        name = voter.name.strip()
        if not name:
            # Even with empty name, if voter has EPIC, keep them (name will be set to EPIC later)
            return not bool(voter.voter_id)

        # CRITICAL: A voter with a valid EPIC is ALWAYS a real voter — never drop
        if voter.voter_id:
            return False

        # --- Cover page summary cell detection ---
        # Standalone gender/category words from summary tables are NOT voters.
        # e.g. name="ஆண்" with gender="Male" but no EPIC/age/house/father
        name_bare = re.sub(r'\s+', '', name)
        _summary_names = {
            'ஆண்', 'பெண்', 'ஆண', 'பெண',
            'மூன்றாம்பாலினம்', 'பொது', 'மொத்தம்',
            'வரிசை', 'எண்ணிக்கை', 'திருத்தம்',
        }
        if name_bare in _summary_names:
            return True
        # Also catch partial OCR of summary labels (e.g. "மற்றும் ஒ")
        _summary_fragments = (
            'மற்றும் ஒ', 'தீவிர திருத்தம்', 'ப்பன்னி',
            'சிறப்பு திருத்தம்', 'supplement', 'amendment',
            'deletion', 'revision',
        )
        name_lower = name.lower()
        for frag in _summary_fragments:
            if frag in name_lower:
                return True

        # Count how many secondary fields this record has
        evidence_count = sum([
            bool(voter.father_husband_name and len(voter.father_husband_name.strip()) > 2),
            bool(voter.age),
            bool(voter.gender),
            bool(voter.house_no and voter.house_no.strip()),
        ])

        # Any secondary evidence means this is likely a real voter — keep
        if evidence_count >= 1:
            return False

        # Header keywords that indicate this is metadata, not a voter
        # (Only strong, unambiguous header-only keywords — removed city names
        # and common Tamil words that could appear in voter names)
        metadata_kw = (
            'சாவடி', 'தொகுதி', 'பட்டியல்', 'வாக்காளர்',
            'ஊராட்சி', 'சட்டமன்ற', 'நாடாளுமன்ற',
            'electoral', 'constituency', 'polling', 'station',
            'கையொப்பம்', 'google', 'map', 'nazri', 'naksha',
            'ஆண்/பெண்', 'frade', 'bape',
            'amendment', 'supplement', 'revision', 'deletion',
        )
        name_lower = name.lower()

        # No evidence fields: apply metadata checks
        tamil_chars = len(re.findall(r'[\u0B80-\u0BFF]', name))

        # Early rejection: garbage names that are too short or pure ASCII noise
        if len(name) <= 1:
            return True
        if len(name) <= 2 and tamil_chars <= 1:
            return True
        if re.fullmatch(r'[a-z]{1,5}', name):
            return True

        if any(kw in name_lower for kw in metadata_kw):
            return True
        # Pattern: "digit-CityName" or "(மா)" (municipality) — page header metadata
        if re.search(r'^\d+\s*[-–]\s*\S', name):
            return True
        if '(மா)' in name or '(ந)' in name or '(பே)' in name:
            return True
        # Names with only punctuation/symbols
        if not re.search(r'[\w\u0B80-\u0BFF]', name):
            return True
        # Excessively long names are typically OCR garbage (real names < 60 chars)
        if len(name) > 80:
            return True
        # Names that are mostly ASCII/Latin (OCR noise) with very few Tamil chars
        ascii_chars = len(re.findall(r'[a-zA-Z]', name))
        if ascii_chars > 10 and tamil_chars < 3:
            return True
        # Names containing special chars — clean rather than drop
        if re.search(r'[{}\[\]|]', name):
            return False
        # Very short names with mostly non-Tamil chars are likely noise
        if tamil_chars < 2 and len(name) > 3:
            return True
        # Keep voters with Tamil name content even without secondary fields
        if tamil_chars >= 3:
            return False
        # A real voter should have at least name + (age or gender or voter_id)
        has_secondary = bool(voter.age or voter.gender or voter.voter_id)
        if not has_secondary:
            has_father = bool(voter.father_husband_name and voter.father_husband_name.strip())
            has_house = bool(voter.house_no and voter.house_no.strip())
            if has_father and tamil_chars >= 4:
                return False
            if has_house and tamil_chars >= 3:
                return False
            if tamil_chars >= 6:
                return False
            return True
        return False

    def _parse_voters_from_text(
        self,
        page_text: str,
        page_epic_map: Optional[dict[str, str]] = None,
    ) -> list[VoterRecord]:
        """Parse voter records from a page of text.

        Tries multiple strategies in order:
        0. Card-row parsing (3-column Tamil voter card OCR layout)
        1. Structured table parsing (tab/multi-space separated columns)
        2. Block-based parsing (serial numbers at line starts)
        3. EPIC-anchor splitting (split by voter ID patterns)
        4. Field-label splitting (split by Name:/பெயர்: labels)

        If strategies 1 or 2 produce far fewer results than the number of
        EPIC IDs in the text, we try strategy 3/4 instead.

        Args:
            page_text: OCR text from one page.
            page_epic_map: Optional name→EPIC mapping from PSM 3 OCR pass.
        """
        # Strip zero-width chars that Tamil OCR commonly inserts
        clean_text = _strip_zw(page_text)
        lines = clean_text.split("\n")

        # Count EPIC IDs in text as a quality benchmark
        epic_count = len(_EPIC_RE.findall(clean_text))

        # Strategy 0: Card-row parsing for 3-column Tamil voter lists
        # (OCR of scanned voter PDFs produces interleaved multi-column data)
        card_voters = self._parse_voters_card_rows(lines, page_epic_map)
        if card_voters and len(card_voters) >= 3:
            logger.info(f"Card-row parsing: {len(card_voters)} voters from page")
            return card_voters

        # Strategy 1: Try structured table parsing (tab/multi-space separated)
        table_voters = self._parse_as_table(lines)
        if table_voters and (epic_count == 0 or len(table_voters) >= epic_count * 0.7):
            return table_voters

        # Strategy 2: Block-based parsing (common in Indian voter lists)
        block_voters = self._parse_as_blocks(lines)
        if block_voters and (epic_count == 0 or len(block_voters) >= epic_count * 0.7):
            return block_voters

        # Strategy 3: EPIC-anchor + field-label based splitting
        # (handles concatenated text blobs from card-based PDFs)
        field_voters = self._parse_voters_from_cell_text(clean_text)
        if field_voters:
            return field_voters

        # Return best result from earlier strategies if field parsing also failed
        if table_voters:
            return table_voters
        if block_voters:
            return block_voters

        return []

    @staticmethod
    def _clean_name(name: str) -> str:
        """Remove OCR artifacts from voter/father names."""
        # Remove trailing artifacts: " - ; ;", " ; ;", trailing " ."
        name = re.sub(r'\s*-?\s*;\s*;?\s*$', '', name)
        name = re.sub(r'\s+\.\s*$', '', name)
        # --- Remove LEADING label prefixes that leaked into the value ---
        # e.g. "தந்தையின் பெயர்: முத்துசாமி" → "முத்துசாமி"
        # e.g. "தந்த ன் பெயர்: முத்துசாமி" → "முத்துசாமி" (garbled)
        name = re.sub(
            r'^(?:தந்தை(?:யின்)?\s*.{0,6}(?:பெயர்|பயர்)'
            r'|தந்த.{0,8}(?:பெயர்|பயர்)'
            r'|கணவர்\s*.{0,4}(?:பெயர்|பயர்)'
            r'|இதர(?:ர்)?\s*.{0,4}(?:பெயர்|பயர்)'
            r'|தாயின்\s*.{0,4}(?:பெயர்|பயர்)'
            r'|பெயர்'
            r')\s*:?\s*',
            '', name
        )
        # --- Remove TRAILING label fragments that leaked into the name ---
        # Each pattern requires the relation keyword + பெயர்/பயர் to avoid
        # matching legitimate name substrings.
        # e.g. "ஊமத்துரை - தந்தையின் பெயர்: ஊமத்துரை" → "ஊமத்துரை"
        name = re.sub(
            r'\s*-?\s*(?:தந்தையின்|தந்தை)\s*(?:leit|lelt|lett|peit|lest|leat)?\s*(?:பெயர்|பயர்)\s*:?\s*.*$',
            '', name
        )
        name = re.sub(
            r'\s*-?\s*கணவர்\s*(?:leit|lelt|lett|peit|lest|leat)?\s*(?:பெயர்|பயர்)\s*:?\s*.*$',
            '', name
        )
        name = re.sub(
            r'\s*-?\s*(?:இதரர்|தாயின்)\s*(?:leit|lelt|lett|peit|lest|leat)?\s*(?:பெயர்|பயர்)\s*:?\s*.*$',
            '', name
        )
        # Remove "கணவர் N பயர்:" type garbled patterns (require பெயர்/பயர்)
        name = re.sub(r'கணவர்\s*\d*\s*(?:பயர்|பெயர்)\s*:?\s*', '', name)
        # Remove trailing bare "பெயர் :" (leaked label with no preceding keyword)
        name = re.sub(r'\s*பெயர்\s*:?\s*$', '', name)
        # --- Remove field-label lines that leaked into the name ---
        # e.g. "வீட்டு எண் : 111" should not be a name
        name = re.sub(
            r'^(?:வீட்டு\s*எண்|ட்டு\s*எண்|வயது|பாலினம்|Photo\s+is)\s*:?\s*.*$',
            '', name
        )
        name = name.strip().rstrip(' -.:;')
        return name

    # Tamil letter → English letter mapping for house number sub-units
    _TAMIL_HOUSE_LETTER_MAP: dict[str, str] = {
        'அ': 'A', 'ஆ': 'A', 'ஏ': 'A',
        'பி': 'B', 'பீ': 'B',
        'சி': 'C', 'சீ': 'C',
        'டி': 'D', 'டீ': 'D',
        'இ': 'E',
        'எஃப்': 'F',
        'ஜி': 'G',
        'எச்': 'H',
        'ஐ': 'I',
        'ஜே': 'J', 'ஜெ': 'J',
        'கே': 'K', 'கெ': 'K',
        'எல்': 'L',
        'எம்': 'M',
        'என்': 'N',
    }

    # OCR letter→digit confusion map for characters inside numeric segments.
    # These are letters commonly misread by OCR when the correct char is a digit.
    _LETTER_TO_DIGIT: dict[str, str] = {
        'O': '0', 'o': '0', 'Q': '0',
        'l': '1', 'I': '1', 'i': '1', '|': '1',
        'Z': '2', 'z': '2',
        'S': '5', 's': '5',
        'B': '8', 'b': '8',
        'G': '6', 'g': '6',
        'D': '0', 'T': '7',
    }

    # Letters that look like digits and should NOT be treated as intentional
    # house-number suffixes. These are almost never used as real house number
    # subdivisions in Indian voter rolls, so if they appear as trailing chars,
    # they are more likely OCR-garbled digits.
    # Note: B, D, G ARE legitimate suffixes so they're excluded from this set.
    _AMBIGUOUS_SUFFIX_LETTERS: set[str] = {'O', 'I', 'S', 'Z', 'T'}

    @staticmethod
    def _fix_ocr_digit_confusion(h: str) -> str:
        """Fix OCR letter↔digit confusion in house number numeric segments.

        House numbers follow patterns like "123", "1/8", "1-21B", "08/191".
        Numeric segments (groups of digits possibly mixed with OCR-garbled
        letters) should be pure digits. A trailing single letter (A-Z suffix)
        is intentional and preserved — UNLESS the letter itself commonly
        looks like a digit (O, I, S, B, D, G, Z, T).

        Single-letter tokens after separators (e.g., "15/B") are preserved
        as letter subdivisions.

        Examples:
            "l2"    → "12"    (lowercase L → 1)
            "O8"    → "08"    (letter O → 0)
            "1S3"   → "153"   (letter S → 5)
            "l-2lB" → "1-21B" (B is unambiguous suffix)
            "O8/l9l"→ "08/191"
            "12B"   → "12B"   (trailing letter suffix kept)
            "3O"    → "30"    (O is ambiguous, treated as 0)
            "15/B"  → "15/B"  (single-letter token = subdivision)
            "12A"   → "12A"   (A is unambiguous suffix)
        """
        if not h:
            return h

        # Split house number into tokens by separators (-, /)
        # Preserve separators for reassembly
        tokens = re.split(r'([-/])', h)
        result_parts = []

        for idx, token in enumerate(tokens):
            # Separators pass through unchanged
            if token in ('-', '/'):
                result_parts.append(token)
                continue

            if not token:
                result_parts.append(token)
                continue

            # Single-letter token after a separator (e.g., "B" in "15/B")
            # is a letter subdivision — preserve as-is
            if len(token) == 1 and token.isalpha() and idx > 0:
                result_parts.append(token)
                continue

            # Determine if this token ends with a letter suffix (e.g., "21B", "8C")
            # Only the LAST token in the house number can have a letter suffix.
            # Letters that commonly look like digits (O, I, S, B, etc.) are NOT
            # treated as suffixes — they are more likely OCR-garbled digits.
            is_last_token = idx == len(tokens) - 1
            suffix = ""
            core = token
            if is_last_token and len(token) >= 2 and token[-1].isalpha() and token[-1].isupper():
                last_char = token[-1]
                # Only treat as suffix if the letter is NOT commonly confused with a digit
                if last_char not in VotersPDFProcessor._AMBIGUOUS_SUFFIX_LETTERS:
                    before_suffix = token[:-1]
                    has_digit_like = any(
                        c.isdigit() or c in VotersPDFProcessor._LETTER_TO_DIGIT
                        for c in before_suffix
                    )
                    if has_digit_like:
                        suffix = last_char
                        core = before_suffix

            # Fix letter→digit confusion in the core numeric part
            fixed_chars = []
            for c in core:
                if c.isdigit():
                    fixed_chars.append(c)
                elif c in VotersPDFProcessor._LETTER_TO_DIGIT:
                    fixed_chars.append(VotersPDFProcessor._LETTER_TO_DIGIT[c])
                else:
                    # Unknown char — keep as-is (could be legitimate)
                    fixed_chars.append(c)

            result_parts.append(''.join(fixed_chars) + suffix)

        return ''.join(result_parts)

    @staticmethod
    def _clean_house_no(h: str) -> str:
        """Clean OCR artifacts from a house number value.

        Handles:
        - Trailing/leading dashes and underscores: "15 _- -" → "15"
        - "Photo" text leakage: "15 - Photo 6" → "15"
        - Tamil "எண்" prefix: "எண் 08/191" → "08/191"
        - Tamil letter sub-units: "15 அ" → "15A", "3 சி" → "3C"
        - Stray OCR-garbled Tamil chars (not letter sub-units): "43 ர" → "43"
        - "&" OCR misread of "A" or "/": "36&" → "36A"
        - Alphanumeric house numbers preserved: "1A", "1/8", "56J/11"
        - OCR letter↔digit confusion: "O8" → "08", "l2" → "12", "1S3" → "153"
        """
        if not h:
            return h
        # Strip leading special characters (OCR noise)
        h = h.lstrip(';:!@#$%^*+=')
        # Remove "Photo is ..." leakage
        h = re.sub(r'\s*Photo\s+is.*$', '', h, flags=re.IGNORECASE).strip()
        h = re.sub(r'\s*Photo\s*\d*\s*$', '', h, flags=re.IGNORECASE).strip()
        # Remove Tamil "எண்" prefix (means "Number")
        h = re.sub(r'^எண்\s*\.?\s*', '', h).strip()
        # Replace "&" with "A" (common OCR misread)
        h = h.replace('&', 'A')
        # Convert Tamil letter sub-units to English equivalents
        # e.g. "15 அ" → "15A", "3/சி" → "3/C", "56ஜே" → "56J"
        for tamil_ch, eng_ch in VotersPDFProcessor._TAMIL_HOUSE_LETTER_MAP.items():
            if tamil_ch in h:
                # Replace Tamil letter (with optional preceding space/slash)
                h = re.sub(r'[\s/]*' + re.escape(tamil_ch), eng_ch, h)
        # Remove remaining stray single Tamil chars that are NOT known sub-units
        # (garbled OCR noise like isolated "ர", "ண", etc.)
        h = re.sub(r'\s+[\u0B80-\u0BFF](?:\s|$)', '', h).strip()
        # Remove trailing OCR noise: sequences of _ . ; spaces (preserve internal hyphens)
        h = re.sub(r'[\s_\.;]+$', '', h).strip()
        # Remove only trailing hyphens/underscores/dots/semicolons (preserve internal hyphens like "1-21B")
        h = h.rstrip(' _.;')
        # Strip leading underscores/dots only
        h = h.lstrip(' _.')
        # Only strip leading/trailing hyphens if they are not part of the house number
        if h.startswith('-') and not re.match(r'-\d', h):
            h = h.lstrip('-')
        if h.endswith('-'):
            h = h.rstrip('-')
        # If result is empty or just dashes, return empty
        if not h or re.fullmatch(r'[\s_\-\.]+', h):
            return ""
        # Reject house numbers with no digits AND no digit-like letters
        # (after OCR fix, letters like "O", "l" may represent digits)
        if not re.search(r'[\dOoQlIiSsZzBbGgDT|]', h):
            return ""
        # Fix OCR letter↔digit confusion in numeric segments
        # e.g., "O8" → "08", "l2" → "12", "l-2lB" → "1-21B"
        h = VotersPDFProcessor._fix_ocr_digit_confusion(h)
        # Strip trailing English words (e.g., "4671 STREET" → "4671")
        h = re.sub(r'\s+[A-Za-z]{3,}.*$', '', h).strip()
        # Strip trailing text after comma (e.g., "16J,SWETHAN" → "16J", "121,சண்முகா" → "121")
        h = re.sub(r',[A-Za-z]{3,}.*$', '', h).strip()
        h = re.sub(r',[\u0B80-\u0BFF]{2,}.*$', '', h).strip()
        # Reject excessively long values (real house numbers are short)
        if len(h) > 20:
            return ""
        if not h or not re.search(r'\d', h):
            return ""
        return h

    @staticmethod
    def _fix_house_numbers_contextual(voters: list["VoterRecord"]) -> None:
        """Fix OCR digit↔letter confusion in house numbers using page context.

        If most house numbers on a page have letter suffixes (e.g., "1-21A",
        "1-22C"), then "1-218" is likely "1-21B" (OCR confused B→8).

        Common OCR confusions: B↔8, C↔0, D↔0, A↔4, G↔6, S↔5, Z↔2, I↔1
        """
        if not voters:
            return

        # Analyze house number patterns
        with_letter_suffix = 0
        with_digit_only_suffix = 0
        # Pattern: something followed by a letter at the end
        _letter_suffix_re = re.compile(r'[-/]\d*[A-Za-z]$|^\d+[A-Za-z]$')
        # Pattern: ends with digits after separator, last digit could be OCR'd letter
        _digit_suffix_re = re.compile(r'[-/]\d+$')

        for v in voters:
            h = v.house_no
            if not h:
                continue
            if _letter_suffix_re.search(h):
                with_letter_suffix += 1
            elif _digit_suffix_re.search(h):
                with_digit_only_suffix += 1

        # If majority have letter suffixes, fix suspicious digit-only endings
        if with_letter_suffix < 3 or with_letter_suffix <= with_digit_only_suffix:
            return

        # Reverse OCR confusion map: digit → most likely letter
        _DIGIT_TO_LETTER = {
            '8': 'B', '0': 'C', '4': 'A', '6': 'G',
            '5': 'S', '2': 'Z', '1': 'I', '7': 'T',
        }

        fixed_count = 0
        for v in voters:
            h = v.house_no
            if not h:
                continue
            # Match house numbers ending with a suspicious digit after separator
            # e.g., "1-218" → could be "1-21B", "1-80" → could be "1-8C"
            m = re.match(r'^(.+[-/]\d*)(\d)$', h)
            if m and m.group(2) in _DIGIT_TO_LETTER:
                v.house_no = m.group(1) + _DIGIT_TO_LETTER[m.group(2)]
                fixed_count += 1
            elif not _letter_suffix_re.search(h):
                # Standalone numbers like "128" → "12B" when pattern says letter suffix
                m2 = re.match(r'^(\d+)(\d)$', h)
                if m2 and m2.group(2) in _DIGIT_TO_LETTER and len(h) >= 2:
                    v.house_no = m2.group(1) + _DIGIT_TO_LETTER[m2.group(2)]
                    fixed_count += 1

        if fixed_count:
            logger.info(f"[HOUSE-FIX] Contextual fix applied to {fixed_count} house numbers")

    @staticmethod
    def _extract_house_numbers(line: str) -> list[str]:
        """Extract house numbers from a house-number line, including garbled OCR variants.

        Handles alphanumeric house numbers like "1A", "1/A", "12B", "3/1".
        Tamil OCR often garbles "வீட்டு எண்:" into patterns like:
          "GLO) crevor:", "ALG) crovor:", "LQ) erevor:", "LG) srevor:"
        This method handles both correct Tamil and garbled variants.
        """
        # Primary: correct Tamil patterns (வீட்டு எண், ட்டு எண், ட்டுஎண்)
        # Capture full alphanumeric house numbers including hyphens, slashes,
        # and letter suffixes (e.g. "1A", "1/A", "12B", "1-21B", "1-8C", "1&")
        houses = re.findall(
            r'(?:வீட்டு|ட்டு|ட்டுஎ)\s*எண்\s*:?\s*(\d[\w/\-&.]*)',
            line,
        )
        # Clean up: "&" is OCR misread of "A", remove trailing punctuation
        houses = [re.sub(r'&', 'A', h).rstrip('.,;: ') for h in houses]

        # Secondary: garbled OCR patterns that replace Tamil with Latin chars
        # These look like "GLO) crevor: 32" or "ALG) crovor: 13"
        garbled = re.findall(
            r'[A-Z]{2,4}\)\s*[a-z]*(?:evor|revor|rovor)\s*:?\s*(\d[\w/\-&.]*)',
            line,
        )
        if garbled:
            garbled = [re.sub(r'&', 'A', g).rstrip('.,;: ') for g in garbled]
            # Garbled OCR sometimes appends extra digits (e.g. "320" for "32").
            # If Tamil-extracted houses exist, use their length as a guide.
            if houses:
                max_len = max(len(h) for h in houses)
                cleaned = []
                for g in garbled:
                    if len(g) > max_len:
                        g = g[:max_len]  # Truncate to match nearby house number lengths
                    cleaned.append(g)
                houses.extend(cleaned)
            else:
                houses.extend(garbled)
        return houses

    def _parse_voters_card_rows(
        self,
        lines: list[str],
        page_epic_map: Optional[dict[str, str]] = None,
    ) -> list[VoterRecord]:
        """Parse voter records from 3-column card layout OCR text.

        Tamil Nadu electoral roll PDFs use a 3-column card layout. When OCR'd,
        each row of 3 cards produces interleaved lines:

            பெயர் : NAME1 - பெயர் : NAME2 - பெயர் : NAME3
            தந்தையின் பெயர்: FATHER1 - ... FATHER2 - ... FATHER3
            வீட்டு எண் : HOUSE1 Photo is வீட்டு எண் : HOUSE2 ...
            வயது : AGE1 பாலினம் : GENDER1 வயது : AGE2 ...
            available available available

        This method classifies each line and accumulates parallel lists of
        names, fathers, houses, ages, and genders, then zips them into voters.

        Args:
            lines: Pre-split text lines from PSM 6 OCR.
            page_epic_map: Optional name→EPIC mapping from PSM 3 OCR.
        """
        voters: list[VoterRecord] = []
        current_names: list[str] = []
        current_fathers: list[str] = []
        current_relation_type: str = ""  # "F" or "H" for the current row of cards
        current_per_card_relations: list[str] = []  # per-card overrides when a row mixes F/H
        current_houses: list[str] = []
        current_ages: list[str] = []
        current_genders: list[str] = []

        # Quick check: does this page have the Tamil card layout?
        full_text = "\n".join(lines)
        name_label_count = len(re.findall(r'(?:^|[\s\-])பெயர்\s*:', full_text, re.MULTILINE))
        father_label_count = len(re.findall(
            r'(?:தந்தையின்|கணவர்|இதரர்)\s*பெயர்', full_text
        ))
        if name_label_count < 3 or father_label_count < 1:
            return []

        # Per-card slot data. The 3-column layout has N card positions.
        # We fill slots as data arrives from OCR lines.
        # Format: list of dicts, one per card position (index = column position)
        card_slots: list[dict[str, str]] = []  # [{'house':'', 'age':'', 'gender':''}, ...]

        def _init_slots() -> None:
            """Initialize per-card slots to match the number of names."""
            nonlocal card_slots
            n = len(current_names)
            card_slots = [{'house': '', 'age': '', 'gender': ''} for _ in range(n)]

        def _fill_slots_houses(houses: list[str], line: str = "") -> None:
            """Fill house numbers into card slots.

            Uses 'Photo is' markers to detect how many card positions the line
            covers. If the line has 3 photos but only 2 houses, the missing
            house is at the front (garbled OCR dropped it), so the 2 houses
            go to the later positions.
            """
            if not card_slots:
                return

            n_slots = len(card_slots)
            n_houses = len(houses)
            n_photos = len(re.findall(r'Photo\s+is', line, re.IGNORECASE))

            # Determine starting slot offset
            if n_photos >= n_slots and n_houses < n_photos:
                # This is a "full-width" house line where some houses were garbled.
                # The garbled positions are at the front (L→R OCR order).
                offset = n_photos - n_houses
            else:
                # Fill into next available empty slot
                offset = 0

            slot_idx = offset
            for h in houses:
                while slot_idx < n_slots and card_slots[slot_idx]['house']:
                    slot_idx += 1
                if slot_idx < n_slots:
                    card_slots[slot_idx]['house'] = h
                    slot_idx += 1

        def _fill_slots_age_gender(ages: list[str], genders: list[str]) -> None:
            """Fill age/gender into card slots, left to right into empty slots."""
            slot_idx = 0
            for j, age in enumerate(ages):
                gender = genders[j] if j < len(genders) else ""
                while slot_idx < len(card_slots) and card_slots[slot_idx]['age']:
                    slot_idx += 1
                if slot_idx < len(card_slots):
                    card_slots[slot_idx]['age'] = age
                    card_slots[slot_idx]['gender'] = gender
                    slot_idx += 1

        def _flush() -> None:
            """Convert accumulated card data into VoterRecord objects."""
            if not current_names:
                return
            n = len(current_names)
            for i in range(n):
                name = current_names[i] if i < len(current_names) else ""
                father = current_fathers[i] if i < len(current_fathers) else ""
                slot = card_slots[i] if i < len(card_slots) else {}
                house = slot.get('house', '')
                age = slot.get('age', '')
                gender = slot.get('gender', '')

                # Clean OCR artifacts from names
                name = VotersPDFProcessor._clean_name(name)
                father = VotersPDFProcessor._clean_name(father)

                # Skip header-like false positives (constituency metadata, not voter names)
                _HEADER_LEAK_KW = (
                    'தொகுதி', 'மற்றும்', 'சட்டமன்ற', 'பாகம்', 'பகுதி',
                    'வாக்காளர்', 'பட்டியல்', 'ஊராட்சி', 'சாவடி',
                    'constituency', 'polling', 'electoral', 'supplement',
                    'amendment', 'revision', 'வெளியிடப்பட்ட', 'மொத்த',
                )
                name_lower = name.lower()
                if any(kw in name_lower for kw in _HEADER_LEAK_KW):
                    # Don't drop if the row has strong secondary evidence
                    _has_evidence = bool(father) and bool(age or gender)
                    if not _has_evidence:
                        logger.info(f"[CARD-ROW FILTER] Dropped metadata: name='{name}'")
                        continue
                # Drop names that are entirely non-Tamil (pure ASCII/digit noise)
                tamil_in_name = len(re.findall(r'[\u0B80-\u0BFF]', name))
                if tamil_in_name == 0 and not re.search(r'[a-zA-Z]{2,}', name):
                    logger.info(f"[CARD-ROW FILTER] Dropped non-Tamil noise: name='{name}'")
                    continue
                # If name has 2+ consecutive digits, try to strip them (OCR artifact)
                # rather than dropping the record entirely
                if re.search(r'\d{2,}', name):
                    cleaned = re.sub(r'\d+', '', name).strip()
                    tamil_in_cleaned = len(re.findall(r'[\u0B80-\u0BFF]', cleaned))
                    if tamil_in_cleaned >= 2:
                        # Has real Tamil name chars after removing digits — keep it
                        name = cleaned
                        logger.info(f"[CARD-ROW FILTER] Stripped digits from name: '{name}'")
                    elif not age and not gender and not father:
                        # No other fields and name is mostly digits — likely header
                        logger.info(f"[CARD-ROW FILTER] Dropped digit-heavy name: '{name}'")
                        continue

                # Use per-card relation type if available, else row-level
                rel_type = (current_per_card_relations[i]
                            if current_per_card_relations and i < len(current_per_card_relations)
                            else current_relation_type)
                voter = VoterRecord(
                    name=name,
                    father_husband_name=father,
                    house_no=VotersPDFProcessor._clean_house_no(house) if house else "",
                    age=age,
                    gender=gender,
                    relation_type=rel_type,
                )
                if voter.is_valid:
                    voters.append(voter)
                else:
                    logger.warning(f"[IS_VALID FILTER] Dropped: name='{name}' father='{father}' house='{house}' age='{age}' gender='{gender}'")

        # Regex for detecting house lines (including garbled OCR variants)
        _house_line_re = re.compile(
            r'(?:வீட்டு|ட்டு|ட்டுஎ)\s*எண்|[A-Z]{2,4}\)\s*[a-z]*(?:evor|revor|rovor)'
        )

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Classify each line by its dominant field label
            has_standalone_name = bool(re.search(r'(?:^|[\s\-])பெயர்\s*:', line))
            has_father = bool(re.search(
                r'(?:தந்தையின்|கணவர்|இதரர்)\s*(?:பெயர்|பயர்)', line
            ))
            has_house = bool(_house_line_re.search(line))
            has_age = bool(re.search(r'வயது\s*:', line))
            is_available = bool(re.match(r'^(?:available\s*)+$', line, re.IGNORECASE))

            if has_standalone_name and not has_father:
                # New row of voter cards — flush previous batch
                _flush()
                current_names = []
                current_fathers = []
                current_per_card_relations = []

                # Extract names: split by பெயர் :
                raw = re.split(r'\s*-?\s*பெயர்\s*:\s*', line)
                current_names = [
                    VotersPDFProcessor._clean_name(v)
                    for v in raw
                    if v.strip() and v.strip() not in ('-', ':')
                ]
                _init_slots()

            elif has_father:
                # Father/husband name line — detect per-card relation types.
                # A row can mix Father and Husband labels across cards.
                label_matches = list(re.finditer(
                    r'(?:தந்தையின்|கணவர்|இதரர்|தாயின்)\s*(?:பெயர்|பயர்)',
                    line,
                ))
                per_card_rels = [
                    VotersPDFProcessor._detect_relation_type(m.group(0))
                    for m in label_matches
                ]
                if len(per_card_rels) > 1:
                    current_per_card_relations = per_card_rels
                    # Use the first as default fallback
                    current_relation_type = per_card_rels[0]
                elif len(per_card_rels) == 1:
                    current_relation_type = per_card_rels[0]
                    current_per_card_relations = []
                else:
                    current_relation_type = VotersPDFProcessor._detect_relation_type(line)
                    current_per_card_relations = []
                raw = re.split(
                    r'\s*-?\s*(?:தந்தையின்|கணவர்|இதரர்|தாயின்)\s*(?:பெயர்|பயர்)\s*:?\s*',
                    line,
                )
                current_fathers = [
                    VotersPDFProcessor._clean_name(v)
                    for v in raw
                    if v.strip() and v.strip() not in ('-', ':')
                ]

            elif has_house and has_age:
                # Mixed line: house + age/gender on same line
                # e.g. "வீட்டு எண் : 7 ; ; வயது : 34 பாலினம் : ஆண் வயது : 30 பாலினம் : பெண்"
                # On a mixed line, house(s) and age(s) belong to DIFFERENT cards!
                # The house is a "recovered" house for a card whose house was garbled
                # on the previous house-only line. The ages are for the OTHER cards
                # (the ones that had their houses already placed).

                # FIRST: identify which slots already have houses (BEFORE adding mixed houses)
                n_slots = len(card_slots)
                pre_house_slots = [
                    i for i in range(n_slots)
                    if card_slots[i]['house'] and not card_slots[i]['age']
                ]

                # THEN: fill the recovered house(s) from this mixed line
                new_houses = self._extract_house_numbers(line)
                _fill_slots_houses(new_houses, line)

                new_ages = re.findall(r'வயது\s*:\s*(\d+)', line)
                new_genders_raw = re.findall(r'பாலினம்\s*:\s*(ஆண்|பெண்|மூன்றாம்\s*பாலினம்)', line)
                new_genders = [
                    "Male" if g == 'ஆண்' else ("Female" if g == 'பெண்' else "Other") for g in new_genders_raw
                ]

                # Place ages into slots that had houses BEFORE this line
                # (those are the cards whose ages appear on this mixed line)
                if pre_house_slots and len(new_ages) <= len(pre_house_slots):
                    for j, age in enumerate(new_ages):
                        gender = new_genders[j] if j < len(new_genders) else ""
                        if j < len(pre_house_slots):
                            si = pre_house_slots[j]
                            card_slots[si]['age'] = age
                            card_slots[si]['gender'] = gender
                else:
                    # Fallback: fill into any empty age slots
                    _fill_slots_age_gender(new_ages, new_genders)

            elif has_house:
                # House number line
                new_houses = self._extract_house_numbers(line)
                _fill_slots_houses(new_houses, line)

            elif has_age:
                # Age + gender line
                new_ages = re.findall(r'வயது\s*:\s*(\d+)', line)
                new_genders_raw = re.findall(r'பாலினம்\s*:\s*(ஆண்|பெண்|மூன்றாம்\s*பாலினம்)', line)
                new_genders = [
                    "Male" if g == 'ஆண்' else ("Female" if g == 'பெண்' else "Other") for g in new_genders_raw
                ]
                _fill_slots_age_gender(new_ages, new_genders)

            elif is_available:
                # Photo status line — skip but don't flush
                pass

        # Flush the last batch
        _flush()

        # Assign EPIC voter IDs by positional order from PSM 3 extraction
        if page_epic_map:
            self._assign_epics_by_position(voters, page_epic_map)

        # Fix house numbers with OCR digit↔letter confusion using page context
        self._fix_house_numbers_contextual(voters)

        # Assign serial numbers
        for i, voter in enumerate(voters, 1):
            voter.serial_no = str(i)

        return voters

    @staticmethod
    def _extract_name_epic_pairs(psm3_text: str) -> list[tuple[str, str]]:
        """Extract (name, EPIC) pairs from PSM 3 OCR text.

        PSM 3 reads each voter card individually (column by column), so the
        EPIC voter ID appears near the voter's name. This method walks
        through the PSM 3 text and associates each name with the nearest EPIC.

        Returns a list of (name, epic) tuples preserving reading order.
        Some entries may have empty EPIC if OCR didn't capture it.
        """
        clean = _strip_zw(psm3_text)
        pairs: list[tuple[str, str]] = []

        lines = clean.split('\n')
        current_name = ""
        current_epic = ""

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check for EPIC on this line
            epic_m = re.search(r'([A-Z]{3}\d{7})', line)

            # Check for standalone name (not father/husband)
            is_father = bool(re.search(
                r'(?:தந்தையின்|கணவர்|இதரர்|தாயின்)\s*(?:பெயர்|பயர்)', line
            ))
            name_m = re.match(r'[\s\-]*பெயர்\s*:\s*(.+?)(?:\s*-\s*)?$', line)

            if name_m and not is_father:
                # Save previous voter
                if current_name:
                    pairs.append((current_name, current_epic))
                current_name = name_m.group(1).strip().rstrip(' -')
                current_epic = ""
                if epic_m:
                    current_epic = epic_m.group(1)
            elif epic_m:
                if current_name and not current_epic:
                    current_epic = epic_m.group(1)

        # Save last voter
        if current_name:
            pairs.append((current_name, current_epic))

        # Also collect orphan EPICs not associated with any name
        all_epics_in_text = set(_EPIC_RE.findall(clean))
        paired_epics = set(e for _, e in pairs if e)
        orphan_epics = list(all_epics_in_text - paired_epics)

        return pairs, orphan_epics

    @staticmethod
    def _extract_name_epic_map(psm3_text: str) -> dict:
        """Extract EPIC data from PSM 3 text.

        Returns a dict with:
          'pairs': list of (name, epic) tuples
          'orphan_epics': list of EPICs not paired to names
        """
        pairs, orphans = VotersPDFProcessor._extract_name_epic_pairs(psm3_text)
        return {'pairs': pairs, 'orphan_epics': orphans}

    @staticmethod
    def _assign_epics_by_position(
        voters: list["VoterRecord"],
        epic_data: dict,
    ) -> None:
        """Assign EPIC IDs to voters by positional order matching.

        PSM 3 and PSM 6 both read cards in the same reading order
        (top-to-bottom, left-to-right), so position N in PSM 3 pairs
        corresponds to voter N from card-row parsing.

        This replaces the previous name-based matching which caused
        widespread EPIC mismatches due to OCR variations in Tamil names.
        """
        if not epic_data:
            return

        pairs = epic_data.get('pairs', [])
        orphan_epics = list(epic_data.get('orphan_epics', []))

        # Collect all EPICs in reading order: paired first, then orphans
        all_epics_ordered: list[str] = []
        for _, epic in pairs:
            if epic:
                all_epics_ordered.append(epic)
        all_epics_ordered.extend(orphan_epics)

        if not all_epics_ordered:
            return

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique_epics: list[str] = []
        for epic in all_epics_ordered:
            if epic not in seen:
                seen.add(epic)
                unique_epics.append(epic)

        # Collect EPICs already assigned to voters (from card text extraction)
        already_assigned = set(v.voter_id for v in voters if v.voter_id)

        # Assign by position: voter[i] gets epic[i], skipping already-used EPICs
        epic_idx = 0
        for voter in voters:
            if voter.voter_id:
                # Already has EPIC from card text extraction — skip
                continue
            # Skip EPICs that are already used by other voters
            while epic_idx < len(unique_epics) and unique_epics[epic_idx] in already_assigned:
                epic_idx += 1
            if epic_idx < len(unique_epics):
                voter.voter_id = unique_epics[epic_idx]
                already_assigned.add(unique_epics[epic_idx])
                epic_idx += 1

    def _parse_as_table(self, lines: list[str]) -> list[VoterRecord]:
        """Try to parse lines as a structured table with columns."""
        voters: list[VoterRecord] = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            # Split by multiple spaces or tabs
            parts = re.split(r'\s{2,}|\t', stripped)
            parts = [p.strip() for p in parts if p.strip()]

            if len(parts) < 3:
                continue

            # Check if first part is a serial number
            serial_match = re.match(r'^(\d{1,4})$', parts[0])
            if not serial_match:
                continue

            voter = VoterRecord()
            voter.serial_no = parts[0]

            # Look for EPIC in any part
            epic_found = False
            for j, part in enumerate(parts):
                epic_match = _EPIC_RE.search(part)
                if epic_match:
                    voter.voter_id = epic_match.group(1)
                    epic_found = True

            # Look for age and gender
            for part in parts:
                if not voter.gender:
                    if _GENDER_MALE.search(part):
                        voter.gender = "Male"
                    elif _GENDER_FEMALE.search(part):
                        voter.gender = "Female"
                    elif _GENDER_OTHER.search(part):
                        voter.gender = "Other"

                if not voter.age:
                    age_match = _AGE_RE.search(part)
                    if age_match:
                        age_val = int(age_match.group(1))
                        if 18 <= age_val <= 100:
                            voter.age = str(age_val)

            # Assign remaining text parts as name fields
            text_parts = []
            for part in parts[1:]:
                # Skip parts already used
                if part == voter.voter_id:
                    continue
                if part == voter.age:
                    continue
                if part in ("Male", "Female", "Other", "M", "F", "O", "ஆண்", "பெண்", "மூன்றாம் பாலினம்"):
                    continue
                text_parts.append(part)

            if len(text_parts) >= 1:
                voter.name = text_parts[0]
            if len(text_parts) >= 2:
                voter.father_husband_name = text_parts[1]
            if len(text_parts) >= 3:
                voter.house_no = VotersPDFProcessor._clean_house_no(text_parts[2])

            if voter.is_valid:
                voters.append(voter)

        return voters

    def _parse_as_blocks(self, lines: list[str]) -> list[VoterRecord]:
        """Parse voter entries as blocks separated by serial numbers or EPIC IDs.

        Indian voter list PDFs often have entries like:
          1  VOTER_NAME
             Father's Name: FATHER_NAME
             House No: 123
             Age: 45  Gender: Male
             EPIC: ABC1234567
        """
        voters: list[VoterRecord] = []
        current_block: list[str] = []
        current_serial: str = ""

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            serial_match = _SERIAL_RE.match(stripped)
            if serial_match:
                # Process previous block
                if current_block:
                    voter = self._parse_voter_block(current_serial, current_block)
                    if voter and voter.is_valid:
                        voters.append(voter)

                current_serial = serial_match.group(1)
                # Rest of the line after serial number
                rest = stripped[serial_match.end():].strip()
                current_block = [rest] if rest else []
            else:
                current_block.append(stripped)

        # Process last block
        if current_block:
            voter = self._parse_voter_block(current_serial, current_block)
            if voter and voter.is_valid:
                voters.append(voter)

        return voters

    def _parse_voter_block(self, serial: str, block_lines: list[str]) -> Optional[VoterRecord]:
        """Parse a single voter block into a VoterRecord.

        Uses _extract_voter_from_segment for consistent field extraction.
        """
        if not block_lines:
            return None

        full_text = " ".join(block_lines)

        # Check if this block contains field labels — use the structured extractor
        if _NAME_LABEL_RE.search(full_text) or _FATHER_LABEL_RE.search(full_text):
            voter = self._extract_voter_from_segment(full_text)
            voter.serial_no = serial
            return voter

        # Legacy: unlabeled block parsing
        voter = VoterRecord(serial_no=serial)

        # Extract EPIC
        epic_match = _EPIC_RE.search(full_text)
        if epic_match:
            voter.voter_id = epic_match.group(1)

        # Extract gender
        if _GENDER_FEMALE.search(full_text):
            voter.gender = "Female"
        elif _GENDER_MALE.search(full_text):
            voter.gender = "Male"

        # Extract age
        for age_match in _AGE_RE.finditer(full_text):
            age_val = int(age_match.group(1))
            if 18 <= age_val <= 100:
                voter.age = str(age_val)
                break

        # Extract house number
        house_match = re.search(r'(?:House\s*No|வீட்டு\s*எண்|H\.?No)[:\s]*([^\s,]+)', full_text, re.IGNORECASE)
        if house_match:
            voter.house_no = VotersPDFProcessor._clean_house_no(house_match.group(1))

        # Extract father/husband name
        rel_match = re.search(
            r"(?:Father(?:'s)?\s*Name|Husband(?:'s)?\s*Name|"
            r"தந்தை(?:யின்)?\s*பெயர்|கணவர்\s*பெயர்|"
            r"F/H\s*Name|S/W/D\s*of|Relation\s*Name)[:\s]*(.+?)(?:\s{2,}|$)",
            full_text,
            re.IGNORECASE,
        )
        if rel_match:
            voter.father_husband_name = rel_match.group(1).strip()
            voter.relation_type = VotersPDFProcessor._detect_relation_type(rel_match.group(0))

        # Extract name: typically the first line or first significant text
        name_match = re.search(
            r"(?:Name|பெயர்|Elector\s*Name)[:\s]*(.+?)(?:\s{2,}|$)",
            full_text,
            re.IGNORECASE,
        )
        if name_match:
            voter.name = name_match.group(1).strip()
        elif block_lines:
            # First line is often the name
            first_line = block_lines[0].strip()
            # Remove EPIC if present
            first_line = _EPIC_RE.sub("", first_line).strip()
            # Remove gender/age tokens
            first_line = re.sub(r'\b(Male|Female|Other|ஆண்|பெண்|மூன்றாம்\s*பாலினம்|M|F|O)\b', '', first_line, flags=re.IGNORECASE).strip()
            if first_line and len(first_line) > 1:
                voter.name = first_line

        return voter

    # ------------------------------------------------------------------
    # Field-delimiter based parsing (for concatenated text blobs)
    # ------------------------------------------------------------------

    def _parse_voters_from_cell_text(self, text: str) -> list[VoterRecord]:
        """Parse voter records from a concatenated text blob.

        When pdfplumber merges all voter data into one text block (common with
        card-based Tamil Nadu electoral roll PDFs), this method splits by
        EPIC voter IDs or by repeating field label patterns.

        Strategy:
          1. Find all EPIC IDs as anchors — each EPIC belongs to one voter
          2. Split text into segments around each EPIC
          3. Extract name, father name, house no, age, gender from each segment
        """
        if not text or len(text.strip()) < 20:
            return []

        # Find all EPIC IDs and their positions
        epics = list(_EPIC_RE.finditer(text))

        if epics:
            return self._split_by_epics(text, epics)

        # No EPICs found — try splitting by repeating name labels
        return self._split_by_field_labels(text)

    def _split_by_epics(self, text: str, epics: list[re.Match]) -> list[VoterRecord]:
        """Split concatenated text into voter records using EPIC IDs as anchors.

        Each voter's data surrounds their EPIC ID. We look backwards from
        each EPIC to find the name/father/house and forwards to get age/gender.
        """
        voters: list[VoterRecord] = []
        serial_counter = 0

        for idx, epic_match in enumerate(epics):
            epic_id = epic_match.group(1)
            epic_start = epic_match.start()
            epic_end = epic_match.end()

            # Determine segment boundaries
            if idx == 0:
                seg_start = 0
            else:
                # Midpoint between previous EPIC end and this EPIC start
                prev_end = epics[idx - 1].end()
                seg_start = prev_end

            if idx < len(epics) - 1:
                next_start = epics[idx + 1].start()
                seg_end = next_start
            else:
                seg_end = len(text)

            segment = text[seg_start:seg_end]
            voter = self._extract_voter_from_segment(segment)
            voter.voter_id = epic_id

            # Use auto-incrementing serial numbers for EPIC-split voters.
            # The segment boundaries don't reliably contain serial numbers.
            serial_counter += 1
            voter.serial_no = str(serial_counter)

            if voter.is_valid:
                voters.append(voter)

        return voters

    def _split_by_field_labels(self, text: str) -> list[VoterRecord]:
        """Split text by repeating field labels (Name:/பெயர்:) when no EPICs found."""
        voters: list[VoterRecord] = []

        # Split by the Name label pattern — each occurrence starts a new voter
        # Use the Tamil பெயர்: as primary split since it's most common
        splits = re.split(
            r'(?=(?:பெயர்\s*:|Name\s*:|Elector\s*Name\s*:))',
            text,
            flags=re.IGNORECASE,
        )

        serial_counter = 0
        for chunk in splits:
            chunk = chunk.strip()
            if not chunk or len(chunk) < 5:
                continue

            # Skip if it looks like a header/metadata chunk
            if any(kw in chunk.lower() for kw in [
                "electoral roll", "voter list", "வாக்காளர் பட்டியல்",
            ]):
                continue

            voter = self._extract_voter_from_segment(chunk)

            if not voter.serial_no:
                serial_counter += 1
                voter.serial_no = str(serial_counter)
            else:
                try:
                    serial_counter = int(voter.serial_no)
                except ValueError:
                    serial_counter += 1

            if voter.is_valid:
                voters.append(voter)

        return voters

    # Regex for field labels that should start new lines (used by _collapse_non_label_newlines)
    _FIELD_LABEL_RE = re.compile(
        r'^\s*(?:'
        r'பெயர்\s*:|Name\s*:|Elector\s*Name\s*:'      # Name label
        r'|தந்தை|கணவர்|இதர|தாயின்'                      # Relation labels (Tamil)
        r'|தந்த\w*\s*.*(?:பெயர்|பயர்)'                  # OCR-garbled father label
        r'|Father|Husband|Mother'                         # Relation labels (English)
        r'|F/H\s*Name|S/W/D'                              # English shorthand
        r'|வீட்டு\s*எண்|ட்டு\s*எண்|House\s*No'          # House number
        r'|வயது\s*:?|Age\s*:?'                            # Age
        r'|பாலினம்\s*:?|Gender\s*:?'                      # Gender
        r'|Photo\s+is'                                     # Photo marker
        r'|[A-Z]{3}\d{7}'                                  # EPIC voter ID
        r'|\d{1,4}\s+[A-Z]{3}\d{7}'                       # Serial + EPIC
        r')',
        re.IGNORECASE,
    )

    # Regex to detect that a father/relation label exists somewhere in text
    _HAS_RELATION_LABEL_RE = re.compile(
        r'தந்தை|கணவர்|இதர(?:ர்)?|தாயின்'
        r'|Father|Husband|Mother|F/H\s*Name|S/W/D',
        re.IGNORECASE,
    )

    @staticmethod
    def _collapse_non_label_newlines(text: str) -> str:
        """Collapse newlines that don't precede a field label into spaces.

        Tamil voter card text reconstructed from word positions may split
        names across lines. This method joins continuation lines back to
        their parent field while preserving label-starting newlines.

        IMPORTANT: Only collapses when a father/relation label EXISTS in
        the text. If there is no father label, non-label lines are kept
        separate so the fallback can use them as unlabeled father names.

        Example:
            "பெயர் : கொளஞ்\\nசி\\nதந்தையின் பெயர்: செல்வராசு"
            → "பெயர் : கொளஞ் சி\\nதந்தையின் பெயர்: செல்வராசு"
        """
        lines = text.split('\n')
        if len(lines) <= 1:
            return text

        # If there is no father/relation label in the text, non-label Tamil
        # lines are likely unlabeled father names — keep them separate.
        has_relation_label = bool(
            VotersPDFProcessor._HAS_RELATION_LABEL_RE.search(text)
        )

        if not has_relation_label:
            return text

        collapsed = [lines[0]]
        for line in lines[1:]:
            if VotersPDFProcessor._FIELD_LABEL_RE.search(line):
                # This line starts a new field — keep the newline
                collapsed.append(line)
            else:
                # Continuation line — join to previous with space
                collapsed[-1] = collapsed[-1] + ' ' + line

        return '\n'.join(collapsed)

    def _extract_voter_from_segment(self, segment: str) -> VoterRecord:
        """Extract a single voter's fields from a text segment.

        Handles both labeled (Name: X, Father: Y) and unlabeled text.
        """
        # Strip zero-width chars for reliable regex matching
        segment = _strip_zw(segment)
        # Collapse continuation lines so split names are reconstructed
        segment = VotersPDFProcessor._collapse_non_label_newlines(segment)
        voter = VoterRecord()

        # --- EPIC ---
        epic_match = _EPIC_RE.search(segment)
        if epic_match:
            voter.voter_id = epic_match.group(1)
        else:
            # Try fuzzy EPIC (handles OCR errors: O↔0, I↔1, l↔1)
            fuzzy_match = _EPIC_FUZZY_RE.search(segment)
            if fuzzy_match:
                normalized = _normalize_epic(fuzzy_match.group(1))
                if normalized:
                    voter.voter_id = normalized

        # --- Name ---
        # Try labeled name first, then fallback to line-based extraction.
        # The lookahead uses full relation label patterns (keyword + பெயர்) to
        # avoid stopping prematurely on partial keyword matches inside names.
        name_match = re.search(
            r'(?:பெயர்|Name|Elector\s*Name)\s*:?\s*(.+?)'
            r'(?=\s*(?:தந்தை(?:யின்)?\s*(?:[^\u0B80-\u0BFF]{0,4})?\s*(?:பெயர்|பயர்)'
            r'|கணவர்\s*(?:[^\u0B80-\u0BFF]{0,4})?\s*(?:பெயர்|பயர்)'
            r'|இதர(?:ர்)?\s*(?:[^\u0B80-\u0BFF]{0,4})?\s*(?:பெயர்|பயர்)'
            r'|தாயின்\s*(?:[^\u0B80-\u0BFF]{0,4})?\s*(?:பெயர்|பயர்))'
            r'|(?:Father|Husband|Mother)(?:\s*(?:\'s)?)?\s*(?:Name)?'
            r'|F/H\s*Name|S/W/D\s*of'
            r'|வீட்டு\s*எண்|ட்டு\s*எண்|House\s*No'
            r'|வயது\s*:?|Age\s*:?'
            r'|பாலினம்\s*:?|Gender\s*:?'
            r'|[A-Z]{3}\d{7}'
            r'|Photo\s+is'
            r'|\n|$)',
            segment,
            re.IGNORECASE,
        )
        if name_match:
            name = name_match.group(1).strip()
            # Clean up: remove trailing punctuation and "Photo" markers
            name = re.sub(r'\s*Photo\s+is.*$', '', name, flags=re.IGNORECASE).strip()
            name = VotersPDFProcessor._clean_name(name)
            name = name.rstrip(' .,;:-')
            if name:
                voter.name = name

        # Fallback: if no labeled name found, use first line with ≥3 Tamil chars
        if not voter.name:
            for line in segment.split('\n'):
                line = line.strip()
                tamil_count = len(re.findall(r'[\u0B80-\u0BFF]', line))
                # Skip lines that are pure EPIC or serial numbers
                if _EPIC_RE.search(line) and tamil_count < 3:
                    continue
                if re.fullmatch(r'\d{1,4}', line.strip()):
                    continue
                if tamil_count >= 3:
                    cleaned = VotersPDFProcessor._clean_name(line)
                    cleaned = cleaned.rstrip(' .,;:-')
                    if cleaned and len(cleaned) >= 2:
                        voter.name = cleaned
                        break

        # --- Father/Husband Name ---
        # Handle OCR variations of தந்தை/கணவர்/தாயின்/இதரர்.
        # Use [^\u0B80-\u0BFF]{0,4} (non-Tamil noise chars only) between keyword
        # and பெயர்/பயர் to prevent consuming actual Tamil name characters.
        father_match = re.search(
            r"(?:தந்தை(?:யின்)?\s*(?:[^\u0B80-\u0BFF]{0,4})?\s*(?:பெயர்|பயர்)"
            r"|தந்த.{0,8}(?:பெயர்|பயர்)"                     # OCR-garbled: தந்த ன் பெயர்
            r"|கணவர்\s*(?:[^\u0B80-\u0BFF]{0,4})?\s*(?:பெயர்|பயர்)"
            r"|தாயின்\s*(?:[^\u0B80-\u0BFF]{0,4})?\s*(?:பெயர்|பயர்)"
            r"|இதர(?:ர்)?\s*(?:[^\u0B80-\u0BFF]{0,4})?\s*(?:பெயர்|பயர்)"
            r"|Father(?:'s)?\s*(?:Name)?|Husband(?:'s)?\s*(?:Name)?|Mother(?:'s)?\s*(?:Name)?"
            r"|F/H\s*Name|S/W/D\s*of|Relation\s*Name)\s*:?\s*"
            r"(.+?)(?=வீட்டு|ட்டு\s*எண்|House\s*No|வயது\s*:?|Age\s*:?|பாலினம்\s*:?|Gender\s*:?|[A-Z]{3}\d{7}|Photo\s+is|\n|$)",
            segment,
            re.IGNORECASE,
        )
        if father_match:
            fname = father_match.group(1).strip()
            fname = re.sub(r'\s*Photo\s+is.*$', '', fname, flags=re.IGNORECASE).strip()
            # Clean garbled label fragments that leaked into father name
            fname = VotersPDFProcessor._clean_name(fname)
            fname = fname.rstrip(' .,;:-')
            if fname:
                voter.father_husband_name = fname
                voter.relation_type = VotersPDFProcessor._detect_relation_type(father_match.group(0))

        # Fallback: if no labeled father name, try second Tamil text line.
        # Skip lines that contain known field labels (house, age, gender, etc.)
        # to avoid picking up "வீட்டு எண் : 111" as father name.
        _NON_NAME_LABEL_RE = re.compile(
            r'வீட்டு\s*எண்|ட்டு\s*எண்|House\s*No|வயது\s*:|Age\s*:'
            r'|பாலினம்\s*:|Gender\s*:|Photo\s+is|[A-Z]{3}\d{7}',
            re.IGNORECASE,
        )
        if not voter.father_husband_name and voter.name:
            found_name = False
            for line in segment.split('\n'):
                line = line.strip()
                tamil_count = len(re.findall(r'[\u0B80-\u0BFF]', line))
                if tamil_count < 3:
                    continue
                if _EPIC_RE.search(line):
                    continue
                # Skip lines that are clearly field-label lines (house, age, gender)
                if _NON_NAME_LABEL_RE.search(line):
                    continue
                cleaned = VotersPDFProcessor._clean_name(line)
                cleaned = cleaned.rstrip(' .,;:-')
                if not cleaned or len(cleaned) < 2:
                    continue
                if not found_name:
                    # Skip the first Tamil line (already used as name)
                    if cleaned == voter.name or voter.name in cleaned or cleaned in voter.name:
                        found_name = True
                        continue
                    found_name = True
                    continue
                # This is the second Tamil text line — use as father name
                voter.father_husband_name = cleaned
                break

        # --- House Number ---
        # Handle both standard Tamil label and garbled OCR variants
        house_match = re.search(
            r'(?:வீட்டு\s*எண்|ட்டு\s*எண்|House\s*No|H\.?No)\s*:?\s*(.+?)(?=\s*(?:வயது|Age|பாலினம்|Gender|Photo\s+is)|\n|$)',
            segment,
            re.IGNORECASE,
        )
        if house_match:
            h = house_match.group(1).strip().rstrip(' .,;:')
            # Treat standalone dash as empty
            if h and h != '-':
                # Strip leading zeros only from purely numeric house numbers (07 → 7)
                # Keep alphanumeric intact: "01A" stays "01A", "0123" → "123"
                if re.fullmatch(r'0+\d+', h):
                    h = h.lstrip('0') or '0'
                voter.house_no = VotersPDFProcessor._clean_house_no(h)
        else:
            # Fallback: try to find house number without Tamil label
            # (OCR may garble the label entirely)
            # Look for patterns like "HNo: 1A" or standalone number-letter combos
            # near the end of a line, after age/gender context
            house_fb = re.search(
                r'(?:H\.?\s*No|HNo)\s*:?\s*(\S+)',
                segment, re.IGNORECASE,
            )
            if house_fb:
                h = house_fb.group(1).strip().rstrip(' .,;:')
                if h and h != '-':
                    voter.house_no = VotersPDFProcessor._clean_house_no(h)

        # --- Age ---
        age_match = re.search(
            r'(?:வயது|Age)\s*:?\s*(\d{1,3})',
            segment,
            re.IGNORECASE,
        )
        if age_match:
            age_val = int(age_match.group(1))
            if 18 <= age_val <= 100:
                voter.age = str(age_val)
        else:
            # Fallback: look for age near gender
            for m in _AGE_RE.finditer(segment):
                val = int(m.group(1))
                if 18 <= val <= 100:
                    voter.age = str(val)
                    break

        # --- Gender ---
        gender_match = re.search(
            r'(?:பாலினம்|Gender)\s*:?\s*(மூன்றாம்\s*பாலினம்|ஆண்|பெண்|Male|Female|Other|M|F|O)',
            segment,
            re.IGNORECASE,
        )
        if gender_match:
            g = gender_match.group(1).strip()
            if g in ('ஆண்', 'Male', 'M', 'm'):
                voter.gender = "Male"
            elif g in ('பெண்', 'Female', 'F', 'f'):
                voter.gender = "Female"
            elif g.replace(' ', '') in ('மூன்றாம்பாலினம்',) or g in ('Other', 'O', 'o'):
                voter.gender = "Other"
        else:
            if _GENDER_FEMALE.search(segment):
                voter.gender = "Female"
            elif _GENDER_MALE.search(segment):
                voter.gender = "Male"
            elif _GENDER_OTHER.search(segment):
                voter.gender = "Other"
            else:
                # Tertiary fallback: plain Tamil gender words without boundaries
                if re.search(r'பெண்', segment):
                    voter.gender = "Female"
                elif re.search(r'ஆண்', segment):
                    voter.gender = "Male"
                elif re.search(r'மூன்றாம்\s*பாலினம்', segment):
                    voter.gender = "Other"

        # --- Serial Number ---
        # Only match a leading number that is NOT already captured as house/age
        serial_match = re.match(r'^\s*(\d{1,4})\s', segment)
        if serial_match:
            sn = int(serial_match.group(1))
            sn_str = serial_match.group(1)
            # Don't use it if it equals the house number or age we already extracted
            if (1 <= sn <= 9999
                    and sn_str != voter.house_no
                    and sn_str != voter.age):
                voter.serial_no = sn_str

        return voter
