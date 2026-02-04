"use client";

import { useState, useCallback, useEffect } from "react";
import { SpreadsheetEditor } from "@/components/SpreadsheetEditor";
import { ColumnFilter } from "@/components/ColumnFilter";
import { useBoothUpload } from "@/hooks/useBoothUpload";
import { downloadExcel, getPreview, getStatus, getColumns } from "@/lib/api";
import type { PreviewData, ValidationIssues } from "@/types";
import {
  IdleState,
  ProcessingState,
  CompletedState,
  NeedsReviewState,
  ErrorState,
  FeaturesSection,
} from "./shared/StateComponents";

export function BoothView() {
  // Own isolated state
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [columnFilterOpen, setColumnFilterOpen] = useState(false);
  const [columns, setColumns] = useState<string[]>([]);
  const [validationIssues, setValidationIssues] = useState<ValidationIssues | null>(null);
  const [previewData, setPreviewData] = useState<PreviewData | null>(null);

  const {
    status,
    progress,
    message,
    taskId,
    error,
    filename,
    uploadFile,
    reset,
  } = useBoothUpload();

  const handleFileSelect = useCallback(
    (file: File) => {
      setSelectedFile(file);
      uploadFile(file);
    },
    [uploadFile]
  );

  const handleReset = useCallback(() => {
    setSelectedFile(null);
    setPreviewOpen(false);
    setColumnFilterOpen(false);
    setColumns([]);
    setValidationIssues(null);
    setPreviewData(null);
    reset();
  }, [reset]);

  const handleDownload = useCallback(async () => {
    if (!taskId || !filename) return;
    await downloadExcel(taskId, filename);
  }, [taskId, filename]);

  const isIdle = status === "idle";
  const isProcessing = status === "uploading" || status === "processing";
  const isComplete = status === "completed";
  const isError = status === "error";
  const needsReview = status === "needs_review";

  // Fetch columns and preview when conversion completes
  useEffect(() => {
    if (isComplete && taskId && columns.length === 0) {
      getColumns(taskId)
        .then((data) => {
          setColumns(data.columns);
        })
        .catch((err) => {
          console.error("Failed to fetch columns:", err);
          getPreview(taskId)
            .then((data: PreviewData) => {
              setColumns(data.headers);
              setPreviewData(data);
            })
            .catch((fallbackErr) => {
              console.error("Failed to fetch columns from preview:", fallbackErr);
            });
        });

      // Also fetch preview data for stats
      getPreview(taskId)
        .then((data) => {
          setPreviewData(data);
        })
        .catch(console.error);
    }
  }, [isComplete, taskId, columns.length]);

  // Fetch validation issues when needs_review
  useEffect(() => {
    if (needsReview && taskId && !validationIssues) {
      getStatus(taskId)
        .then((statusData) => {
          if (statusData.validation_issues) {
            setValidationIssues(statusData.validation_issues);
          }
        })
        .catch((err) => {
          console.error("Failed to fetch validation issues:", err);
        });
    }
  }, [needsReview, taskId, validationIssues]);

  return (
    <>
      {/* File Upload Area */}
      <div className="mb-12">
        {isIdle && (
          <IdleState onFileSelect={handleFileSelect} />
        )}

        {isProcessing && (
          <ProcessingState
            filename={filename || selectedFile?.name || ""}
            fileSize={selectedFile?.size || 0}
            progress={progress}
            message={message}
            onCancel={handleReset}
          />
        )}

        {isComplete && taskId && (
          <CompletedState
            filename={filename || ""}
            previewData={previewData}
            onPreview={() => setPreviewOpen(true)}
            onFilter={() => setColumnFilterOpen(true)}
            onDownload={handleDownload}
            onReset={handleReset}
          />
        )}

        {needsReview && (
          <NeedsReviewState
            validationIssues={validationIssues}
            onReview={() => setPreviewOpen(true)}
            onReset={handleReset}
          />
        )}

        {isError && (
          <ErrorState
            error={error || message}
            onReset={handleReset}
          />
        )}
      </div>

      {/* Features Section */}
      <FeaturesSection />

      {/* Modals - owned by this view */}
      {taskId && (
        <SpreadsheetEditor
          isOpen={previewOpen}
          onClose={() => setPreviewOpen(false)}
          taskId={taskId}
          filename={filename || "data.pdf"}
          onFilterColumns={() => {
            setPreviewOpen(false);
            setColumnFilterOpen(true);
          }}
        />
      )}

      {taskId && columns.length > 0 && (
        <ColumnFilter
          isOpen={columnFilterOpen}
          onClose={() => setColumnFilterOpen(false)}
          taskId={taskId}
          columns={columns}
          filename={filename || "data.pdf"}
        />
      )}
    </>
  );
}
