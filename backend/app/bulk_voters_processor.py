"""Bulk voter PDF processor using ProcessPoolExecutor for concurrent extraction.

Processes multiple voter list PDFs simultaneously (default 8 workers) and
consolidates all extracted voter data into a single dataset.
"""

import logging
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


def _extract_single_pdf(file_path: str, pdf_index: int) -> dict[str, Any]:
    """Extract voters from a single PDF. Runs in a child process.

    Must be a top-level function for picklability with ProcessPoolExecutor.
    """
    from .voters_pdf_processor import VotersPDFProcessor

    try:
        processor = VotersPDFProcessor(file_path)
        result = processor.extract(progress_callback=None)

        header_info = result["header_info"]
        return {
            "pdf_index": pdf_index,
            "filename": Path(file_path).name,
            "header_info": {
                "ac_no": header_info.ac_no,
                "part_no": header_info.part_no,
                "address": header_info.address,
                "total_voters": header_info.total_voters,
            },
            "voters": result["voters"],
            "headers": result["headers"],
            "total_pages": result["total_pages"],
            "error": None,
        }
    except Exception as e:
        return {
            "pdf_index": pdf_index,
            "filename": Path(file_path).name,
            "header_info": {},
            "voters": [],
            "headers": [],
            "total_pages": 0,
            "error": str(e),
        }


class BulkVotersProcessor:
    """Process multiple voter PDFs concurrently and consolidate results."""

    def __init__(self, max_workers: int = 8):
        self.max_workers = min(max_workers, os.cpu_count() or 4)

    def process_all(
        self,
        pdf_paths: list[tuple[int, str, str]],
        progress_callback: Optional[Callable[[dict], None]] = None,
    ) -> dict[str, Any]:
        """Process all PDFs concurrently.

        Args:
            pdf_paths: List of (index, file_path, original_filename) tuples.
            progress_callback: Called after each PDF completes with
                {completed, total, current_file, had_error, voter_count}.

        Returns:
            Consolidated result dict with all_voters, booth_groups, etc.
        """
        total = len(pdf_paths)
        results: list[dict] = []

        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_info = {}
            for idx, file_path, orig_name in pdf_paths:
                future = executor.submit(_extract_single_pdf, file_path, idx)
                future_to_info[future] = (idx, orig_name)

            completed = 0
            for future in as_completed(future_to_info):
                idx, orig_name = future_to_info[future]
                try:
                    result = future.result(timeout=300)
                except Exception as e:
                    result = {
                        "pdf_index": idx,
                        "filename": orig_name,
                        "header_info": {},
                        "voters": [],
                        "headers": [],
                        "total_pages": 0,
                        "error": str(e),
                    }

                results.append(result)
                completed += 1

                if progress_callback:
                    progress_callback({
                        "completed": completed,
                        "total": total,
                        "current_file": orig_name,
                        "had_error": result["error"] is not None,
                        "voter_count": len(result["voters"]),
                    })

        return self._consolidate(results)

    def _consolidate(self, results: list[dict]) -> dict[str, Any]:
        """Merge all extraction results into one consolidated dataset."""
        successful = [r for r in results if r["error"] is None and r["voters"]]
        failed = [
            {"filename": r["filename"], "error": r["error"]}
            for r in results
            if r["error"] is not None
        ]
        empty = [
            {"filename": r["filename"], "error": "No voters extracted"}
            for r in results
            if r["error"] is None and not r["voters"]
        ]

        # Sort by part_no (booth number) numerically
        def sort_key(r):
            part = r["header_info"].get("part_no", "0") or "0"
            try:
                return int(part)
            except ValueError:
                return 999999

        successful.sort(key=sort_key)

        all_voters: list[list] = []
        booth_groups: list[dict] = []
        serial_counter = 1
        ac_no = ""

        for result in successful:
            hi = result["header_info"]
            if not ac_no:
                ac_no = hi.get("ac_no", "")

            booth_start_row = len(all_voters)

            for voter_row in result["voters"]:
                row_copy = list(voter_row)
                # Re-number serial to be globally sequential
                row_copy[0] = str(serial_counter)
                # Append booth/part number as extra column
                row_copy.append(hi.get("part_no", ""))
                all_voters.append(row_copy)
                serial_counter += 1

            booth_groups.append({
                "part_no": hi.get("part_no", ""),
                "address": hi.get("address", ""),
                "voter_count": len(result["voters"]),
                "filename": result["filename"],
                "start_row": booth_start_row,
                "end_row": len(all_voters) - 1,
            })

        # Build per-booth data for separate Excel sheets
        booth_data: list[dict] = []
        for result in successful:
            hi = result["header_info"]
            booth_data.append({
                "part_no": hi.get("part_no", ""),
                "ac_no": hi.get("ac_no", ""),
                "address": hi.get("address", ""),
                "total_voters": str(len(result["voters"])),
                "voters": result["voters"],
                "headers": result["headers"],
                "filename": result["filename"],
            })

        return {
            "all_voters": all_voters,
            "booth_groups": booth_groups,
            "booth_data": booth_data,
            "total_voters": len(all_voters),
            "total_pdfs": len(results),
            "successful_pdfs": len(successful),
            "failed_pdfs": failed + empty,
            "ac_no": ac_no,
        }
