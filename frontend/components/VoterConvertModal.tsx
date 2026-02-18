"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { useDropzone, FileRejection } from "react-dropzone";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Upload, FileText, AlertCircle, CheckCircle2, X } from "lucide-react";
import { cn, formatFileSize, isValidPdfFile } from "@/lib/utils";
import {
  startVoterConvert,
  getVoterConvertStatus,
  downloadVoterConvert,
  VoterConvertStatus,
} from "@/lib/api";

interface VoterConvertModalProps {
  isOpen: boolean;
  onClose: () => void;
}

type ConvertState = "idle" | "uploading" | "processing" | "success" | "error";

const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB
const POLL_INTERVAL_MS = 2000;

export function VoterConvertModal({ isOpen, onClose }: VoterConvertModalProps) {
  const [file, setFile] = useState<File | null>(null);
  const [state, setState] = useState<ConvertState>("idle");
  const [errorMessage, setErrorMessage] = useState("");
  const [progress, setProgress] = useState<VoterConvertStatus["progress"]>({
    current_page: 0,
    total_pages: 0,
  });
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const jobIdRef = useRef<string | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const handleReset = useCallback(() => {
    stopPolling();
    jobIdRef.current = null;
    setFile(null);
    setState("idle");
    setErrorMessage("");
    setProgress({ current_page: 0, total_pages: 0 });
  }, [stopPolling]);

  const handleClose = useCallback(() => {
    handleReset();
    onClose();
  }, [handleReset, onClose]);

  // Cleanup on unmount
  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  const onDrop = useCallback(
    (acceptedFiles: File[], rejectedFiles: FileRejection[]) => {
      if (acceptedFiles.length > 0) {
        const f = acceptedFiles[0];
        if (isValidPdfFile(f)) {
          setFile(f);
          setErrorMessage("");
          setState("idle");
          return;
        }
      }
      if (rejectedFiles.length > 0) {
        const f = rejectedFiles[0].file;
        if (isValidPdfFile(f) && f.size <= MAX_FILE_SIZE) {
          setFile(f);
          setErrorMessage("");
          setState("idle");
          return;
        }
        const code = rejectedFiles[0].errors[0]?.code;
        if (code === "file-too-large") {
          setErrorMessage("File is too large. Maximum size is 50MB.");
        } else {
          setErrorMessage("Only PDF files are accepted.");
        }
      }
    },
    []
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
      "application/octet-stream": [".pdf"],
    },
    maxFiles: 1,
    maxSize: MAX_FILE_SIZE,
    disabled: state === "uploading" || state === "processing",
  });

  const handleConvert = useCallback(async () => {
    if (!file) return;

    setState("uploading");
    setErrorMessage("");
    setProgress({ current_page: 0, total_pages: 0 });

    try {
      const { job_id } = await startVoterConvert(file);
      jobIdRef.current = job_id;
      setState("processing");

      // Start polling
      pollRef.current = setInterval(async () => {
        try {
          const status = await getVoterConvertStatus(job_id);
          setProgress(status.progress);

          if (status.status === "completed") {
            stopPolling();
            setState("success");

            // Auto-download
            try {
              await downloadVoterConvert(job_id, file.name);
            } catch {
              // Download failed but conversion succeeded
            }

            setTimeout(() => handleClose(), 1500);
          } else if (status.status === "failed") {
            stopPolling();
            setState("error");
            setErrorMessage(status.error || "Conversion failed. Please try again.");
          }
        } catch {
          // Network error during polling - keep trying
        }
      }, POLL_INTERVAL_MS);
    } catch (err) {
      setState("error");
      setErrorMessage(
        err instanceof Error ? err.message : "Conversion failed. Please try again."
      );
    }
  }, [file, handleClose, stopPolling]);

  const handleRemoveFile = useCallback(() => {
    setFile(null);
    setState("idle");
    setErrorMessage("");
  }, []);

  const isWorking = state === "uploading" || state === "processing";
  const progressPercent =
    progress.total_pages > 0
      ? Math.round((progress.current_page / progress.total_pages) * 100)
      : 0;

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && handleClose()}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Convert Voter PDF to Excel</DialogTitle>
          <DialogDescription>
            Upload an Indian electoral roll PDF to extract voter data into Excel format.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 pt-2">
          {/* Drop Zone */}
          {!file ? (
            <div
              {...getRootProps()}
              className={cn(
                "border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all duration-200",
                isDragActive
                  ? "border-blue-500 bg-blue-50"
                  : "border-gray-300 hover:border-gray-400 hover:bg-gray-50",
                isWorking && "opacity-50 cursor-not-allowed"
              )}
            >
              <input {...getInputProps()} />
              <Upload
                className={cn(
                  "h-10 w-10 mx-auto mb-3",
                  isDragActive ? "text-blue-600" : "text-gray-400"
                )}
              />
              <p className="font-medium text-gray-700">
                {isDragActive ? "Drop your PDF here" : "Drag and drop your PDF here"}
              </p>
              <p className="text-sm text-gray-500 mt-1">or click to browse (max 50MB)</p>
            </div>
          ) : (
            /* Selected File Preview */
            <div className="flex items-center gap-3 bg-gray-50 rounded-lg p-4 border border-gray-200">
              <FileText className="h-8 w-8 text-blue-600 flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="font-medium text-gray-900 truncate">{file.name}</p>
                <p className="text-sm text-gray-500">{formatFileSize(file.size)}</p>
              </div>
              {!isWorking && (
                <button
                  onClick={handleRemoveFile}
                  className="p-1 rounded hover:bg-gray-200 text-gray-400 hover:text-gray-600 transition-colors"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>
          )}

          {/* Progress Bar */}
          {isWorking && (
            <div className="space-y-2">
              <div className="flex justify-between text-sm text-gray-600">
                <span>
                  {state === "uploading"
                    ? "Uploading..."
                    : progress.total_pages > 0
                      ? `Processing page ${progress.current_page} of ${progress.total_pages}...`
                      : "Starting conversion..."}
                </span>
                {progress.total_pages > 0 && (
                  <span className="font-medium">{progressPercent}%</span>
                )}
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2.5 overflow-hidden">
                <div
                  className="bg-blue-600 h-2.5 rounded-full transition-all duration-500 ease-out"
                  style={{
                    width: state === "uploading"
                      ? "10%"
                      : progress.total_pages > 0
                        ? `${progressPercent}%`
                        : "15%",
                  }}
                />
              </div>
            </div>
          )}

          {/* Error Message */}
          {errorMessage && (
            <div className="flex items-start gap-2 text-red-600 text-sm bg-red-50 border border-red-200 rounded-lg p-3">
              <AlertCircle className="h-4 w-4 flex-shrink-0 mt-0.5" />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Success Message */}
          {state === "success" && (
            <div className="flex items-center gap-2 text-green-700 text-sm bg-green-50 border border-green-200 rounded-lg p-3">
              <CheckCircle2 className="h-4 w-4 flex-shrink-0" />
              <span>Conversion complete! Your download should start automatically.</span>
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex gap-3 pt-2">
            <Button variant="outline" onClick={handleClose} className="flex-1" disabled={isWorking}>
              Cancel
            </Button>
            <Button
              onClick={handleConvert}
              className="flex-1"
              disabled={!file || isWorking || state === "success"}
            >
              {isWorking ? (
                <span className="flex items-center gap-2">
                  <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Converting...
                </span>
              ) : (
                "Convert & Download"
              )}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
