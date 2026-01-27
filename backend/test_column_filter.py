"""Test script for column filtering service."""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.column_filter import ColumnFilterService


async def test_column_filter():
    """Test the column filter service with a sample Excel file."""

    # You'll need to provide an actual Excel file path for testing
    # This is just a demonstration

    filter_service = ColumnFilterService()

    # Example usage:
    # input_file = "/path/to/your/excel/file.xlsx"
    # requested_columns = ["Column1", "Column2", "Column3"]
    # output_dir = "./outputs"

    # filtered_file, metadata = filter_service.filter_columns(
    #     input_file=input_file,
    #     requested_columns=requested_columns,
    #     output_dir=output_dir,
    # )

    # print(f"Filtered file created: {filtered_file}")
    # print(f"Metadata: {metadata}")

    print("Column filter service initialized successfully!")
    print("\nTo test, create a sample Excel file and update this script with:")
    print("  - input_file: path to your Excel file")
    print("  - requested_columns: list of column names to keep")
    print("  - output_dir: directory for the filtered file")


if __name__ == "__main__":
    asyncio.run(test_column_filter())
