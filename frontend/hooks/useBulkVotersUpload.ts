"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import {
  initBulkVoterUpload,
  addBulkVoterFiles,
  startBulkVoterProcessing,
  getBulkVoterStatus,
  downloadBulkVoters,
  type BulkVoterSummary,
} from "@/lib/api";

type BulkStatus =
  | "idle"
  | "uploading"
  | "processing"
  | "completed"
  | "error";

const POLL_INTERVAL_MS = 2000;
const UPLOAD_BATCH_SIZE = 15;

interface BulkUploadState {
  status: BulkStatus;
  jobId: string | null;
  totalFiles: number;
  uploadedFiles: number;
  completedPdfs: number;
  totalVoters: number;
  currentFile: string;
  failedCount: number;
  error: string | null;
  summary: BulkVoterSummary | null;
}

const initialState: BulkUploadState = {
  status: "idle",
  jobId: null,
  totalFiles: 0,
  uploadedFiles: 0,
  completedPdfs: 0,
  totalVoters: 0,
  currentFile: "",
  failedCount: 0,
  error: null,
  summary: null,
};

export function useBulkVotersUpload() {
  const [state, setState] = useState<BulkUploadState>(initialState);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const jobIdRef = useRef<string | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  const reset = useCallback(() => {
    stopPolling();
    jobIdRef.current = null;
    setState(initialState);
  }, [stopPolling]);

  const startBulkUpload = useCallback(
    async (files: File[]) => {
      if (files.length === 0) return;

      setState((s) => ({
        ...s,
        status: "uploading",
        totalFiles: files.length,
        uploadedFiles: 0,
        error: null,
        summary: null,
      }));

      try {
        // Phase 1: Init
        const { job_id } = await initBulkVoterUpload();
        jobIdRef.current = job_id;
        setState((s) => ({ ...s, jobId: job_id }));

        // Phase 2: Upload in batches
        let uploaded = 0;
        for (let i = 0; i < files.length; i += UPLOAD_BATCH_SIZE) {
          const batch = files.slice(i, i + UPLOAD_BATCH_SIZE);
          await addBulkVoterFiles(job_id, batch);
          uploaded += batch.length;
          setState((s) => ({ ...s, uploadedFiles: uploaded }));
        }

        // Phase 3: Start processing
        setState((s) => ({ ...s, status: "processing" }));
        await startBulkVoterProcessing(job_id);

        // Phase 4: Poll for progress
        pollRef.current = setInterval(async () => {
          try {
            const status = await getBulkVoterStatus(job_id);

            setState((s) => ({
              ...s,
              completedPdfs: status.progress.completed_pdfs,
              totalVoters: status.progress.total_voters_so_far,
              currentFile: status.progress.current_file,
              failedCount: status.progress.failed_count,
            }));

            if (status.status === "completed") {
              stopPolling();
              setState((s) => ({
                ...s,
                status: "completed",
                summary: status.summary || null,
              }));
            } else if (status.status === "failed") {
              stopPolling();
              setState((s) => ({
                ...s,
                status: "error",
                error: status.error || "Processing failed",
              }));
            }
          } catch {
            // Network error during polling — keep trying
          }
        }, POLL_INTERVAL_MS);
      } catch (err) {
        stopPolling();
        setState((s) => ({
          ...s,
          status: "error",
          error:
            err instanceof Error
              ? err.message
              : "Bulk upload failed. Please try again.",
        }));
      }
    },
    [stopPolling]
  );

  const downloadResult = useCallback(async () => {
    if (!jobIdRef.current) return;
    try {
      await downloadBulkVoters(jobIdRef.current);
    } catch (err) {
      setState((s) => ({
        ...s,
        error:
          err instanceof Error ? err.message : "Download failed",
      }));
    }
  }, []);

  return {
    ...state,
    startBulkUpload,
    reset,
    downloadResult,
  };
}
