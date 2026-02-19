/**
 * API client functions for the PDF to Excel Converter
 */

import type {
  UploadResponse,
  StatusResponse,
  PreviewData,
  ProgressEvent,
  FilterExcelResponse,
  FullPreviewData,
  DownloadModifiedRequest,
  CellValue,
  GeocodeStartResponse,
  GeocodeProgressEvent,
  GeocodeApplyResponse,
} from "@/types";
import { cleanFilename } from "@/lib/utils";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/** Upload request timeout (OCR can make backend slow to respond on first request) */
const UPLOAD_TIMEOUT_MS = 120_000; // 2 minutes
/** Extended timeout for voter PDFs (scanned pages need OCR which is slower) */
const VOTER_UPLOAD_TIMEOUT_MS = 300_000; // 5 minutes

export interface UploadOptions {
  /** Always use OCR with higher DPI (for complex/image election PDFs) */
  forceOcr?: boolean;
}

function getErrorMessage(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0];
    if (first && typeof first === "object" && "msg" in first) {
      return String((first as { msg?: string }).msg) || "Validation failed";
    }
  }
  return "Upload failed";
}

/**
 * Upload a PDF file for conversion
 */
export async function uploadPdf(
  file: File,
  options?: UploadOptions
): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const url = new URL(`${API_BASE_URL}/api/upload`);
  if (options?.forceOcr) {
    url.searchParams.set("force_ocr", "true");
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), UPLOAD_TIMEOUT_MS);

  try {
    const response = await fetch(url.toString(), {
      method: "POST",
      body: formData,
      signal: controller.signal,
    });

    const contentType = response.headers.get("content-type") ?? "";
    const isJson = contentType.includes("application/json");

    if (!response.ok) {
      const msg = isJson
        ? getErrorMessage((await response.json().catch(() => ({}))).detail)
        : `Server error (${response.status})`;
      throw new Error(msg);
    }

    const data = await response.json().catch(() => null);
    if (!data || typeof data.task_id !== "string") {
      throw new Error("Invalid server response. Please try again.");
    }
    return data as UploadResponse;
  } catch (err) {
    if (err instanceof Error && err.name === "AbortError") {
      throw new Error(
        "Upload timed out. The file may be large or the server is busy. Try again."
      );
    }
    if (err instanceof TypeError && err.message === "Failed to fetch") {
      throw new Error(
        "Cannot reach the server. Make sure the backend is running at " +
          (API_BASE_URL || "http://localhost:8000")
      );
    }
    throw err;
  } finally {
    clearTimeout(timeoutId);
  }
}

/**
 * Upload a PDF file for voters data extraction
 */
export async function uploadVotersPdf(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), VOTER_UPLOAD_TIMEOUT_MS);

  try {
    const response = await fetch(`${API_BASE_URL}/api/voters/upload`, {
      method: "POST",
      body: formData,
      signal: controller.signal,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || "Voters upload failed");
    }

    return response.json();
  } catch (err) {
    if (err instanceof Error && err.name === "AbortError") {
      throw new Error("Upload timed out. The file may be large or the server is busy. Try again.");
    }
    if (err instanceof TypeError && err.message === "Failed to fetch") {
      throw new Error(
        "Cannot reach the server. Make sure the backend is running at " +
          (API_BASE_URL || "http://localhost:8000")
      );
    }
    throw err;
  } finally {
    clearTimeout(timeoutId);
  }
}

/**
 * Start an async voter PDF conversion. Returns a job_id for polling.
 */
export async function startVoterConvert(file: File): Promise<{ job_id: string }> {
  const formData = new FormData();
  formData.append("pdf_file", file);

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), VOTER_UPLOAD_TIMEOUT_MS);

  try {
    const response = await fetch(`${API_BASE_URL}/api/voters/convert-pdf`, {
      method: "POST",
      body: formData,
      signal: controller.signal,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `Upload failed (${response.status})`);
    }

    return response.json();
  } catch (err) {
    if (err instanceof Error && err.name === "AbortError") {
      throw new Error("Upload timed out. The file may be large or the server is busy. Try again.");
    }
    if (err instanceof TypeError && err.message === "Failed to fetch") {
      throw new Error(
        "Cannot reach the server. Make sure the backend is running at " +
          (API_BASE_URL || "http://localhost:8000")
      );
    }
    throw err;
  } finally {
    clearTimeout(timeoutId);
  }
}

