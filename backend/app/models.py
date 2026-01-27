"""Pydantic models for the PDF to Excel Converter API."""

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ConversionTask(BaseModel):
    """Model representing a PDF conversion task."""

    task_id: str = Field(..., description="Unique identifier for the task")
    filename: str = Field(..., description="Original filename of the uploaded PDF")
    status: Literal["pending", "processing", "completed", "failed", "needs_review"] = Field(
        default="pending", description="Current status of the conversion"
    )
    progress: int = Field(default=0, ge=0, le=100, description="Progress percentage (0-100)")
    message: str = Field(default="", description="Human-readable status message")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    output_file: Optional[str] = Field(default=None, description="Path to generated Excel file")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    validation_issues: Optional[list] = Field(default=None, description="Validation issues if needs_review status")

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "abc123",
                "filename": "election_results.pdf",
                "status": "processing",
                "progress": 45,
                "message": "Extracting tables from page 5 of 10...",
                "created_at": "2024-01-20T10:30:00Z",
                "output_file": None,
                "error": None
            }
        }


class UploadResponse(BaseModel):
    """Response after successful file upload."""

    task_id: str = Field(..., description="Task ID for tracking conversion")
    filename: str = Field(..., description="Name of uploaded file")
    size: int = Field(..., description="File size in bytes")
    message: str = Field(default="File uploaded successfully")


class StatusResponse(BaseModel):
    """Response for status check endpoint."""

    task_id: str
    status: Literal["pending", "processing", "completed", "failed", "needs_review"]
    progress: int
    message: str
    output_file: Optional[str] = None
    error: Optional[str] = None
    validation_issues: Optional[dict] = None


class ProgressEvent(BaseModel):
    """SSE progress event data."""

    progress: int
    status: str
    message: str
    step: Optional[str] = None


class PreviewData(BaseModel):
    """Preview of extracted table data."""

    headers: list[str] = Field(..., description="Column headers")
    rows: list[list[Any]] = Field(..., description="Data rows (first 10)")
    total_rows: int = Field(..., description="Total number of rows extracted")
    total_columns: int = Field(..., description="Total number of columns")
    pages_processed: int = Field(..., description="Number of PDF pages processed")


class TableData(BaseModel):
    """Extracted table data from a PDF page."""

    headers: list[str] = Field(default_factory=list)
    rows: list[list[Any]] = Field(default_factory=list)
    page_number: int = Field(default=1)
    title_rows: list[list[str]] = Field(default_factory=list, description="Title rows extracted from PDF (merged cells)")
    header_rows: list[list[str]] = Field(default_factory=list, description="Multi-row headers if present")
    extraction_method: str = Field(default="pdfplumber", description="Method used for extraction: 'pdfplumber' or 'ocr'")
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score for extraction quality (0.0 to 1.0)")

    @property
    def is_empty(self) -> bool:
        """Check if the table has no data."""
        return len(self.rows) == 0


class ExtractionResult(BaseModel):
    """Complete extraction result including tables."""

    tables: list[TableData] = Field(default_factory=list)
    page_texts: list[str] = Field(default_factory=list)




class ExcelMetadata(BaseModel):
    """Metadata for Excel file generation."""

    title: Optional[str] = Field(default=None, description="Document title")
    source_filename: str = Field(..., description="Original PDF filename")
    extraction_date: datetime = Field(default_factory=datetime.utcnow)
    total_pages: int = Field(default=1)
    total_rows: int = Field(default=0)




class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Human-readable error message")
    detail: Optional[str] = Field(default=None, description="Additional details")


class FilterColumnsRequest(BaseModel):
    """Request model for filtering Excel columns."""

    task_id: str = Field(..., description="Task ID of the Excel file to filter")
    columns: list[str] = Field(..., description="List of column names to keep (in desired order)")


class FilterExcelRequest(BaseModel):
    """Request model for filtering Excel columns with OTHERS support."""

    task_id: str = Field(..., description="Task ID of the Excel file to filter")
    selected_columns: list[str] = Field(..., description="List of column names to keep (in desired order)")
    include_others: bool = Field(default=False, description="Whether to include an OTHERS column with sum of unselected party columns")
    header_overrides: Optional[dict[str, str]] = Field(
        default=None,
        description="Optional mapping of original column name -> desired output header name",
    )


class FilterColumnsResponse(BaseModel):
    """Response model for column filtering operation."""

    filtered_file_path: str = Field(..., description="Path to the filtered Excel file")
    original_file: str = Field(..., description="Path to the original Excel file")
    selected_columns: list[str] = Field(..., description="Columns that were selected")
    total_columns: int = Field(..., description="Number of columns in filtered file")
    total_rows: int = Field(..., description="Number of data rows")
    columns_removed: int = Field(..., description="Number of columns removed from original")
    timestamp: str = Field(..., description="Timestamp of the filtering operation")


class FullPreviewData(BaseModel):
    """Full preview data with all rows for spreadsheet editor."""

    headers: list[str] = Field(..., description="Column headers")
    rows: list[list[Any]] = Field(..., description="All data rows")
    total_rows: int = Field(..., description="Total number of rows")
    total_columns: int = Field(..., description="Total number of columns")
    pages_processed: int = Field(..., description="Number of PDF pages processed")
    document_title: Optional[str] = Field(default=None, description="Document title if available")


class CellData(BaseModel):
    """Represents a single cell's data."""
    
    row: int = Field(..., description="Row index (0-based)")
    col: int = Field(..., description="Column index (0-based)")
    value: Any = Field(..., description="Cell value")


class DownloadModifiedRequest(BaseModel):
    """Request model for downloading modified Excel data."""

    task_id: str = Field(..., description="Original task ID")
    headers: list[str] = Field(..., description="Column headers")
    rows: list[list[Any]] = Field(..., description="All data rows (including edits)")
    document_title: Optional[str] = Field(default=None, description="Document title")
