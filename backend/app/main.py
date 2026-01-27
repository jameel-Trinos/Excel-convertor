"""Simplified FastAPI application for PDF to Excel Converter."""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict

import aiofiles
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sse_starlette.sse import EventSourceResponse

from .column_filter import ColumnFilterService
from .excel_creator import ExcelCreator
from .models import (
    ConversionTask,
    DownloadModifiedRequest,
    ErrorResponse,
    FilterColumnsRequest,
    FilterColumnsResponse,
    FilterExcelRequest,
    FullPreviewData,
    PreviewData,
    ProgressEvent,
    StatusResponse,
    UploadResponse,
)
from .pdf_processor import PDFProcessor
from .utils import cleanup_file, validate_pdf_file

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./uploads"))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "./outputs"))
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 10 * 1024 * 1024))  # 10MB default
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:3001").split(",")

# Ensure directories exist
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# In-memory task storage (use Redis for production)
tasks: Dict[str, ConversionTask] = {}

# Create FastAPI app
app = FastAPI(
    title="PDF to Excel Converter API",
    description="Convert tabular PDFs to professionally formatted Excel spreadsheets",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def update_task_progress(task_id: str, progress: int, message: str, step: str = None):
    """Update task progress in storage."""
    if task_id in tasks:
        tasks[task_id].progress = progress
        tasks[task_id].message = message


async def process_conversion(task_id: str, file_path: Path):
    """Simplified background task for PDF to Excel conversion."""
    try:
        tasks[task_id].status = "processing"
        tasks[task_id].message = "Starting conversion..."

        update_task_progress(task_id, 10, "Extracting tables from PDF...")
        logger.info(f"Processing task {task_id}")

        processor = PDFProcessor(str(file_path))

        def progress_callback(progress: int, message: str):
            # Scale extraction progress to 10-80%
            scaled_progress = 10 + int(progress * 0.7)
            update_task_progress(task_id, scaled_progress, message)

        extraction_result = await processor.extract_tables(progress_callback=progress_callback)

        if not extraction_result.tables or all(t.is_empty for t in extraction_result.tables):
            raise ValueError("No tables found in the PDF")

        update_task_progress(task_id, 85, "Creating Excel file...")

        # Create Excel file
        creator = ExcelCreator()
        output_filename = f"{task_id}.xlsx"
        output_path = OUTPUT_DIR / output_filename

        await asyncio.to_thread(
            creator.create_from_tables,
            extraction_result.tables,
            str(output_path),
            source_filename=tasks[task_id].filename,
        )

        update_task_progress(task_id, 95, "Finalizing...")

        # Mark as complete
        tasks[task_id].status = "completed"
        tasks[task_id].progress = 100
        tasks[task_id].message = "Conversion completed successfully"
        tasks[task_id].output_file = str(output_path)

        logger.info(f"Conversion completed for task {task_id}: {output_path}")

    except Exception as e:
        logger.error(f"Conversion failed for task {task_id}: {e}", exc_info=True)
        tasks[task_id].status = "failed"
        tasks[task_id].error = str(e)
        tasks[task_id].message = f"Conversion failed: {str(e)}"

    finally:
        # Cleanup uploaded PDF
        await cleanup_file(file_path)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}




@app.post("/api/upload", response_model=UploadResponse)
async def upload_pdf(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
):
    """
    Upload a PDF file for conversion to Excel.

    - **file**: PDF file to convert (max 10MB)

    Returns task ID for tracking conversion progress.
    """
    # Validate file
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are accepted",
        )

    # Read file content
    content = await file.read()

    # Check file size
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE // 1024 // 1024}MB",
        )

    # Validate PDF content
    validation_error = validate_pdf_file(content)
    if validation_error:
        raise HTTPException(status_code=400, detail=validation_error)

    # Generate task ID
    task_id = str(uuid.uuid4())

    # Save file
    file_path = UPLOAD_DIR / f"{task_id}.pdf"
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    # Create task
    tasks[task_id] = ConversionTask(
        task_id=task_id,
        filename=file.filename,
        status="pending",
        progress=0,
        message="File uploaded, starting conversion...",
    )

    # Start background conversion
    background_tasks.add_task(process_conversion, task_id, file_path)

    return UploadResponse(
        task_id=task_id,
        filename=file.filename,
        size=len(content),
        message="File uploaded successfully. Conversion started.",
    )