export interface VoterConvertStatus {
  status: "processing" | "completed" | "failed";
  progress: { current_page: number; total_pages: number };
  download_url?: string;
  error?: string;
}

/**
 * Poll the status of a voter PDF conversion job.
 */
export async function getVoterConvertStatus(jobId: string): Promise<VoterConvertStatus> {
  const response = await fetch(`${API_BASE_URL}/api/voters/convert-status/${jobId}`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || "Failed to get conversion status");
  }

  return response.json();
}

/**
 * Download the Excel file from a completed voter conversion job.
 */
export async function downloadVoterConvert(jobId: string, originalFilename: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/voters/download/${jobId}`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || "Download failed");
  }

  const blob = await response.blob();
  const disposition = response.headers.get("content-disposition") ?? "";
  const filenameMatch = disposition.match(/filename="?([^";\n]+)"?/);
  const filename = filenameMatch?.[1] || originalFilename.replace(".pdf", ".xlsx");

  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
}

// ============================================================================
// Bulk Voter Processing API Functions
// ============================================================================

/**
 * Initialize a bulk voter upload job. Returns a job_id for subsequent calls.
 */
export async function initBulkVoterUpload(): Promise<{ job_id: string }> {
  const response = await fetch(`${API_BASE_URL}/api/voters/bulk-upload/init`, {
    method: "POST",
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || "Failed to initialize bulk upload");
  }
  return response.json();
}

/**
 * Upload a batch of PDFs to an existing bulk job. Call multiple times for large sets.
 */
export async function addBulkVoterFiles(
  jobId: string,
  files: File[]
): Promise<{ added: number; total: number }> {
  const formData = new FormData();
  files.forEach((f) => formData.append("files", f));

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), VOTER_UPLOAD_TIMEOUT_MS);

  try {
    const response = await fetch(
      `${API_BASE_URL}/api/voters/bulk-upload/add/${jobId}`,
      { method: "POST", body: formData, signal: controller.signal }
    );
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || "Failed to upload batch");
    }
    return response.json();
  } finally {
    clearTimeout(timeoutId);
  }
}

/**
 * Start concurrent processing of all uploaded PDFs for a bulk job.
 */
export async function startBulkVoterProcessing(
  jobId: string
): Promise<{ job_id: string; total_files: number }> {
  const response = await fetch(
    `${API_BASE_URL}/api/voters/bulk-upload/start/${jobId}`,
    { method: "POST" }
  );
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || "Failed to start bulk processing");
  }
  return response.json();
}

export interface BulkVoterProgress {
  total_pdfs: number;
  completed_pdfs: number;
  current_file: string;
  total_voters_so_far: number;
  failed_count: number;
}

export interface BulkVoterSummary {
  total_voters: number;
  successful_pdfs: number;
  total_pdfs: number;
  failed_pdfs: { filename: string; error: string }[];
  booth_groups: {
    part_no: string;
    address: string;
    voter_count: number;
    filename: string;
  }[];
}

export interface BulkVoterStatus {
  status: "uploading" | "processing" | "completed" | "failed";
  progress: BulkVoterProgress;
  download_url?: string;
  error?: string;
  summary?: BulkVoterSummary;
}

/**
 * Poll the status of a bulk voter processing job.
 */
export async function getBulkVoterStatus(
  jobId: string
): Promise<BulkVoterStatus> {
  const response = await fetch(
    `${API_BASE_URL}/api/voters/bulk-status/${jobId}`
  );
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || "Failed to get bulk status");
  }
  return response.json();
}

/**
 * Download the consolidated Excel from a completed bulk voter job.
 */
export async function downloadBulkVoters(
  jobId: string,
  filename: string = "voters_consolidated.xlsx"
): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/api/voters/bulk-download/${jobId}`
  );
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || "Download failed");
  }

  const blob = await response.blob();
  const disposition = response.headers.get("content-disposition") ?? "";
  const filenameMatch = disposition.match(/filename="?([^";\n]+)"?/);
  const downloadName = filenameMatch?.[1] || filename;

  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = downloadName;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
}

/**
 * Upload a PDF file for booth-specific conversion
 */
