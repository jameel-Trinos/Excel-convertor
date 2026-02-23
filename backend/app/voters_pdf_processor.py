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

# EPIC (voter ID) pattern: 3 letters followed by 7 digits
_EPIC_RE = re.compile(r'\b([A-Z]{3}\d{7})\b')

# Fuzzy EPIC pattern: OCR often reads digits as letters in the digit portion.
# Common OCR confusions: 0↔O, 1↔I/l, 4↔A, 5↔S, 6↔G, 8↔B
# Matches 3 uppercase letters followed by 7 alphanumeric chars (mostly digits)
_EPIC_FUZZY_RE = re.compile(r'\b([A-Z]{3}[0-9A-Za-z]{7})\b')


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
_TOTAL_VOTERS_RE = re.compile(r'(?:Total\s*(?:Electors|Voters)|மொத்த\s*வாக்காளர்கள்)[:\s]*(\d+)', re.IGNORECASE)

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
    ):
        self.serial_no = serial_no
        self.name = name
        self.father_husband_name = father_husband_name
        self.house_no = house_no
        self.age = age
        self.gender = gender
        self.voter_id = voter_id

    def to_row(self) -> list[str]:
        return [
            self.serial_no,
            self.name,
            self.father_husband_name,
            self.house_no,
            self.age,
            self.gender,
            self.voter_id,
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
                    self.voters.extend(page_voters)
                    if progress_callback:
                        pct = 30 + int((i + 1) / max(total_pages, 1) * 50)
                        progress_callback(pct, f"Parsed page {i + 1}/{total_pages} ({len(self.voters)} voters found)")

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
        # Remove voters whose name became empty after cleaning
        self.voters = [v for v in self.voters if v.name and v.name.strip()]
        logger.info(f"[FILTER STATS] Before={pre_filter_count}, After={len(self.voters)}, Dropped={pre_filter_count - len(self.voters)}")

        # Re-number serial numbers sequentially
        for i, voter in enumerate(self.voters, 1):
            voter.serial_no = str(i)

        # Update total voters from actual count if header didn't have it
        if not self.header_info.total_voters and self.voters:
            self.header_info.total_voters = str(len(self.voters))

        if progress_callback:
            progress_callback(85, f"Extraction complete: {len(self.voters)} voters")

        headers = [
            "Serial No", "Name", "Father/Husband Name",
            "House No", "Age", "Gender", "Voter ID",
        ]

        return {
            "header_info": self.header_info,
            "voters": [v.to_row() for v in self.voters],
            "headers": headers,
            "total_pages": total_pages,
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
                            # First row: extend up to 40pt (EPIC strip above first row)
                            return min(40.0, card_top - 2)
                        prev_bottom = row_bottoms.get(row_tops_sorted[ri - 1], card_top)
                        gap = card_top - prev_bottom
                        # Extend by 90% of the gap between rows (captures EPIC strip)
                        return max(0.0, gap * 0.9)

                    # Extract text from each card
                    page_voters: list[VoterRecord] = []
                    skipped_cards: list[str] = []  # track skipped card texts for retry
                    for x0, top, x1, bottom in card_bboxes:
                        try:
                            # Extend crop UPWARD to capture EPIC voter ID printed
                            # above the card box, then inset sides by 2pt
                            extend_up = _header_extend(top)
                            crop_top = max(0, top - extend_up)
                            cropped = page.crop(
                                (x0 + 2, crop_top, x1 - 2, bottom - 2),
                                strict=False,
                            )
                            card_text = cropped.extract_text() or ""
                        except Exception:
                            continue

                        if len(card_text.strip()) < 5:
                            continue

                        # Card must contain voter-like field labels to be valid
                        has_name_field = bool(
                            re.search(r'பெயர்\s*:?|Name\s*:', card_text, re.IGNORECASE)
                        )
                        has_age_gender = bool(
                            re.search(r'வயது\s*:?|Age\s*:?|பாலினம்\s*:?|Gender\s*:?', card_text, re.IGNORECASE)
                        )
                        # Also check for EPIC ID as a strong voter card indicator
                        has_epic = bool(_EPIC_RE.search(card_text))

                        # Accept card if it has name+age/gender OR name+EPIC OR EPIC+age/gender
                        has_voter_fields = (has_name_field and has_age_gender) or \
                                           (has_name_field and has_epic) or \
                                           (has_epic and has_age_gender)

                        if not has_voter_fields:
                            # Still try to extract — some cards have data without standard labels
                            # Check for Tamil text content (real voter data has Tamil chars)
                            tamil_chars = len(re.findall(r'[\u0B80-\u0BFF]', card_text))
                            if has_epic or has_name_field or tamil_chars >= 5:
                                skipped_cards.append(card_text)
                                logger.info(f"[SPATIAL] Card without full labels on page {page_idx+1}, will retry: name={has_name_field} age/gender={has_age_gender} epic={has_epic} tamil={tamil_chars}")
                            continue

                        voter = self._extract_voter_from_segment(card_text)
                        if voter.is_valid:
                            page_voters.append(voter)
                        else:
                            logger.warning(f"[SPATIAL] Card extracted but invalid on page {page_idx+1}: text={card_text[:100]!r}")

                    # Retry skipped cards with relaxed extraction
                    for card_text in skipped_cards:
                        voter = self._extract_voter_from_segment(card_text)
                        if voter.is_valid:
                            logger.info(f"[SPATIAL RETRY] Recovered voter: {voter.name}")
                            page_voters.append(voter)

                    # --- EPIC recovery: assign EPICs to voters that don't have one ---
                    # The EPIC may be in the header strip above the card. If the
                    # extended crop didn't capture it, fall back to matching EPICs
                    # from full page text to card positions.
                    voters_missing_epic = [
                        (i, v) for i, v in enumerate(page_voters) if not v.voter_id
                    ]
                    if voters_missing_epic:
                        # Collect all EPICs from the full page text with their positions
                        all_page_epics: list[str] = _EPIC_RE.findall(page_text)
                        # Already-used EPICs
                        used_epics = set(v.voter_id for v in page_voters if v.voter_id)
                        available_epics = [e for e in all_page_epics if e not in used_epics]

                        if available_epics:
                            # Positional assignment: cards and EPICs are both in
                            # reading order (top-to-bottom, left-to-right), so
                            # assign available EPICs to missing-EPIC voters in order
                            epic_idx = 0
                            for vi, voter in voters_missing_epic:
                                if epic_idx < len(available_epics):
                                    candidate = available_epics[epic_idx]
                                    if candidate not in used_epics:
                                        voter.voter_id = candidate
                                        used_epics.add(candidate)
                                    epic_idx += 1
                            logger.info(
                                f"[SPATIAL EPIC-RECOVERY] Page {page_idx+1}: "
                                f"assigned {epic_idx} EPICs to voters missing IDs"
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

                    voters.extend(page_voters)

                    if progress_callback:
                        pct = 8 + int((page_idx + 1) / max(total_pages, 1) * 45)
                        progress_callback(
                            pct,
                            f"Parsed page {page_idx + 1}/{total_pages} ({len(voters)} voters found)",
                        )

                # Quality gate: compare voter count vs EPIC count in full text
                if voters:
                    total_epics = sum(
                        len(_EPIC_RE.findall(pt)) for pt in all_page_texts
                    )
                    if total_epics > 0 and len(voters) < total_epics * 0.4:
                        logger.warning(
                            f"Spatial extraction found {len(voters)} voters vs "
                            f"{total_epics} EPICs in text — falling back"
                        )
                        return [], 0, first_page_text

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
                    # Get plain text for header parsing (first page only)
                    if page_idx == 0:
                        first_page_text = page.extract_text() or ""

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
        These should be skipped, not parsed as voter records.
        """
        text_stripped = text.strip()
        if not text_stripped:
            return False

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
        text_lower = text_stripped.lower()
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

    def _ocr_single_page_cards(
        self,
        page_idx: int,
        gray: np.ndarray,
        do_header_ocr: bool,
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
        }

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
        if not card_bboxes:
            # Try full-page OCR fallback for pages without grid
            try:
                page_text = pytesseract.image_to_string(
                    gray, lang="tam+eng", config="--oem 3 --psm 3"
                )
                if page_text and _EPIC_RE.search(page_text):
                    fallback_voters = self._parse_voters_from_text(page_text)
                    result["voters"] = [v for v in fallback_voters if v.is_valid]
                    if result["voters"]:
                        logger.info(
                            f"[IMG-CARD-OCR] Page {page_idx+1}: no grid, "
                            f"recovered {len(result['voters'])} voters via full-page OCR"
                        )
            except Exception:
                pass
            return result

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

        # --- Per-card OCR + dedicated EPIC strip OCR ---
        page_voters: list[VoterRecord] = []
        card_to_voter: dict[int, int] = {}
        # Store expanded bboxes for whole-page EPIC fallback
        expanded_bboxes: list[tuple[int, int, int, int]] = []
        has_missing_epic = False
        skipped_header_cards = 0
        used_epics: set[str] = set()

        for ci, (x, y, w, h) in enumerate(card_bboxes):
            row_idx = row_tops.index(y) if y in row_tops else 0
            inset = 4

            # --- Step A: OCR card body (NO header extension) ---
            # Crop only the card interior to avoid header metadata pollution
            card_img = gray[y + inset:y + h - inset, x + inset:x + w - inset]
            if card_img.size == 0:
                # Store a dummy expanded bbox
                expanded_bboxes.append((x, y, w, h))
                continue

            card_enhanced = clahe.apply(card_img)

            try:
                card_text = pytesseract.image_to_string(
                    card_enhanced, lang="tam+eng",
                    config="--oem 3 --psm 6",
                )
            except Exception:
                expanded_bboxes.append((x, y, w, h))
                continue

            # Strip header metadata lines that may leak into first-row cards
            card_text = re.sub(
                r'^.*?(?:சட்டமன்ற|தொகுதி|பிரிவு எண்|பகுதி எண்|பாகம் எண்).*?\n',
                '', card_text, count=2,
            )

            # Store expanded bbox for whole-page EPIC fallback
            if row_idx == 0:
                expanded_bboxes.append((x, y, w, h))
            else:
                prev_bottom = row_prev_bottom.get(y)
                epic_y = prev_bottom if prev_bottom is not None else max(0, y - 50)
                expanded_bboxes.append((x, epic_y, w, h + (y - epic_y)))

            if self._is_header_card_text(card_text):
                skipped_header_cards += 1
                continue

            if len(card_text.strip()) < 3:
                continue

            voter = self._extract_voter_from_segment(card_text)

            # --- Step B: Dedicated EPIC strip OCR ---
            # The EPIC (voter ID) is in a strip near the card:
            #   Row 0: EPIC may be just ABOVE the card or at the top INSIDE
            #          the card (varies by page layout)
            #   Row 1+: EPIC is in the gap BETWEEN previous row bottom
            #           and current row top
            if not voter.voter_id:
                epic_strips: list[np.ndarray] = []
                if row_idx == 0:
                    # Try strip above card first (most pages)
                    above_strip = gray[max(0, y - 50):y, x:x + w]
                    if above_strip.size > 0:
                        epic_strips.append(above_strip)
                    # Also try top of card (some pages have EPIC inside)
                    inside_strip = gray[y:y + 35, x:x + w]
                    if inside_strip.size > 0:
                        epic_strips.append(inside_strip)
                else:
                    prev_bottom = row_prev_bottom.get(y)
                    if prev_bottom is not None:
                        epic_strips.append(gray[prev_bottom:y, x:x + w])
                    else:
                        epic_strips.append(gray[max(0, y - 50):y, x:x + w])

                for epic_strip in epic_strips:
                    if epic_strip.size == 0:
                        continue
                    try:
                        epic_text = pytesseract.image_to_string(
                            epic_strip, lang="eng",
                            config="--oem 3 --psm 3",
                        )
                        epic_m = _EPIC_RE.search(epic_text)
                        if epic_m and epic_m.group(1) not in used_epics:
                            voter.voter_id = epic_m.group(1)
                            break
                        elif not epic_m:
                            fuzzy_m = _EPIC_FUZZY_RE.search(epic_text)
                            if fuzzy_m:
                                normalized = _normalize_epic(
                                    fuzzy_m.group(1)
                                )
                                if normalized and normalized not in used_epics:
                                    voter.voter_id = normalized
                                    break
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

        # --- Whole-page EPIC pass: fallback for voters still missing IDs ---
        if has_missing_epic:
            try:
                epic_data = pytesseract.image_to_data(
                    gray, lang="eng",
                    config="--oem 3 --psm 3",
                    output_type=pytesseract.Output.DICT,
                )
                # Collect words with positions
                epic_words: list[dict] = []
                for i in range(len(epic_data["text"])):
                    text = epic_data["text"][i].strip()
                    conf = int(epic_data["conf"][i])
                    if text and conf > 0:
                        epic_words.append({
                            "text": text,
                            "left": epic_data["left"][i],
                            "top": epic_data["top"][i],
                            "width": epic_data["width"][i],
                            "height": epic_data["height"][i],
                        })

                # Build text per expanded card region
                margin = 15
                for ci_target, vi in card_to_voter.items():
                    if page_voters[vi].voter_id:
                        continue
                    ex, ey, ew, eh = expanded_bboxes[ci_target]
                    card_word_texts = []
                    for w in epic_words:
                        wcx = w["left"] + w["width"] // 2
                        wcy = w["top"] + w["height"] // 2
                        if (ex - margin <= wcx <= ex + ew + margin and
                                ey - margin <= wcy <= ey + eh + margin):
                            card_word_texts.append(w["text"])
                    combined = " ".join(card_word_texts)
                    epic_m = _EPIC_RE.search(combined)
                    if epic_m and epic_m.group(1) not in used_epics:
                        page_voters[vi].voter_id = epic_m.group(1)
                        used_epics.add(epic_m.group(1))
                    elif not epic_m or epic_m.group(1) in used_epics:
                        fuzzy_m = _EPIC_FUZZY_RE.search(combined)
                        if fuzzy_m:
                            normalized = _normalize_epic(fuzzy_m.group(1))
                            if normalized and normalized not in used_epics:
                                page_voters[vi].voter_id = normalized
                                used_epics.add(normalized)
            except Exception:
                pass

        # Quality check: if no voter has any evidence (EPIC, age, gender),
        # this page is likely a cover/summary page — discard all voters
        voters_with_evidence = sum(
            1 for v in page_voters
            if v.voter_id or v.age or v.gender
        )
        if page_voters and voters_with_evidence == 0:
            logger.info(
                f"[IMG-CARD-OCR] Page {page_idx+1}: discarding {len(page_voters)} "
                f"voters — no EPIC/age/gender evidence (likely cover page)"
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

        # Adaptive DPI: start at 200 for speed, fall back to 300 if quality is poor
        INITIAL_DPI = int(os.environ.get("VOTER_OCR_DPI", "200"))
        FALLBACK_DPI = 300
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

            # Convert to grayscale numpy arrays
            gray_batch: list[np.ndarray] = []
            for pil_img in batch_images:
                img = np.array(pil_img)
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
                    future = executor.submit(
                        self._ocr_single_page_cards, page_idx, gray, do_header
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
                            for pil_img in retry_images:
                                img = np.array(pil_img)
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
                                        }
                                    completed_count += 1
                            del retry_gray
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

            # Assign serial numbers and collect voters
            for voter in pr["voters"]:
                serial_counter = len(voters) + 1
                voter.serial_no = str(serial_counter)
                voters.append(voter)

        if voters:
            logger.info(
                f"[IMG-CARD-OCR] Total: {len(voters)} voters from "
                f"{total_pages} pages at {current_dpi} DPI"
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
        h_threshold = w_img * 0.1 * 255  # at least 10% of page width
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
        v_threshold = h_img * 0.05 * 255  # at least 5% of page height
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

        # Need at least 4 vertical lines (for 3 columns) and 2 horizontal lines
        if len(v_positions) < 4 or len(h_positions) < 2:
            return []

        # Build card rectangles from grid intersections
        cards: list[tuple[int, int, int, int]] = []
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

        # Sort: top-to-bottom, left-to-right
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

        # Try to extract address: look for lines after "Part No" and before voter data
        if self.header_info.address:
            return
        lines = page_text.split("\n")
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
            self.header_info.address = ", ".join(address_lines[-2:])  # Take last 2 lines as address

    # ------------------------------------------------------------------
    # Voter record parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _is_false_positive_voter(voter: "VoterRecord") -> bool:
        """Check if a voter record is actually metadata/header text misidentified.

        IMPORTANT: Never drop a record that has strong secondary evidence
        (father name, age, gender, voter_id, house_no). Real voters whose
        names got garbled by OCR or merged with header text must be kept.
        """
        name = voter.name.strip()
        if not name:
            return True

        # Count how many secondary fields this record has
        evidence_count = sum([
            bool(voter.father_husband_name and len(voter.father_husband_name.strip()) > 2),
            bool(voter.age),
            bool(voter.gender),
            bool(voter.voter_id),
            bool(voter.house_no and voter.house_no.strip()),
        ])

        # Strong evidence: 2+ secondary fields means this is almost certainly
        # a real voter, even if the name looks garbled or contains metadata text.
        # OCR often prepends/appends header text to the first voter's name.
        if evidence_count >= 2:
            return False

        # Header keywords that indicate this is metadata, not a voter
        metadata_kw = (
            'சாவடி', 'தொகுதி', 'பட்டியல்', 'வாக்காளர்',
            'ஊராட்சி', 'சட்டமன்ற', 'நாடாளுமன்ற', 'பிரிவு',
            'electoral', 'constituency', 'polling', 'station',
            'பாகம்', 'கையொப்பம்', 'google', 'map', 'nazri', 'naksha',
            'நூலக', 'கட்டிடம்',
            'ஆண்/பெண்', 'நகரம்', 'frade', 'bape',
            # Cover page / summary keywords
            'முக்கிய', 'கிராமம்', 'மற்றும்', 'வருவாய்', 'மாவட்ட',
            'சுருக்கம்', 'விவரம்',
            # Common OCR fragments from page headers/footers
            'மாற்றம்', 'என் மற்றும்', 'திருத்த', 'குறிப்பு',
            'முகவரி', 'சேர்த்தல்', 'நீக்கம்', 'அட்டவணை',
            'amendment', 'supplement', 'revision', 'deletion',
        )
        # Tamil Nadu city/district names that appear in page headers
        _city_district_kw = (
            'கடலூர்', 'சென்னை', 'கோயம்புத்தூர்', 'மதுரை', 'திருச்சி',
            'சேலம்', 'திருநெல்வேலி', 'ஈரோடு', 'தூத்துக்குடி',
            'விழுப்புரம்', 'வேலூர்', 'திருவண்ணாமலை', 'தஞ்சாவூர்',
            'நாகப்பட்டினம்', 'கன்னியாகுமரி', 'தருமபுரி', 'திண்டுக்கல்',
            'கரூர்', 'நாமக்கல்', 'பெரம்பலூர்', 'அரியலூர்',
            'கிருஷ்ணகிரி', 'சிவகங்கை', 'விருதுநகர்', 'ராமநாதபுரம்',
            'புதுக்கோட்டை', 'நீலகிரி', 'திருப்பூர்', 'திருவாரூர்',
            'காஞ்சிபுரம்', 'திருவள்ளூர்', 'ராணிப்பேட்டை', 'தென்காசி',
            'செங்கல்பட்டு', 'கள்ளக்குறிச்சி', 'மயிலாடுதுறை',
        )
        name_lower = name.lower()

        # With 1 evidence field, only drop on very strong metadata signals
        if evidence_count == 1:
            # Only drop if name is PURELY metadata (no Tamil name chars at all)
            tamil_chars = len(re.findall(r'[\u0B80-\u0BFF]', name))
            metadata_hit = any(kw in name_lower for kw in metadata_kw)
            city_hit = any(kw in name for kw in _city_district_kw)
            if metadata_hit or city_hit:
                # Check: does the name have real Tamil name content BEYOND the keyword?
                # Strip all metadata/city keywords and see what's left
                cleaned = name
                for kw in list(metadata_kw) + list(_city_district_kw):
                    cleaned = cleaned.replace(kw, '')
                cleaned = re.sub(r'[\d\s\-–.,;:()\[\]{}|/]', '', cleaned)
                tamil_remaining = len(re.findall(r'[\u0B80-\u0BFF]', cleaned))
                if tamil_remaining >= 3:
                    # Real Tamil name mixed with metadata — keep it
                    return False
                # Pure metadata with 1 evidence field — drop
                return True
            # Not metadata keyword match — keep
            return False

        # No evidence fields: apply full metadata checks
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
        if any(kw in name for kw in _city_district_kw):
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
        # Names containing special chars — only drop if no other voter fields
        if re.search(r'[{}\[\]|]', name):
            # Clean the special chars from name rather than dropping
            # (OCR often inserts stray | or } chars in real names)
            return False
        # Very short names with mostly non-Tamil chars are likely noise
        if tamil_chars < 2 and len(name) > 3:
            return True
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
        # Remove garbled father label fragments that leaked into the name
        # e.g. "ஊமத்துரை - தந்த leit பெயர்: ஊமத்துரை" → "ஊமத்துரை"
        name = re.sub(
            r'\s*-?\s*(?:தந்த\w*|கணவர்?|இதர\w*|தாயின்)\s*(?:leit|lelt|lett|peit|lest|leat)?\s*(?:பெயர்|பயர்)\s*:?\s*.*$',
            '', name
        )
        # Remove "கணவர் N பயர்:" type garbled patterns
        name = re.sub(r'கணவர்?\s*\d*\s*(?:பயர்|பெயர்)\s*:?\s*', '', name)
        # Remove trailing label-like text: "- தந்தையின் பெயர்:" and everything after
        name = re.sub(
            r'\s*-?\s*(?:தந்தையின்|கணவர்|இதரர்|தாயின்)\s*(?:பெயர்|பயர்)\s*:?\s*.*$',
            '', name
        )
        # Remove "பெயர் :" at end (leaked label)
        name = re.sub(r'\s*பெயர்\s*:?\s*$', '', name)
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
        # Reject house numbers with no digits (pure text like "SEAS", Tamil-only)
        if not re.search(r'\d', h):
            return ""
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

        Common OCR confusions: B→8, C→0, D→0, A→4, G→6
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
        _DIGIT_TO_LETTER = {'8': 'B', '0': 'C', '4': 'A', '6': 'G'}

        fixed_count = 0
        for v in voters:
            h = v.house_no
            if not h:
                continue
            # Match house numbers ending with a suspicious digit after separator
            # e.g., "1-218" → could be "1-21B", "1-80" → could be "1-8C"
            m = re.match(r'^(.+[-/]\d*)(\d)$', h)
            if m and m.group(2) in _DIGIT_TO_LETTER:
                # Also check: standalone like "128" where "12B" is expected
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

                voter = VoterRecord(
                    name=name,
                    father_husband_name=father,
                    house_no=VotersPDFProcessor._clean_house_no(house) if house else "",
                    age=age,
                    gender=gender,
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

                # Extract names: split by பெயர் :
                raw = re.split(r'\s*-?\s*பெயர்\s*:\s*', line)
                current_names = [
                    VotersPDFProcessor._clean_name(v)
                    for v in raw
                    if v.strip() and v.strip() not in ('-', ':')
                ]
                _init_slots()

            elif has_father:
                # Father/husband name line
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
                new_genders_raw = re.findall(r'பாலினம்\s*:\s*(ஆண்|பெண்)', line)
                new_genders = [
                    "Male" if g == 'ஆண்' else "Female" for g in new_genders_raw
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
                new_genders_raw = re.findall(r'பாலினம்\s*:\s*(ஆண்|பெண்)', line)
                new_genders = [
                    "Male" if g == 'ஆண்' else "Female" for g in new_genders_raw
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
                if part in ("Male", "Female", "M", "F", "ஆண்", "பெண்"):
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
            first_line = re.sub(r'\b(Male|Female|ஆண்|பெண்|M|F)\b', '', first_line, flags=re.IGNORECASE).strip()
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

    def _extract_voter_from_segment(self, segment: str) -> VoterRecord:
        """Extract a single voter's fields from a text segment.

        Handles both labeled (Name: X, Father: Y) and unlabeled text.
        """
        # Strip zero-width chars for reliable regex matching
        segment = _strip_zw(segment)
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
        # Try labeled name first, then fallback to line-based extraction
        name_match = re.search(
            r'(?:பெயர்|Name|Elector\s*Name)\s*:?\s*(.+?)(?=தந்தை|கணவர்|இதர|தாயின்|Father|Husband|'
            r'F/H|S/W/D|வீட்டு|House|வயது|Age|பாலினம்|Gender|[A-Z]{3}\d{7}|\n|$)',
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

        # --- Father/Husband Name ---
        # Broader pattern: handle OCR variations of தந்தை/கணவர்/தாயின்/இதரர்
        # OCR commonly garbles: தந்தையின் → தந்தை ின், பெயர் → ( பயர் / பயர்
        # Use .{0,6} to allow up to 6 noise chars between keyword and பெயர்/பயர்
        father_match = re.search(
            r"(?:தந்தை(?:யின்|.{0,6})?\s*(?:பெயர்|பயர்)|கணவர்?\s*.{0,4}(?:பெயர்|பயர்)|"
            r"தாயின்\s*.{0,4}(?:பெயர்|பயர்)|இதர(?:ர்)?\s*.{0,4}(?:பெயர்|பயர்)|"
            r"Father(?:'s)?\s*(?:Name)?|Husband(?:'s)?\s*(?:Name)?|Mother(?:'s)?\s*(?:Name)?|"
            r"F/H\s*Name|S/W/D\s*of|Relation\s*Name)\s*:?\s*"
            r"(.+?)(?=வீட்டு|ட்டு\s*எண்|House|வயது|Age|பாலினம்|Gender|[A-Z]{3}\d{7}|Photo\s+is|\n|$)",
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
            r'(?:பாலினம்|Gender)\s*:?\s*(ஆண்|பெண்|Male|Female|M|F)',
            segment,
            re.IGNORECASE,
        )
        if gender_match:
            g = gender_match.group(1).strip()
            if g in ('ஆண்', 'Male', 'M', 'm'):
                voter.gender = "Male"
            elif g in ('பெண்', 'Female', 'F', 'f'):
                voter.gender = "Female"
        else:
            if _GENDER_FEMALE.search(segment):
                voter.gender = "Female"
            elif _GENDER_MALE.search(segment):
                voter.gender = "Male"
            else:
                # Tertiary fallback: plain Tamil gender words without boundaries
                if re.search(r'பெண்', segment):
                    voter.gender = "Female"
                elif re.search(r'ஆண்', segment):
                    voter.gender = "Male"

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
