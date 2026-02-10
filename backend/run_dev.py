"""
Dev server runner.

Why this exists:
- When running `uvicorn ... --reload` on Python 3.12, it's common to see:
  `multiprocessing.resource_tracker: ... leaked semaphore objects ...`
  on shutdown. This is emitted by the reloader process and is usually harmless,
  but noisy.

Run this instead of the CLI to keep the same reload behavior while filtering
only that specific warning.
"""

from __future__ import annotations

import warnings


def main() -> None:
    # Silence only the known-noisy warning. Everything else still surfaces.
    warnings.filterwarnings(
        "ignore",
        message=r"resource_tracker: There appear to be \d+ leaked semaphore objects to clean up at shutdown",
        category=UserWarning,
        module=r"multiprocessing\.resource_tracker",
    )

    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()









