/**
 * Type definitions for the PDF to Excel Converter frontend
 */

export type UploadStatus =
  | "idle"
  | "uploading"
  | "processing"
  | "completed"
  | "error"
  | "needs_review";

export interface UploadState {
  status: UploadStatus;
  progress: number;
  message: string;
  taskId?: string;
  error?: string;
  filename?: string;
  fileSize?: number;
}

export interface UploadResponse {
  task_id: string;
  filename: string;
  size: number;
  message: string;
}

export interface ValidationIssues {
  passed: boolean;
  confidence: number;
  issues: string[];
  warnings: string[];
  suggestions: string[];
}

export interface StatusResponse {
  task_id: string;
  status: "pending" | "processing" | "completed" | "failed" | "needs_review";
  progress: number;
  message: string;
  output_file?: string;
  error?: string;
  validation_issues?: ValidationIssues;
}

export interface ProgressEvent {
  progress: number;
  status: string;
  message: string;
  step?: string;
}

export interface PreviewData {
  headers: string[];
  rows: (string | number | null)[][];
  total_rows: number;
  total_columns: number;
  pages_processed: number;
}

export interface TableData {
  headers: string[];
  rows: (string | number | null)[][];
  page_number: number;
}

export interface FileInfo {
  name: string;
  size: number;
  type: string;
}

export interface ConversionResult {
  taskId: string;
  filename: string;
  totalRows: number;
  totalColumns: number;
  downloadUrl: string;
}

export interface FilterExcelRequest {
  selected_columns: string[];
  header_overrides?: Record<string, string>;
}

export interface FilterExcelResponse {
  task_id: string;
  message: string;
  filtered_columns: string[];
}

export interface FullPreviewData {
  headers: string[];
  rows: (string | number | null)[][];
  total_rows: number;
  total_columns: number;
  pages_processed: number;
  document_title?: string;
}

export interface DownloadModifiedRequest {
  task_id: string;
  headers: string[];
  rows: (string | number | null)[][];
  document_title?: string;
}

export type CellValue = string | number | null;

// Geocoding Types

export interface GeocodeStartResponse {
  geocode_task_id: string;
  total_addresses: number;
  message: string;
}

export interface GeocodeProgressEvent {
  current: number;
  total: number;
  status: "geocoding" | "completed" | "failed" | "cancelled";
  message: string;
  success_count: number;
  failed_count: number;
}

export interface GeocodeApplyRequest {
  geocode_task_id: string;
  task_id: string;
  headers: string[];
  rows: CellValue[][];
}

export interface GeocodeApplyResponse {
  headers: string[];
  rows: CellValue[][];
  total_geocoded: number;
  successful: number;
  failed: number;
}