@app.get("/api/status/{task_id}", response_model=StatusResponse)
async def get_status(task_id: str):
    """Get the status of a conversion task."""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = tasks[task_id]
    return StatusResponse(
        task_id=task.task_id,
        status=task.status,
        progress=task.progress,
        message=task.message,
        output_file=task.output_file,
        error=task.error,
    )


@app.get("/api/progress/{task_id}")
async def progress_stream(task_id: str):
    """
    Server-Sent Events endpoint for real-time progress updates.

    Connect to this endpoint to receive live progress updates during conversion.
    """
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    async def event_generator():
        last_progress = -1
        while True:
            if task_id in tasks:
                task = tasks[task_id]

                # Only send update if progress changed
                if task.progress != last_progress:
                    last_progress = task.progress
                    event = ProgressEvent(
                        progress=task.progress,
                        status=task.status,
                        message=task.message,
                    )
                    yield {
                        "event": "progress",
                        "data": json.dumps(event.model_dump()),
                    }

                # Stop streaming when complete or failed
                if task.status in ["completed", "failed"]:
                    break

            await asyncio.sleep(0.3)

    return EventSourceResponse(event_generator())


@app.get("/api/preview/{task_id}", response_model=PreviewData)
async def get_preview(task_id: str):
    """
    Get a preview of the extracted data.

    Returns the first 10 rows of data for preview before download.
    """
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = tasks[task_id]

    if task.status != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Task not completed. Current status: {task.status}",
        )

    if not task.output_file or not Path(task.output_file).exists():
        raise HTTPException(status_code=404, detail="Output file not found")

    # Read Excel file for preview
    try:
        import openpyxl

        wb = openpyxl.load_workbook(task.output_file, data_only=True)
        ws = wb.active

        # Find actual data range by scanning for cells with values
        # This is more reliable than max_row/max_column which can be inaccurate
        # Start with max_row/max_column as baseline, then expand if needed
        actual_max_row = ws.max_row if ws.max_row else 0
        actual_max_col = ws.max_column if ws.max_column else 0
        
        # Scan iteratively to find actual data boundaries
        # Check rows beyond max_row (sometimes max_row is inaccurate)
        last_data_row = actual_max_row
        scan_limit = max(actual_max_row + 100, 1000)  # Scan up to 1000 rows or max_row + 100
        for row in range(1, min(scan_limit + 1, 2000)):
            row_has_data = False
            for col in range(1, min(actual_max_col + 100, 200)):
                cell = ws.cell(row, col)
                if cell.value is not None and str(cell.value).strip():
                    actual_max_row = max(actual_max_row, row)
                    actual_max_col = max(actual_max_col, col)
                    row_has_data = True
                    last_data_row = row
            # If we've gone 50 rows without finding new data, stop scanning
            if row > last_data_row + 50:
                break

        # Ensure we have reasonable values
        if actual_max_row == 0:
            actual_max_row = ws.max_row if ws.max_row else 100
        if actual_max_col == 0:
            actual_max_col = ws.max_column if ws.max_column else 50

        # Find data start row (skip title rows)
        data_start_row = 1
        for row in range(1, min(20, actual_max_row + 1)):
            cell_value = ws.cell(row, 1).value
            if cell_value and str(cell_value).strip():
                # Check if this row looks like headers (has multiple non-empty cells)
                non_empty_count = sum(
                    1 for col in range(1, min(actual_max_col + 1, 20))
                    if ws.cell(row, col).value and str(ws.cell(row, col).value).strip()
                )
                if non_empty_count >= 2:  # At least 2 columns with data
                    data_start_row = row
                    break

        # Get headers by merging multi-row headers
        # Many election PDFs have 2-3 header rows (main header + candidate name + party)
        headers = []
        for col in range(1, actual_max_col + 1):
            # Get values from up to 3 header rows
            header_parts = []
            
            # Check up to 3 rows for header information
            for header_row in range(data_start_row, min(data_start_row + 3, actual_max_row + 1)):
                value = ws.cell(header_row, col).value
                if value is not None and str(value).strip():
                    clean_value = str(value).strip()
                    # Skip generic phrases and party abbreviation labels
                    if clean_value.upper() not in ['PARTY ABBREVIATION', 'NO. OF VALID VOTES CAST IN FAVOUR OF']:
                        header_parts.append(clean_value)
            
            # Combine header parts into a single name
            if header_parts:
                # Use the last non-empty part (usually the party name or most specific info)
                # Or combine if there are multiple meaningful parts
                if len(header_parts) == 1:
                    headers.append(header_parts[0])
                else:
                    # For multi-part headers, prioritize party names (usually in last row)
                    # and candidate names
                    combined = " - ".join(header_parts[-2:]) if len(header_parts) >= 2 else header_parts[-1]
                    headers.append(combined)
            else:
                # Fallback for empty columns
                headers.append(f"Column {col}")

        # Ensure we have at least some headers
        if not headers:
            # Fallback: try to detect columns by scanning first few data rows
            for col in range(1, min(actual_max_col + 1, 50)):
                headers.append(f"Column {col}")

        # Get first 10 data rows - read all columns up to actual_max_col
        # Skip up to 3 header rows (data_start_row, data_start_row+1, data_start_row+2)
        # Find where actual data starts (first row with numeric data in first column)
        first_data_row = data_start_row + 1
        for row in range(data_start_row + 1, min(data_start_row + 10, actual_max_row + 1)):
            cell_val = ws.cell(row, 1).value
            # Check if this looks like data (numeric or starts with a number)
            if cell_val is not None:
                if isinstance(cell_val, (int, float)) or (isinstance(cell_val, str) and cell_val.strip().isdigit()):
                    first_data_row = row
                    break
        
        rows = []
        preview_row_count = min(10, actual_max_row - first_data_row + 1)
        for row_idx in range(first_data_row, first_data_row + preview_row_count):
            if row_idx > actual_max_row:
                break
            row_data = []
            # Read all columns up to the number of headers we found
            num_cols_to_read = max(len(headers), actual_max_col)
            for col in range(1, num_cols_to_read + 1):
                value = ws.cell(row_idx, col).value
                row_data.append(value)
            # Ensure row_data matches header count
            while len(row_data) < len(headers):
                row_data.append(None)
            # Trim if too long (shouldn't happen, but safety check)
            if len(row_data) > len(headers):
                row_data = row_data[:len(headers)]
            rows.append(row_data)

        # Calculate actual total rows (excluding all header rows)
        total_rows = max(0, actual_max_row - first_data_row + 1)

        return PreviewData(
            headers=headers,
            rows=rows,
            total_rows=total_rows,
            total_columns=len(headers),
            pages_processed=1,  # Simplified for now
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read preview: {str(e)}",
        )


