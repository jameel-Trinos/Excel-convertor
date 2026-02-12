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

/**
 * Upload a PDF file for conversion
 */
export async function uploadPdf(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/api/upload`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || "Upload failed");
  }

  return response.json();
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
