"""
Optional AI-assisted table structure inference for complex OCR extraction.

When grid and bbox parsing produce low-confidence or obviously wrong structure
(e.g. very few columns), Claude can suggest header row and column count to
improve or validate extraction. Requires ANTHROPIC_API_KEY.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def infer_table_structure(
    raw_text: str,
    current_headers: List[str],
    current_rows_sample: List[List[str]],
    page_number: int = 1,
) -> Optional[Dict[str, Any]]:
    """
    Use Claude to suggest table structure from OCR output (election Form 20 style).

    Called when bbox fallback produces suspiciously few columns or low confidence.
    Returns suggested num_columns and header_row_index, or None if unavailable.

    Args:
        raw_text: First page OCR raw text
        current_headers: Currently extracted headers
        current_rows_sample: First few parsed rows (e.g. up to 5)
        page_number: Page number for logging

    Returns:
        Dict with num_columns, header_row_index (0-based), and optional message,
        or None if API not configured or call fails
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.debug("ANTHROPIC_API_KEY not set, skipping OCR structure inference")
        return None

    try:
        from anthropic import Anthropic
    except ImportError:
        logger.debug("anthropic not installed, skipping OCR structure inference")
        return None

    client = Anthropic(api_key=api_key)
    model = "claude-sonnet-4-20250514"

    sample = "\n".join(
        " | ".join(str(c) for c in row) for row in ([current_headers] + current_rows_sample[:5])
    )
    text_preview = (raw_text or "")[:2000]

    prompt = f"""You are analyzing OCR output from an Indian election result PDF (Form 20 style).
The table has candidate/party columns and vote counts. Current extraction may have wrong structure.

Current headers ({len(current_headers)} columns): {current_headers[:15]}
Sample rows (header + first rows):
{sample}

Raw OCR text (first 2000 chars):
{text_preview}

Respond with a JSON object only, no markdown:
- "num_columns": integer (expected number of data columns, typically 10–30 for Form 20)
- "header_row_index": 0 if the first row above is the header row, else 1 if there are title rows above
- "confidence": 0.0 to 1.0
- "message": optional short note

If the current extraction looks reasonable (e.g. 8+ columns and header-like first row), set confidence high.
If columns seem merged or missing, suggest higher num_columns and set confidence low.
"""

    try:
        response = client.messages.create(
            model=model,
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text if response.content else ""
        # Strip possible markdown code block
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()
        data = json.loads(text)
        num_cols = data.get("num_columns")
        header_idx = data.get("header_row_index", 0)
        if num_cols is not None and isinstance(num_cols, int):
            logger.info(
                "OCR structure AI (page %s): suggested num_columns=%s, header_row_index=%s",
                page_number, num_cols, header_idx,
            )
            return {
                "num_columns": num_cols,
                "header_row_index": header_idx,
                "confidence": float(data.get("confidence", 0.5)),
                "message": data.get("message"),
            }
    except json.JSONDecodeError as e:
        logger.warning("OCR structure AI: invalid JSON response: %s", e)
    except Exception as e:
        logger.warning("OCR structure AI failed: %s", e)

    return None