export async function uploadBoothPdf(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/api/booth/upload`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || "Booth upload failed");
  }

  return response.json();
}

/**
 * Get the status of a conversion task
 */
export async function getStatus(taskId: string): Promise<StatusResponse> {
  const response = await fetch(`${API_BASE_URL}/api/status/${taskId}`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || "Failed to get status");
  }

  return response.json();
}

/**
 * Subscribe to progress updates via Server-Sent Events
 */
export function subscribeToProgress(
  taskId: string,
  onProgress: (event: ProgressEvent) => void,
  onComplete: () => void,
  onError: (error: Error) => void
): () => void {
  const eventSource = new EventSource(
    `${API_BASE_URL}/api/progress/${taskId}`
  );

  eventSource.addEventListener("progress", (event) => {
    try {
      const data: ProgressEvent = JSON.parse(event.data);
      onProgress(data);

      if (data.status === "completed" || data.status === "failed" || data.status === "needs_review") {
        eventSource.close();
        if (data.status === "completed") {
          onComplete();
        } else if (data.status === "needs_review") {
          // For needs_review, we don't call onError, just let the status update
          // The frontend will handle displaying the needs_review state
        } else {
          onError(new Error(data.message || "Conversion failed"));
        }
      }
    } catch (e) {
      console.error("Failed to parse progress event:", e);
    }
  });

  eventSource.onerror = () => {
    eventSource.close();
    onError(new Error("Connection to server lost"));
  };

  // Return cleanup function
  return () => {
    eventSource.close();
  };
}

/**
 * Get preview data for a completed conversion
 */
export async function getPreview(taskId: string): Promise<PreviewData> {
  const response = await fetch(`${API_BASE_URL}/api/preview/${taskId}`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || "Failed to get preview");
  }

  return response.json();
}

/**
 * Download the generated Excel file
 */
export async function downloadExcel(
  taskId: string,
  filename: string
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/download/${taskId}`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || "Download failed");
  }

  // Create blob and download
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = cleanFilename(filename.replace(".pdf", ".xlsx"));
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
}

/**
 * Get the download URL for a task
 */
export function getDownloadUrl(taskId: string): string {
  return `${API_BASE_URL}/api/download/${taskId}`;
}

/**
 * Filter Excel file to include only selected columns
 */