@app.get("/api/columns/{task_id}")
async def get_columns(task_id: str):
    """
    Get column names directly from the converted Excel file.
    
    Returns the exact column names as they appear in the Excel file,
    without any processing or merging.
    """
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = tasks[task_id]

    if task.status != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Task not completed. Current status: {task.status}",
        )

    if not task.output_file or not Path(task.output_file).exists():
        raise HTTPException(status_code=404, detail="Output file not found")

    # Read Excel file to get column names
    try:
        import openpyxl

        wb = openpyxl.load_workbook(task.output_file, data_only=True)
        ws = wb.active

        # Find actual data range by scanning for cells with values
        actual_max_row = ws.max_row if ws.max_row else 0
        actual_max_col = ws.max_column if ws.max_column else 0
        
        # Scan iteratively to find actual data boundaries
        last_data_row = actual_max_row
        scan_limit = max(actual_max_row + 100, 1000)
        for row in range(1, min(scan_limit + 1, 2000)):
            row_has_data = False
            for col in range(1, min(actual_max_col + 100, 200)):
                cell = ws.cell(row, col)
                if cell.value is not None and str(cell.value).strip():
                    actual_max_row = max(actual_max_row, row)
                    actual_max_col = max(actual_max_col, col)
                    row_has_data = True
                    last_data_row = row
            if row > last_data_row + 50:
                break

        # Ensure we have reasonable values
        if actual_max_row == 0:
            actual_max_row = ws.max_row if ws.max_row else 100
        if actual_max_col == 0:
            actual_max_col = ws.max_column if ws.max_column else 50

        # Find data start row (skip title rows)
        data_start_row = 1
        for row in range(1, min(20, actual_max_row + 1)):
            cell_value = ws.cell(row, 1).value
            if cell_value and str(cell_value).strip():
                # Check if this row looks like headers (has multiple non-empty cells)
                non_empty_count = sum(
                    1 for col in range(1, min(actual_max_col + 1, 20))
                    if ws.cell(row, col).value and str(ws.cell(row, col).value).strip()
                )
                if non_empty_count >= 2:  # At least 2 columns with data
                    data_start_row = row
                    break

        # Get headers by reading from the header row(s)
        # Many Excel files have headers in a single row, but some have multi-row headers
        columns = []
        for col in range(1, actual_max_col + 1):
            # Get values from up to 3 header rows (data_start_row, data_start_row+1, data_start_row+2)
            header_parts = []
            
            for header_row in range(data_start_row, min(data_start_row + 3, actual_max_row + 1)):
                value = ws.cell(header_row, col).value
                if value is not None and str(value).strip():
                    clean_value = str(value).strip()
                    # Skip generic phrases
                    if clean_value.upper() not in ['PARTY ABBREVIATION', 'NO. OF VALID VOTES CAST IN FAVOUR OF']:
                        header_parts.append(clean_value)
            
            # Combine header parts into a single name
            if header_parts:
                # Use the last non-empty part (usually the party name or most specific info)
                # Or combine if there are multiple meaningful parts
                if len(header_parts) == 1:
                    columns.append(header_parts[0])
                else:
                    # For multi-part headers, combine them with " - "
                    combined = " - ".join(header_parts[-2:]) if len(header_parts) >= 2 else header_parts[-1]
                    columns.append(combined)
            else:
                # Fallback for empty columns
                columns.append(f"Column {col}")

        # Ensure we have at least some headers
        if not columns:
            # Fallback: try to detect columns by scanning first few data rows
            for col in range(1, min(actual_max_col + 1, 50)):
                columns.append(f"Column {col}")

        wb.close()

        return {"columns": columns}

    except Exception as e:
        logger.error(f"Failed to read columns from Excel: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read columns from Excel file: {str(e)}",
        )


