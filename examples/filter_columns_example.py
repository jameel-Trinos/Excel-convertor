"""
Example script demonstrating how to use the column filtering API.

This script shows how to:
1. Get the column names from a converted Excel file
2. Filter to specific columns
3. Download the filtered file
"""

import requests
import json

# API base URL
API_BASE = "http://localhost:8000"


def get_preview_columns(task_id: str) -> list[str]:
    """
    Get the column names from a converted Excel file.

    Args:
        task_id: The task ID from the PDF conversion

    Returns:
        List of column names
    """
    response = requests.get(f"{API_BASE}/api/preview/{task_id}")
    response.raise_for_status()

    data = response.json()
    return data["headers"]


def filter_columns(task_id: str, columns: list[str]) -> dict:
    """
    Filter Excel file to include only specified columns.

    Args:
        task_id: The task ID from the PDF conversion
        columns: List of column names to keep (in desired order)

    Returns:
        Response dictionary with filtered file metadata
    """
    response = requests.post(
        f"{API_BASE}/api/filter-columns",
        json={
            "task_id": task_id,
            "columns": columns
        }
    )
    response.raise_for_status()

    return response.json()


def download_filtered_file(timestamp: str, output_path: str):
    """
    Download the filtered Excel file.

    Args:
        timestamp: Timestamp from the filter response
        output_path: Local path to save the file
    """
    response = requests.get(f"{API_BASE}/api/download-filtered/{timestamp}")
    response.raise_for_status()

    with open(output_path, "wb") as f:
        f.write(response.content)

    print(f"Downloaded filtered file to: {output_path}")


def main():
    """Example usage of the column filtering API."""

    # Example task ID (replace with actual task ID from your conversion)
    TASK_ID = "your-task-id-here"

    print("=== Column Filtering Example ===\n")

    # Step 1: Get available columns
    print("Step 1: Getting available columns...")
    try:
        columns = get_preview_columns(TASK_ID)
        print(f"Available columns ({len(columns)}):")
        for i, col in enumerate(columns, 1):
            print(f"  {i}. {col}")
        print()
    except Exception as e:
        print(f"Error getting columns: {e}")
        print("Make sure to replace TASK_ID with a valid task ID from a completed conversion.")
        return

    # Step 2: Select columns to keep
    print("Step 2: Filtering to specific columns...")

    # Example: Keep only the first 3 columns
    # In a real application, you would let the user select these
    selected_columns = columns[:3]

    print(f"Selected columns: {selected_columns}\n")

    try:
        result = filter_columns(TASK_ID, selected_columns)

        print("Filtering results:")
        print(f"  Filtered file: {result['filtered_file_path']}")
        print(f"  Total columns: {result['total_columns']}")
        print(f"  Total rows: {result['total_rows']}")
        print(f"  Columns removed: {result['columns_removed']}")
        print(f"  Timestamp: {result['timestamp']}")
        print()

        # Step 3: Download the filtered file
        print("Step 3: Downloading filtered file...")
        download_filtered_file(
            result['timestamp'],
            f"filtered_output_{result['timestamp']}.xlsx"
        )

        print("\nSuccess! The filtered Excel file has been created and downloaded.")

    except requests.exceptions.HTTPError as e:
        print(f"API Error: {e}")
        print(f"Response: {e.response.text}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    # Interactive example
    print("Column Filtering API Example")
    print("=" * 50)
    print()

    task_id = input("Enter your task ID (or press Enter to see example): ").strip()

    if not task_id:
        print("\n=== Example Usage ===\n")
        print("1. First, convert a PDF to Excel:")
        print("   POST /api/upload")
        print("   -> Returns task_id\n")

        print("2. Wait for conversion to complete, then get columns:")
        print("   GET /api/preview/{task_id}")
        print("   -> Returns column names\n")

        print("3. Filter to specific columns:")
        print("   POST /api/filter-columns")
        print('   Body: {"task_id": "...", "columns": ["Col1", "Col2"]}\n')

        print("4. Download the filtered file:")
        print("   GET /api/download-filtered/{timestamp}\n")

        print("Run this script with a valid task_id to see it in action!")
    else:
        # Use the provided task_id
        TASK_ID = task_id
        main()
