"use client";

import { useState, useCallback, useEffect } from "react";
import { DropZone } from "./DropZone";
import { ProgressBar } from "./ProgressBar";
import { DownloadButton } from "./DownloadButton";
import { SpreadsheetEditor } from "./SpreadsheetEditor";
import { ColumnFilter } from "./ColumnFilter";
import { Button } from "@/components/ui/button";
import { useFileUpload } from "@/hooks/useFileUpload";
import {
  CheckCircle,
  AlertCircle,
  Eye,
  RefreshCcw,
  FileSpreadsheet,
  Columns,
  AlertTriangle,
} from "lucide-react";
import { formatFileSize } from "@/lib/utils";
import { downloadExcel, getPreview, getStatus, getColumns } from "@/lib/api";
import type { PreviewData, ValidationIssues } from "@/types";

export function FileUpload() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [columnFilterOpen, setColumnFilterOpen] = useState(false);
  const [columns, setColumns] = useState<string[]>([]);
  const [validationIssues, setValidationIssues] = useState<ValidationIssues | null>(null);

  const {
    status,
    progress,
    message,
    taskId,
    error,
    filename,
    uploadFile,
    reset,
  } = useFileUpload();

  const handleFileSelect = useCallback(
    (file: File) => {
      setSelectedFile(file);

      // Automatically start upload
      uploadFile(file);
    },
    [uploadFile]
  );

  const handleReset = useCallback(() => {
    setSelectedFile(null);
    setPreviewOpen(false);
    setColumns([]);
    reset();
  }, [reset]);

  const handleDownload = useCallback(async () => {
    if (!taskId || !filename) return;
    await downloadExcel(taskId, filename);
    setPreviewOpen(false);
  }, [taskId, filename]);

  const isProcessing = status === "uploading" || status === "processing";
  const isComplete = status === "completed";
  const isError = status === "error";
  const needsReview = status === "needs_review";

  // Fetch columns directly from Excel file when conversion completes
  useEffect(() => {
    if (isComplete && taskId && columns.length === 0) {
      getColumns(taskId)
        .then((data) => {
          setColumns(data.columns);
        })
        .catch((err) => {
          console.error("Failed to fetch columns:", err);
          // Fallback to preview if columns endpoint fails
          getPreview(taskId)
            .then((data: PreviewData) => {
              setColumns(data.headers);
            })
            .catch((fallbackErr) => {
              console.error("Failed to fetch columns from preview:", fallbackErr);
            });
        });
    }
  }, [isComplete, taskId, columns.length]);

  // Fetch validation issues when needs_review
  useEffect(() => {
    if (needsReview && taskId && !validationIssues) {
      getStatus(taskId)
        .then((status) => {
          if (status.validation_issues) {
            setValidationIssues(status.validation_issues);
          }
        })
        .catch((err) => {
          console.error("Failed to fetch validation issues:", err);
        });
    }
  }, [needsReview, taskId, validationIssues]);

  return (
    <div className="bg-white rounded-xl shadow-lg p-6 md:p-8">
      {/* Idle State - Show DropZone */}
      {status === "idle" && (
        <DropZone
          onFileSelect={handleFileSelect}
          isDisabled={false}
          acceptedFile={selectedFile}
        />
      )}

      {/* Processing State */}
      {isProcessing && (
        <div className="space-y-6">
          <div className="text-center">
            <FileSpreadsheet className="h-12 w-12 text-blue-600 mx-auto mb-4 animate-pulse" />
            <h3 className="text-lg font-semibold text-gray-800">
              Converting: {filename}
            </h3>
            {selectedFile && (
              <p className="text-sm text-gray-500">
                {formatFileSize(selectedFile.size)}
              </p>
            )}
          </div>

          <ProgressBar progress={progress} message={message} />

          <div className="text-center">
            <Button variant="outline" onClick={handleReset}>
              Cancel
            </Button>
          </div>
        </div>
      )}

      {/* Success State */}
      {isComplete && taskId && (
        <div className="space-y-6">
          <div className="text-center">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-green-100 mb-4">
              <CheckCircle className="h-8 w-8 text-green-600" />
            </div>
            <h3 className="text-xl font-semibold text-gray-800">
              Conversion Complete!
            </h3>
            <p className="text-gray-600 mt-1">{filename}</p>
          </div>

          <div className="bg-gray-50 rounded-lg p-4">
            <div className="flex items-center justify-between text-sm text-gray-600">
              <span>Status</span>
              <span className="text-green-600 font-medium">Ready to download</span>
            </div>
          </div>

          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Button
              variant="outline"
              onClick={() => setPreviewOpen(true)}
              className="gap-2"
            >
              <Eye className="h-4 w-4" />
              Preview Data
            </Button>

            <Button
              variant="outline"
              onClick={() => setColumnFilterOpen(true)}
              className="gap-2"
            >
              <Columns className="h-4 w-4" />
              Filter Columns
            </Button>

            <DownloadButton taskId={taskId} filename={filename || "data.pdf"} />
          </div>

          <div className="text-center">
            <Button
              variant="ghost"
              onClick={handleReset}
              className="gap-2 text-gray-600"
            >
              <RefreshCcw className="h-4 w-4" />
              Convert Another File
            </Button>
          </div>
        </div>
      )}

      {/* Needs Review State */}
      {needsReview && (
        <div className="space-y-6">
          <div className="text-center">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-yellow-100 mb-4">
              <AlertTriangle className="h-8 w-8 text-yellow-600" />
            </div>
            <h3 className="text-xl font-semibold text-gray-800">
              Validation Warning
            </h3>
            <p className="text-gray-600 mt-2">{message}</p>
            {validationIssues && (
              <p className="text-sm text-gray-500 mt-1">
                Confidence: {(validationIssues.confidence * 100).toFixed(1)}%
              </p>
            )}
          </div>

          {validationIssues && (
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 space-y-4">
              {validationIssues.issues.length > 0 && (
                <div>
                  <h4 className="font-semibold text-yellow-800 mb-2">
                    Issues Found ({validationIssues.issues.length}):
                  </h4>
                  <ul className="list-disc list-inside space-y-1 text-sm text-yellow-700">
                    {validationIssues.issues.slice(0, 5).map((issue, idx) => (
                      <li key={idx}>{issue}</li>
                    ))}
                    {validationIssues.issues.length > 5 && (
                      <li className="text-yellow-600">
                        ... and {validationIssues.issues.length - 5} more
                      </li>
                    )}
                  </ul>
                </div>
              )}

              {validationIssues.warnings.length > 0 && (
                <div>
                  <h4 className="font-semibold text-yellow-800 mb-2">
                    Warnings ({validationIssues.warnings.length}):
                  </h4>
                  <ul className="list-disc list-inside space-y-1 text-sm text-yellow-700">
                    {validationIssues.warnings.slice(0, 3).map((warning, idx) => (
                      <li key={idx}>{warning}</li>
                    ))}
                    {validationIssues.warnings.length > 3 && (
                      <li className="text-yellow-600">
                        ... and {validationIssues.warnings.length - 3} more
                      </li>
                    )}
                  </ul>
                </div>
              )}

              {validationIssues.suggestions.length > 0 && (
                <div>
                  <h4 className="font-semibold text-yellow-800 mb-2">
                    Suggestions:
                  </h4>
                  <ul className="list-disc list-inside space-y-1 text-sm text-yellow-700">
                    {validationIssues.suggestions.map((suggestion, idx) => (
                      <li key={idx}>{suggestion}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          <div className="flex justify-center gap-3">
            <Button onClick={handleReset} className="gap-2">
              <RefreshCcw className="h-4 w-4" />
              Try Again
            </Button>
          </div>

          <div className="text-center text-sm text-gray-500">
            <p>
              The extraction completed but validation found issues. Please review
              the PDF and try again, or contact support if the issues persist.
            </p>
          </div>
        </div>
      )}

      {/* Error State */}
      {isError && (
        <div className="space-y-6">
          <div className="text-center">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-red-100 mb-4">
              <AlertCircle className="h-8 w-8 text-red-600" />
            </div>
            <h3 className="text-xl font-semibold text-gray-800">
              Conversion Failed
            </h3>
            <p className="text-red-600 mt-2">{error || message}</p>
          </div>

          <div className="flex justify-center gap-3">
            <Button onClick={handleReset} className="gap-2">
              <RefreshCcw className="h-4 w-4" />
              Try Again
            </Button>
          </div>
        </div>
      )}

      {/* Spreadsheet Editor Modal */}
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

      {/* Column Filter Modal */}
      {taskId && columns.length > 0 && (
        <ColumnFilter
          isOpen={columnFilterOpen}
          onClose={() => setColumnFilterOpen(false)}
          taskId={taskId}
          columns={columns}
          filename={filename || "data.pdf"}
        />
      )}
    </div>
  );
}