@app.get("/api/download/{task_id}")
async def download_excel(task_id: str):
    """
    Download the generated Excel file.

    Returns the Excel file as a downloadable attachment.
    """
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = tasks[task_id]

    if task.status != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Task not completed. Current status: {task.status}",
        )

    if not task.output_file or not Path(task.output_file).exists():
        raise HTTPException(status_code=404, detail="Output file not found")

    # Generate download filename
    original_name = Path(task.filename).stem
    download_name = f"{original_name}.xlsx"

    return FileResponse(
        task.output_file,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=download_name,
    )


@app.delete("/api/task/{task_id}")
async def delete_task(task_id: str):
    """Delete a task and its associated files."""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = tasks[task_id]

    # Cleanup files
    if task.output_file and Path(task.output_file).exists():
        await cleanup_file(Path(task.output_file))

    upload_path = UPLOAD_DIR / f"{task_id}.pdf"
    if upload_path.exists():
        await cleanup_file(upload_path)

    # Remove from storage
    del tasks[task_id]

    return {"message": "Task deleted successfully"}


@app.post("/api/filter-columns", response_model=FilterColumnsResponse)
async def filter_columns(request: FilterColumnsRequest):
    """
    Filter Excel file to include only selected columns.

    Takes a task_id and list of column names, creates a new Excel file
    with only the requested columns in the specified order.

    Args:
        request: FilterColumnsRequest with task_id and columns list

    Returns:
        FilterColumnsResponse with filtered file path and metadata
    """
    # Validate task exists and is completed
    if request.task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = tasks[request.task_id]

    if task.status != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Task not completed. Current status: {task.status}",
        )

    if not task.output_file or not Path(task.output_file).exists():
        raise HTTPException(status_code=404, detail="Output file not found")

    # Validate columns list
    if not request.columns or len(request.columns) == 0:
        raise HTTPException(
            status_code=400,
            detail="No columns specified. Please provide at least one column name.",
        )

    try:
        logger.info(f"Filtering columns for task {request.task_id}: {request.columns}")

        # Create filter service
        filter_service = ColumnFilterService()

        # Filter columns
        filtered_file, metadata = await asyncio.to_thread(
            filter_service.filter_columns,
            task.output_file,
            request.columns,
            str(OUTPUT_DIR),
        )

        logger.info(f"Column filtering completed: {filtered_file}")

        # Return response
        return FilterColumnsResponse(
            filtered_file_path=filtered_file,
            original_file=metadata["original_file"],
            selected_columns=metadata["selected_columns"],
            total_columns=metadata["total_columns"],
            total_rows=metadata["total_rows"],
            columns_removed=metadata["columns_removed"],
            timestamp=metadata["timestamp"],
        )

    except ValueError as e:
        # Column validation errors
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Column filtering failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Column filtering failed: {str(e)}",
        )


