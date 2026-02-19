"""Shared in-memory task storage for all processing pipelines.

Extracted from main.py to avoid circular imports when routers need task access.
"""

from typing import Dict

from .models import ConversionTask

# In-memory task storage (use Redis for production)
tasks: Dict[str, ConversionTask] = {}

# Geocoding task storage
geocode_tasks: Dict[str, dict] = {}  # {geocode_task_id: {status, results, progress, ...}}

# Translation task storage
translation_tasks: Dict[str, dict] = {}  # {translate_task_id: {status, progress, ...}}

# Voter convert job storage (async convert-pdf with progress)
voter_convert_jobs: Dict[str, dict] = {}
# Each entry: {
#   "status": "processing" | "completed" | "failed",
#   "progress": {"current_page": int, "total_pages": int},
#   "download_url": str | None,
#   "output_file": str | None,
#   "filename": str,
#   "error": str | None,
# }

# Bulk voter processing job storage
bulk_voter_jobs: Dict[str, dict] = {}
# Each entry: {
#   "status": "uploading" | "processing" | "completed" | "failed",
#   "files": [],  # accumulated (index, path, original_name) tuples
#   "progress": {
#       "total_pdfs": int,
#       "completed_pdfs": int,
#       "current_file": str,
#       "total_voters_so_far": int,
#       "failed_count": int,
#   },
#   "output_file": str | None,
#   "download_url": str | None,
#   "error": str | None,
#   "summary": dict | None,
# }


def update_task_progress(task_id: str, progress: int, message: str, step: str = None):
    """Update task progress in storage."""
    if task_id in tasks:
        tasks[task_id].progress = progress
        tasks[task_id].message = message
