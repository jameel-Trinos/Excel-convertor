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
import {
  startTranslation,
  subscribeToTranslateProgress,
  downloadTranslatedExcel,
  getTranslateStatus,
} from "@/lib/translation-api";
import type { PreviewData, ValidationIssues, TranslateProgressEvent } from "@/types";
import { Languages, Loader2 } from "lucide-react";

export function FileUpload() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [columnFilterOpen, setColumnFilterOpen] = useState(false);
  const [columns, setColumns] = useState<string[]>([]);
  const [validationIssues, setValidationIssues] = useState<ValidationIssues | null>(null);
  
  // Translation state
  const [translatingTamil, setTranslatingTamil] = useState(false);
  const [translatingHindi, setTranslatingHindi] = useState(false);
  const [tamilProgress, setTamilProgress] = useState(0);
  const [hindiProgress, setHindiProgress] = useState(0);
  const [tamilProgressMessage, setTamilProgressMessage] = useState("");
  const [hindiProgressMessage, setHindiProgressMessage] = useState("");
  const [tamilTaskId, setTamilTaskId] = useState<string | null>(null);
  const [hindiTaskId, setHindiTaskId] = useState<string | null>(null);
  const [availableTranslations, setAvailableTranslations] = useState({
    tamil: false,
    hindi: false,
  });

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

  // Check available translations when conversion completes
  useEffect(() => {
    if (isComplete && taskId) {
      getTranslateStatus(taskId)
        .then((status) => {
          setAvailableTranslations({
            tamil: status.has_tamil_version,
            hindi: status.has_hindi_version,
          });
        })
        .catch((err) => {
          console.error("Failed to get translation status:", err);
        });
    }
  }, [isComplete, taskId]);

  const handleTranslate = useCallback(
    async (targetLang: "tamil" | "hindi") => {
      if (!taskId || translatingTamil || translatingHindi) return;

      const setTranslating = targetLang === "tamil" ? setTranslatingTamil : setTranslatingHindi;
      const setProgress = targetLang === "tamil" ? setTamilProgress : setHindiProgress;
      const setProgressMessage =
        targetLang === "tamil" ? setTamilProgressMessage : setHindiProgressMessage;
      const setTaskId = targetLang === "tamil" ? setTamilTaskId : setHindiTaskId;

      setTranslating(true);
      setProgress(0);
      setProgressMessage("Starting translation...");

      try {
        const response = await startTranslation(taskId, targetLang);

        // Check if it's a cached response
        if (response.translate_task_id.startsWith("cached_")) {
          setTranslating(false);
          setAvailableTranslations((prev) => ({ ...prev, [targetLang]: true }));
          setTaskId(response.translate_task_id);
          return;
        }

        setTaskId(response.translate_task_id);

        // Subscribe to progress
        const unsubscribe = subscribeToTranslateProgress(
          response.translate_task_id,
          (event: TranslateProgressEvent) => {
            const progressPercent =
              event.total > 0 ? (event.current / event.total) * 100 : 0;
            setProgress(progressPercent);
            setProgressMessage(event.message);
          },
          () => {
            // Complete
            setTranslating(false);
            setAvailableTranslations((prev) => ({ ...prev, [targetLang]: true }));
            setTaskId(null);
          },
          (err: Error) => {
            // Error
            console.error("Translation failed:", err);
            setProgressMessage(`Error: ${err.message}`);
            setTranslating(false);
            setTaskId(null);
          }
        );

        // Store unsubscribe function (cleanup on unmount)
        return () => unsubscribe();
      } catch (err) {
        console.error("Failed to start translation:", err);
        setProgressMessage(
          err instanceof Error ? err.message : "Translation failed"
        );
        setTranslating(false);
        setTaskId(null);
      }
    },
    [taskId, translatingTamil, translatingHindi]
  );

  const handleDownloadTranslated = useCallback(
    async (language: "tamil" | "hindi") => {
      if (!taskId || !filename) return;
      try {
        await downloadTranslatedExcel(taskId, language, filename);
      } catch (error) {
        console.error(`Failed to download ${language} translation:`, error);
      }
    },
    [taskId, filename]
  );

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

          {/* Translation Buttons */}
          <div className="border-t border-gray-200 pt-4 mt-4">
            <div className="text-center mb-3">
              <p className="text-sm font-medium text-gray-700">Translate to:</p>
            </div>
            <div className="flex flex-col sm:flex-row gap-3 justify-center">
              {/* Tamil Translation Button */}
              <div className="flex flex-col gap-2">
                {availableTranslations.tamil && !translatingTamil ? (
                  <Button
                    variant="outline"
                    onClick={() => handleDownloadTranslated("tamil")}
                    className="gap-2"
                  >
                    <Languages className="h-4 w-4" />
                    Download Tamil (தமிழ்)
                  </Button>
                ) : (
                  <Button
                    variant="outline"
                    onClick={() => handleTranslate("tamil")}
                    disabled={translatingTamil || translatingHindi}
                    className="gap-2"
                  >
                    {translatingTamil ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Translating... {Math.round(tamilProgress)}%
                      </>
                    ) : (
                      <>
                        <Languages className="h-4 w-4" />
                        Translate to Tamil (தமிழ்)
                      </>
                    )}
                  </Button>
                )}
                {translatingTamil && tamilProgressMessage && (
                  <p className="text-xs text-gray-500 text-center">
                    {tamilProgressMessage}
                  </p>
                )}
              </div>

              {/* Hindi Translation Button */}
              <div className="flex flex-col gap-2">
                {availableTranslations.hindi && !translatingHindi ? (
                  <Button
                    variant="outline"
                    onClick={() => handleDownloadTranslated("hindi")}
                    className="gap-2"
                  >
                    <Languages className="h-4 w-4" />
                    Download Hindi (हिंदी)
                  </Button>
                ) : (
                  <Button
                    variant="outline"
                    onClick={() => handleTranslate("hindi")}
                    disabled={translatingTamil || translatingHindi}
                    className="gap-2"
                  >
                    {translatingHindi ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Translating... {Math.round(hindiProgress)}%
                      </>
                    ) : (
                      <>
                        <Languages className="h-4 w-4" />
                        Translate to Hindi (हिंदी)
                      </>
                    )}
                  </Button>
                )}
                {translatingHindi && hindiProgressMessage && (
                  <p className="text-xs text-gray-500 text-center">
                    {hindiProgressMessage}
                  </p>
                )}
              </div>
            </div>
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