@app.post("/api/filter-excel")
async def filter_excel(request: FilterExcelRequest):
    """
    Filter Excel file to include only selected columns and optionally add OTHERS column.

    Takes a task_id, list of column names, and include_others flag.
    Creates a new Excel file with selected columns and optionally adds an
    "OTHER Votes" column that sums all unselected party columns.

    Args:
        request: FilterExcelRequest with task_id, selected_columns, and include_others

    Returns:
        FileResponse with the filtered Excel file for direct download
    """
    # Validate task exists and is completed
    if request.task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = tasks[request.task_id]

    if task.status != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Task not completed. Current status: {task.status}",
        )

    if not task.output_file or not Path(task.output_file).exists():
        raise HTTPException(status_code=404, detail="Output file not found")

    # Validate columns list
    if not request.selected_columns or len(request.selected_columns) == 0:
        raise HTTPException(
            status_code=400,
            detail="No columns specified. Please provide at least one column name.",
        )

    try:
        logger.info(
            f"Filtering columns for task {request.task_id}: {request.selected_columns}, "
            f"include_others: {request.include_others}"
        )

        # Create filter service
        filter_service = ColumnFilterService()

        # Filter columns with OTHERS support
        filtered_file, metadata = await asyncio.to_thread(
            filter_service.filter_columns,
            task.output_file,
            request.selected_columns,
            str(OUTPUT_DIR),
            request.include_others,
            request.header_overrides,
        )

        logger.info(f"Column filtering completed: {filtered_file}")

        # Return the filtered file for download
        return FileResponse(
            filtered_file,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=Path(filtered_file).name,
            headers={
                "Content-Disposition": f'attachment; filename="{Path(filtered_file).name}"'
            },
        )

    except ValueError as e:
        # Column validation errors
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Column filtering failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Column filtering failed: {str(e)}",
        )


@app.get("/api/download-filtered/{timestamp}")
async def download_filtered_excel(timestamp: str):
    """
    Download a filtered Excel file by timestamp.

    Args:
        timestamp: Timestamp string from the filter operation (format: YYYYMMDD_HHMMSS)

    Returns:
        FileResponse with the filtered Excel file
    """
    # Find the filtered file
    filtered_filename = f"filtered_{timestamp}.xlsx"
    filtered_path = OUTPUT_DIR / filtered_filename

    if not filtered_path.exists():
        raise HTTPException(status_code=404, detail="Filtered file not found")

    return FileResponse(
        filtered_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=filtered_filename,
    )


