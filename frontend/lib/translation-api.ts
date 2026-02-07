/**
 * Translation API client functions for multi-language translation feature (Tamil, Hindi, English).
 */

import type {
  TranslateStartResponse,
  TranslateProgressEvent,
  TranslateStatusResponse,
  FullPreviewData,
} from "@/types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * Start translating an Excel file to Tamil, Hindi, or English.
 */
export async function startTranslation(
  taskId: string,
  targetLang: "tamil" | "hindi" | "english"
): Promise<TranslateStartResponse> {
  const response = await fetch(`${API_BASE_URL}/api/translate/start`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      task_id: taskId,
      target_lang: targetLang,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || "Failed to start translation");
  }

  return response.json();
}

/**
 * Subscribe to translation progress updates via Server-Sent Events.
 */
export function subscribeToTranslateProgress(
  translateTaskId: string,
  onProgress: (event: TranslateProgressEvent) => void,
  onComplete: () => void,
  onError: (error: Error) => void
): () => void {
  const eventSource = new EventSource(
    `${API_BASE_URL}/api/translate/progress/${translateTaskId}`
  );

  eventSource.addEventListener("progress", (event) => {
    try {
      const data: TranslateProgressEvent = JSON.parse(event.data);
      onProgress(data);

      if (
        data.status === "completed" ||
        data.status === "failed" ||
        data.status === "cancelled"
      ) {
        eventSource.close();
        if (data.status === "completed") {
          onComplete();
        } else if (data.status === "failed") {
          onError(new Error(data.message || "Translation failed"));
        }
        // For cancelled, we don't call onError
      }
    } catch (e) {
      console.error("Failed to parse translate progress event:", e);
    }
  });

  eventSource.onerror = () => {
    eventSource.close();
    onError(new Error("Connection to translation server lost"));
  };

  // Return cleanup function
  return () => {
    eventSource.close();
  };
}

/**
 * Check if translated versions exist for a task.
 */
export async function getTranslateStatus(
  taskId: string
): Promise<TranslateStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/api/translate/status/${taskId}`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || "Failed to get translation status");
  }

  return response.json();
}

/**
 * Cancel an ongoing translation operation.
 */
export async function cancelTranslation(translateTaskId: string): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/api/translate/cancel/${translateTaskId}`,
    {
      method: "POST",
    }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || "Failed to cancel translation");
  }
}

/**
 * Get the download URL for a translated Excel file.
 */
export function getTranslatedDownloadUrl(
  taskId: string,
  language: "original" | "tamil" | "hindi" | "english"
): string {
  return `${API_BASE_URL}/api/download/${taskId}/${language}`;
}

/**
 * Download a translated Excel file.
 */
export async function downloadTranslatedExcel(
  taskId: string,
  language: "original" | "tamil" | "hindi" | "english",
  filename: string
): Promise<void> {
  const response = await fetch(getTranslatedDownloadUrl(taskId, language));

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || "Download failed");
  }

  // Create blob and download
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;

  // Add language suffix to filename
  const baseName = filename.replace(".pdf", "").replace(".xlsx", "");
  const langSuffix = language === "original" ? "" : `_${language}`;
  a.download = `${baseName}${langSuffix}.xlsx`;

  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
}

/**
 * Get full preview data for a translated Excel file.
 */
export async function getTranslatedFullPreview(
  taskId: string,
  language: "original" | "tamil" | "hindi" | "english"
): Promise<FullPreviewData> {
  const response = await fetch(
    `${API_BASE_URL}/api/preview-full/${taskId}/${language}`
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || "Failed to get translated preview");
  }

  return response.json();
}
