"use client";

import { useState, useCallback, useRef } from "react";
import { uploadVotersPdf, subscribeToProgress, getStatus } from "@/lib/api";
import type { UploadState, ProgressEvent } from "@/types";

const initialState: UploadState = {
  status: "idle",
  progress: 0,
  message: "",
};

export function useVotersUpload() {
  const [state, setState] = useState<UploadState>(initialState);
  const unsubscribeRef = useRef<(() => void) | null>(null);

  const uploadFile = useCallback(async (file: File) => {
    // Cleanup any existing subscription
    if (unsubscribeRef.current) {
      unsubscribeRef.current();
      unsubscribeRef.current = null;
    }

    setState({
      status: "uploading",
      progress: 0,
      message: "Uploading file...",
      filename: file.name,
      fileSize: file.size,
    });

    try {
      // Upload the file to voters endpoint
      const { task_id, filename } = await uploadVotersPdf(file);

      setState((prev) => ({
        ...prev,
        status: "processing",
        progress: 5,
        message: "Starting voters data extraction...",
        taskId: task_id,
        filename,
      }));

      // Subscribe to progress updates
      unsubscribeRef.current = subscribeToProgress(
        task_id,
        // On progress
        (event: ProgressEvent) => {
          setState((prev) => ({
            ...prev,
            progress: event.progress,
            message: event.message,
            status:
              event.status === "failed"
                ? "error"
                : event.status === "needs_review"
                  ? "needs_review"
                  : event.status === "completed"
                    ? "completed"
                    : "processing",
          }));
        },
        // On complete
        () => {
          setState((prev) => ({
            ...prev,
            status: "completed",
            progress: 100,
            message: "Voters data extraction completed successfully!",
          }));
        },
        // On error
        (error: Error) => {
          setState((prev) => ({
            ...prev,
            status: "error",
            error: error.message,
            message: `Error: ${error.message}`,
          }));
        }
      );
    } catch (error) {
      setState((prev) => ({
        ...prev,
        status: "error",
        error: error instanceof Error ? error.message : "Upload failed",
        message:
          error instanceof Error ? `Error: ${error.message}` : "Upload failed",
      }));
    }
  }, []);

  const reset = useCallback(() => {
    // Cleanup subscription
    if (unsubscribeRef.current) {
      unsubscribeRef.current();
      unsubscribeRef.current = null;
    }
    setState(initialState);
  }, []);

  const checkStatus = useCallback(async () => {
    if (!state.taskId) return;

    try {
      const status = await getStatus(state.taskId);
      setState((prev) => ({
        ...prev,
        progress: status.progress,
        message: status.message,
        status:
          status.status === "completed"
            ? "completed"
            : status.status === "failed"
              ? "error"
              : status.status === "needs_review"
                ? "needs_review"
                : "processing",
        error: status.error || undefined,
      }));
    } catch (error) {
      console.error("Failed to check status:", error);
    }
  }, [state.taskId]);

  return {
    ...state,
    uploadFile,
    reset,
    checkStatus,
  };
}