@app.get("/api/preview-full/{task_id}", response_model=FullPreviewData)
async def get_full_preview(task_id: str):
    """
    Get full preview data with all rows for spreadsheet editor.

    Returns all rows of data (not just first 10) for display in the
    interactive spreadsheet editor.
    """
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = tasks[task_id]

    if task.status != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Task not completed. Current status: {task.status}",
        )

    if not task.output_file or not Path(task.output_file).exists():
        raise HTTPException(status_code=404, detail="Output file not found")

    try:
        import openpyxl

        wb = openpyxl.load_workbook(task.output_file, data_only=True)
        ws = wb.active

        # Find actual data range
        actual_max_row = ws.max_row if ws.max_row else 0
        actual_max_col = ws.max_column if ws.max_column else 0

        # Scan to find actual data boundaries
        last_data_row = actual_max_row
        scan_limit = max(actual_max_row + 100, 1000)
        for row in range(1, min(scan_limit + 1, 2000)):
            for col in range(1, min(actual_max_col + 100, 200)):
                cell = ws.cell(row, col)
                if cell.value is not None and str(cell.value).strip():
                    actual_max_row = max(actual_max_row, row)
                    actual_max_col = max(actual_max_col, col)
                    last_data_row = row
            if row > last_data_row + 50:
                break

        if actual_max_row == 0:
            actual_max_row = ws.max_row if ws.max_row else 100
        if actual_max_col == 0:
            actual_max_col = ws.max_column if ws.max_column else 50

        # Find data start row (skip title rows)
        data_start_row = 1
        document_title = None
        for row in range(1, min(20, actual_max_row + 1)):
            cell_value = ws.cell(row, 1).value
            if cell_value and str(cell_value).strip():
                # Check if this looks like a title row
                if row == 1 and "FORM" in str(cell_value).upper():
                    document_title = str(cell_value).strip()
                    continue
                # Check if this row looks like headers
                non_empty_count = sum(
                    1 for col in range(1, min(actual_max_col + 1, 20))
                    if ws.cell(row, col).value and str(ws.cell(row, col).value).strip()
                )
                if non_empty_count >= 2:
                    data_start_row = row
                    break

        # Get headers by merging multi-row headers and fix reversed text
        from .header_fixer import HeaderFixer
        
        headers = []
        for col in range(1, actual_max_col + 1):
            # Get values from up to 3 header rows
            header_parts = []
            
            # Check up to 3 rows for header information
            for header_row in range(data_start_row, min(data_start_row + 3, actual_max_row + 1)):
                value = ws.cell(header_row, col).value
                if value is not None and str(value).strip():
                    clean_value = str(value).strip()
                    # Skip generic phrases and party abbreviation labels
                    if clean_value.upper() not in ['PARTY ABBREVIATION', 'NO. OF VALID VOTES CAST IN FAVOUR OF']:
                        header_parts.append(clean_value)
            
            # Combine header parts into a single name
            if header_parts:
                # Use the last non-empty part (usually the party name or most specific info)
                if len(header_parts) == 1:
                    headers.append(header_parts[0])
                else:
                    # For multi-part headers, prioritize party names (usually in last row)
                    combined = " - ".join(header_parts[-2:]) if len(header_parts) >= 2 else header_parts[-1]
                    headers.append(combined)
            else:
                # Fallback for empty columns
                headers.append(f"Column {col}")
        
        # Fix reversed text in headers
        headers = HeaderFixer.fix_header_list(headers)

        if not headers:
            for col in range(1, min(actual_max_col + 1, 50)):
                headers.append(f"Column {col}")

        # Get ALL data rows (not just first 10)
        # Find where actual data starts (first row with numeric data in first column)
        first_data_row = data_start_row + 1
        for row in range(data_start_row + 1, min(data_start_row + 10, actual_max_row + 1)):
            cell_val = ws.cell(row, 1).value
            # Check if this looks like data (numeric or starts with a number)
            if cell_val is not None:
                if isinstance(cell_val, (int, float)) or (isinstance(cell_val, str) and cell_val.strip().isdigit()):
                    first_data_row = row
                    break
        
        rows = []
        for row_idx in range(first_data_row, actual_max_row + 1):
            row_data = []
            num_cols_to_read = max(len(headers), actual_max_col)
            for col in range(1, num_cols_to_read + 1):
                value = ws.cell(row_idx, col).value
                row_data.append(value)
            while len(row_data) < len(headers):
                row_data.append(None)
            if len(row_data) > len(headers):
                row_data = row_data[:len(headers)]
            rows.append(row_data)

        total_rows = len(rows)
        wb.close()

        return FullPreviewData(
            headers=headers,
            rows=rows,
            total_rows=total_rows,
            total_columns=len(headers),
            pages_processed=1,
            document_title=document_title,
        )

    except Exception as e:
        logger.error(f"Failed to read full preview: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read preview: {str(e)}",
        )