export async function filterExcel(
  taskId: string,
  selectedColumns: string[],
  filename: string,
  headerOverrides?: Record<string, string>,
  sumOtherColumns?: string[]
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/filter-excel`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      task_id: taskId,
      selected_columns: selectedColumns,
      header_overrides: headerOverrides,
      sum_other_columns: sumOtherColumns,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || "Failed to filter Excel");
  }

  // Download the filtered Excel file
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  const cleanName = cleanFilename(filename);
  // Re-add _filtered suffix if needed, or just keep it clean? 
  // User asked for "just name.xls", so maybe we should avoid _filtered too?
  // But filterExcel implies a different content. I'll stick to cleaning the base name and adding suffix if appropriate,
  // or just clean it. The user said "saved as just name.xls".
  // Let's use cleanFilename for the base and add _filtered.xlsx, BUT maybe cleanFilename removes suffixes?
  // cleanFilename removes _modified. It doesn't remove _filtered.
  // safely: cleanFilename("xx_name.pdf") -> "name.pdf" -> replace .pdf with _filtered.xlsx
  a.download = cleanFilename(filename).replace(/\.[^/.]+$/, "") + "_filtered.xlsx";
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
}

/**
 * Get full preview data with all rows for spreadsheet editor
 */
export async function getFullPreview(taskId: string): Promise<FullPreviewData> {
  const response = await fetch(`${API_BASE_URL}/api/preview-full/${taskId}`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || "Failed to get full preview");
  }

  return response.json();
}

/**
 * Get column names directly from the converted Excel file
 */
export async function getColumns(taskId: string): Promise<{ columns: string[] }> {
  const response = await fetch(`${API_BASE_URL}/api/columns/${taskId}`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || "Failed to get columns");
  }

  return response.json();
}

/**
 * Download modified Excel file with edited data
 */
export async function downloadModifiedExcel(
  taskId: string,
  headers: string[],
  rows: CellValue[][],
  filename: string,
  documentTitle?: string
): Promise<void> {
  const requestBody: DownloadModifiedRequest = {
    task_id: taskId,
    headers,
    rows,
    document_title: documentTitle,
  };

  const response = await fetch(`${API_BASE_URL}/api/download-modified`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(requestBody),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || "Failed to download modified Excel");
  }

  // Download the modified Excel file
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  // User explicitly asked for "just name.xls" instead of "xx_name_modified..."
  // `cleanFilename` removes `_modified` suffix and prefixes.
  // So cleanFilename("01_Name.pdf") -> "Name.pdf"
  // cleanFilename("Name_modified.xlsx") -> "Name.xlsx"
  // Here filename is likely the original PDF name.
  a.download = cleanFilename(filename).replace(/\.[^/.]+$/, "") + ".xlsx";
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
}

// ============================================================================
// Geocoding API Functions
// ============================================================================

/**
 * Start geocoding addresses from a specific column
 */
export async function startGeocoding(
  taskId: string,
  addressColumn: string,
  regionHint: string = "Tamil Nadu, India"
): Promise<GeocodeStartResponse> {
  const response = await fetch(`${API_BASE_URL}/api/geocode/start`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      task_id: taskId,
      address_column: addressColumn,
      region_hint: regionHint,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || "Failed to start geocoding");
  }

  return response.json();
}

/**
 * Subscribe to geocoding progress updates via Server-Sent Events
 */
export function subscribeToGeocodeProgress(
  geocodeTaskId: string,
  onProgress: (event: GeocodeProgressEvent) => void,
  onComplete: (event: GeocodeProgressEvent) => void,
  onError: (error: Error) => void
): () => void {
  const eventSource = new EventSource(
    `${API_BASE_URL}/api/geocode/progress/${geocodeTaskId}`
  );

  eventSource.addEventListener("progress", (event) => {
    try {
      const data: GeocodeProgressEvent = JSON.parse(event.data);
      onProgress(data);

      if (data.status === "completed" || data.status === "failed" || data.status === "cancelled") {
        eventSource.close();
        if (data.status === "completed" || data.status === "cancelled") {
          onComplete(data);
        } else {
          onError(new Error(data.message || "Geocoding failed"));
        }
      }
    } catch (e) {
      console.error("Failed to parse geocode progress event:", e);
    }
  });

  eventSource.onerror = () => {
    eventSource.close();
    onError(new Error("Connection to geocoding server lost"));
  };

  // Return cleanup function
  return () => {
    eventSource.close();
  };
}

/**
 * Cancel an ongoing geocoding operation
 */
export async function cancelGeocoding(geocodeTaskId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/geocode/cancel/${geocodeTaskId}`, {
    method: "POST",
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || "Failed to cancel geocoding");
  }
}

/**
 * Apply geocoding results to spreadsheet data
 */
export async function applyGeocoding(
  geocodeTaskId: string,
  taskId: string,
  headers: string[],
  rows: CellValue[][]
): Promise<GeocodeApplyResponse> {
  const response = await fetch(`${API_BASE_URL}/api/geocode/apply`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      geocode_task_id: geocodeTaskId,
      task_id: taskId,
      headers,
      rows,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || "Failed to apply geocoding");
  }

  return response.json();
}

/**
 * Add Booth name column by extracting text before comma from source column
 */
export async function addBoothNameColumn(
  taskId: string,
  sourceColumn: string
): Promise<FullPreviewData> {
  const response = await fetch(`${API_BASE_URL}/api/booth/add-booth-name-column`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      task_id: taskId,
      source_column: sourceColumn,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || "Failed to add booth name column");
  }

  return response.json();
}


/**
 * Normalize a column to Party Names
 */
export async function normalizeColumn(
  taskId: string,
  columnName: string
): Promise<FullPreviewData> {
  const response = await fetch(`${API_BASE_URL}/api/normalize-column`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      task_id: taskId,
      column_name: columnName,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || "Failed to normalize column");
  }

  return response.json();
}

/**
 * Normalize all headers to Party Names
 */
export async function normalizeHeaders(
  taskId: string
): Promise<FullPreviewData> {
  const response = await fetch(`${API_BASE_URL}/api/normalize-headers`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      task_id: taskId,
      column_name: "", // Not used
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || "Failed to normalize headers");
  }

  return response.json();
}
