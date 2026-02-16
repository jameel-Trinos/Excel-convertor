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
    extraction_method: str = Field(default="pdfplumber", description="Method used for extraction: 'pdfplumber', 'azure_di', or 'structured'")
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score for extraction quality (0.0 to 1.0)")
    merged_cells: list[dict] = Field(default_factory=list, description="Merged cell information from Document AI: [{row, col, row_span, col_span, value, is_header}]")

    @property
    def is_empty(self) -> bool:
        """Check if the table has no data."""
        return len(self.rows) == 0


class ExtractionResult(BaseModel):
    """Complete extraction result including tables."""

    tables: list[TableData] = Field(default_factory=list)
    page_texts: list[str] = Field(default_factory=list)
    ac_number: Optional[str] = Field(default=None, description="Assembly Constituency number extracted from PDF")




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
    header_overrides: Optional[dict[str, str]] = Field(
        default=None,
        description="Optional mapping of original column name -> desired output header name",
    )
    sum_other_columns: Optional[list[str]] = Field(
        default=None,
        description="List of unselected numeric/party column names whose values should be summed into an 'Other' column",
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


# Geocoding Models

class GeocodeRequest(BaseModel):
    """Request model for starting geocoding operation."""

    task_id: str = Field(..., description="Task ID of the Excel file")
    address_column: str = Field(..., description="Column name containing addresses to geocode")
    region_hint: str = Field(
        default="Tamil Nadu, India",
        description="Region hint to improve geocoding accuracy"
    )


class GeocodeProgressEvent(BaseModel):
    """SSE event for geocoding progress updates."""

    current: int = Field(..., description="Current address being processed (1-indexed)")
    total: int = Field(..., description="Total number of addresses to geocode")
    status: Literal["geocoding", "completed", "failed", "cancelled"] = Field(
        ..., description="Current geocoding status"
    )
    message: str = Field(..., description="Human-readable progress message")
    success_count: int = Field(default=0, description="Number of successfully geocoded addresses")
    failed_count: int = Field(default=0, description="Number of failed geocoding attempts")


class GeocodeStartResponse(BaseModel):
    """Response after starting geocoding operation."""

    geocode_task_id: str = Field(..., description="Task ID for tracking geocoding progress")
    total_addresses: int = Field(..., description="Total number of addresses to geocode")
    message: str = Field(default="Geocoding started")


class GeocodeResultItem(BaseModel):
    """Result of geocoding a single address."""

    row_index: int = Field(..., description="Row index in the original data (0-indexed)")
    latitude: Optional[float] = Field(default=None, description="Latitude coordinate")
    longitude: Optional[float] = Field(default=None, description="Longitude coordinate")
    status: Literal["success", "not_found", "error"] = Field(
        ..., description="Geocoding status for this address"
    )
    error: Optional[str] = Field(default=None, description="Error message if geocoding failed")


class GeocodeApplyRequest(BaseModel):
    """Request model for applying geocoding results to spreadsheet data."""

    geocode_task_id: str = Field(..., description="Geocoding task ID")
    task_id: str = Field(..., description="Original conversion task ID")
    headers: list[str] = Field(..., description="Current column headers")
    rows: list[list[Any]] = Field(..., description="Current row data")


class GeocodeApplyResponse(BaseModel):
    """Response after applying geocoding results."""

    headers: list[str] = Field(..., description="Updated headers with Latitude/Longitude columns")
    rows: list[list[Any]] = Field(..., description="Updated rows with coordinate data")
    total_geocoded: int = Field(..., description="Total addresses processed")
    successful: int = Field(..., description="Successfully geocoded count")
    failed: int = Field(..., description="Failed geocoding count")


# Translation Models

class TranslateRequest(BaseModel):
    """Request model for starting translation operation."""

    task_id: str = Field(..., description="Task ID of the Excel file to translate")
    target_lang: Literal["tamil", "hindi", "english"] = Field(
        default="tamil",
        description="Target language: 'tamil', 'hindi', or 'english'"
    )


class TranslateStartResponse(BaseModel):
    """Response after starting translation operation."""

    translate_task_id: str = Field(..., description="Task ID for tracking translation progress")
    total_cells: int = Field(..., description="Total number of cells to translate")
    message: str = Field(default="Translation started")


class TranslateProgressEvent(BaseModel):
    """SSE event for translation progress updates."""

    current: int = Field(..., description="Current cell being processed")
    total: int = Field(..., description="Total number of cells to translate")
    status: Literal["translating", "completed", "failed", "cancelled"] = Field(
        ..., description="Current translation status"
    )
    message: str = Field(..., description="Human-readable progress message")


class TranslateStatusResponse(BaseModel):
    """Response for checking translation availability."""

    task_id: str = Field(..., description="Original task ID")
    has_tamil_version: bool = Field(default=False, description="Whether Tamil version exists")
    has_hindi_version: bool = Field(default=False, description="Whether Hindi version exists")
    has_english_version: bool = Field(default=False, description="Whether English version exists")
    tamil_file_path: Optional[str] = Field(default=None, description="Path to Tamil Excel file")
    hindi_file_path: Optional[str] = Field(default=None, description="Path to Hindi Excel file")
    english_file_path: Optional[str] = Field(default=None, description="Path to English Excel file")


class AddBoothNameColumnRequest(BaseModel):
    """Request model for adding booth name column."""

    task_id: str = Field(..., description="Task ID of the Excel file")
    source_column: str = Field(..., description="Column name to extract booth names from")


class NormalizeColumnRequest(BaseModel):
    """Request model for normalizing a column."""

    task_id: str = Field(..., description="Task ID of the Excel file")
    column_name: str = Field(..., description="Column name to normalize")