@app.post("/api/download-modified")
async def download_modified_excel(request: DownloadModifiedRequest):
    """
    Generate and download Excel file from modified spreadsheet data.

    Accepts the edited data from the spreadsheet editor and creates
    a new Excel file with the modifications.
    """
    if request.task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = tasks[request.task_id]

    try:
        import openpyxl
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
        from openpyxl.utils import get_column_letter

        # Create new workbook
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Modified Data"

        # Define styles
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF", size=10)
        header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        thin_border = Border(
            left=Side(style="thin"),
            right=Side(style="thin"),
            top=Side(style="thin"),
            bottom=Side(style="thin"),
        )

        # Add document title if provided
        start_row = 1
        if request.document_title:
            ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(request.headers))
            title_cell = ws.cell(row=1, column=1)
            title_cell.value = request.document_title
            title_cell.font = Font(bold=True, size=14)
            title_cell.alignment = Alignment(horizontal="center")
            start_row = 3

        # Write headers
        for col_idx, header in enumerate(request.headers, 1):
            cell = ws.cell(row=start_row, column=col_idx)
            cell.value = header
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = header_alignment
            cell.border = thin_border

        # Write data rows
        for row_idx, row_data in enumerate(request.rows, start_row + 1):
            for col_idx, value in enumerate(row_data, 1):
                cell = ws.cell(row=row_idx, column=col_idx)
                cell.value = value
                cell.border = thin_border
                cell.alignment = Alignment(horizontal="center", vertical="center")

        # Auto-adjust column widths
        for col_idx in range(1, len(request.headers) + 1):
            column_letter = get_column_letter(col_idx)
            max_length = 0
            for row in range(start_row, start_row + len(request.rows) + 1):
                cell_value = ws.cell(row=row, column=col_idx).value
                if cell_value:
                    max_length = max(max_length, len(str(cell_value)))
            adjusted_width = min(max_length + 2, 30)
            ws.column_dimensions[column_letter].width = max(adjusted_width, 10)

        # Freeze header row
        ws.freeze_panes = ws.cell(row=start_row + 1, column=1)

        # Generate output filename
        output_filename = f"modified_{task.task_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"
        output_path = OUTPUT_DIR / output_filename

        wb.save(str(output_path))
        wb.close()

        logger.info(f"Modified Excel saved: {output_path}")

        # Return file for download
        original_name = Path(task.filename).stem if task.filename else "data"
        download_name = f"{original_name}_modified.xlsx"

        return FileResponse(
            str(output_path),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=download_name,
        )

    except Exception as e:
        logger.error(f"Failed to create modified Excel: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create modified Excel: {str(e)}",
        )


# Startup event for cleanup task
@app.on_event("startup")
async def startup_event():
    """Initialize cleanup background task."""

    logger.info("PDF to Excel Converter API started")

    async def periodic_cleanup():
        from datetime import timedelta

        while True:
            await asyncio.sleep(3600)  # Run every hour

            # Cleanup old tasks (older than 1 hour)
            cutoff = datetime.utcnow() - timedelta(hours=1)
            tasks_to_delete = []

            for task_id, task in tasks.items():
                if task.created_at < cutoff:
                    tasks_to_delete.append(task_id)

            for task_id in tasks_to_delete:
                try:
                    task = tasks[task_id]
                    if task.output_file and Path(task.output_file).exists():
                        await cleanup_file(Path(task.output_file))
                    del tasks[task_id]
                except Exception:
                    pass

            # Cleanup orphaned files
            for file_path in UPLOAD_DIR.glob("*.pdf"):
                try:
                    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if mtime < cutoff:
                        await cleanup_file(file_path)
                except Exception:
                    pass

            for file_path in OUTPUT_DIR.glob("*.xlsx"):
                try:
                    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if mtime < cutoff:
                        await cleanup_file(file_path)
                except Exception:
                    pass

    asyncio.create_task(periodic_cleanup())


