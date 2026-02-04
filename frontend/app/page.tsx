"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { useDropzone, FileRejection } from "react-dropzone";
import { SpreadsheetEditor } from "@/components/SpreadsheetEditor";
import { ColumnFilter } from "@/components/ColumnFilter";
import { NavigationMenu, type MenuItem } from "@/components/NavigationMenu";
import { useFileUpload } from "@/hooks/useFileUpload";
import { formatFileSize, isValidPdfFile } from "@/lib/utils";
import { downloadExcel, getPreview, getStatus, getColumns, uploadBoothPdf } from "@/lib/api";
import type { PreviewData, ValidationIssues } from "@/types";

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

export default function Home() {
  const [currentView, setCurrentView] = useState<MenuItem>("election-results");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [columnFilterOpen, setColumnFilterOpen] = useState(false);
  const [columns, setColumns] = useState<string[]>([]);
  const [validationIssues, setValidationIssues] = useState<ValidationIssues | null>(null);
  const [previewData, setPreviewData] = useState<PreviewData | null>(null);

  // Separate state for booth view
  const [boothState, setBoothState] = useState({
    status: "idle" as "idle" | "uploading" | "processing" | "completed" | "error" | "needs_review",
    progress: 0,
    message: "",
    taskId: null as string | null,
    error: null as string | null,
    filename: null as string | null,
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

  const handleBoothFileSelect = useCallback(async (file: File) => {
    setBoothState({
      status: "uploading",
      progress: 0,
      message: "Uploading file...",
      taskId: null,
      error: null,
      filename: file.name,
    });

    try {
      const { task_id, filename: uploadedFilename } = await uploadBoothPdf(file);
      
      setBoothState((prev) => ({
        ...prev,
        status: "processing",
        progress: 5,
        message: "Starting booth conversion...",
        taskId: task_id,
        filename: uploadedFilename,
      }));

      // Subscribe to progress updates
      const { subscribeToProgress } = await import("@/lib/api");
      const unsubscribe = subscribeToProgress(
        task_id,
        (event) => {
          setBoothState((prev) => ({
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
        () => {
          setBoothState((prev) => ({
            ...prev,
            status: "completed",
            progress: 100,
            message: "Booth conversion completed successfully!",
          }));
        },
        (error: Error) => {
          setBoothState((prev) => ({
            ...prev,
            status: "error",
            error: error.message,
            message: `Error: ${error.message}`,
          }));
        }
      );

      // Store unsubscribe function for cleanup
      // Note: In a production app, you'd want to store this and call it on unmount/reset
    } catch (error) {
      setBoothState((prev) => ({
        ...prev,
        status: "error",
        error: error instanceof Error ? error.message : "Upload failed",
        message: error instanceof Error ? `Error: ${error.message}` : "Upload failed",
      }));
    }
  }, []);

  const handleFileSelect = useCallback(
    (file: File) => {
      setSelectedFile(file);
      if (currentView === "constituency") {
        handleBoothFileSelect(file);
      } else {
        uploadFile(file);
      }
    },
    [uploadFile, currentView, handleBoothFileSelect]
  );

  const handleReset = useCallback(() => {
    setSelectedFile(null);
    setPreviewOpen(false);
    setColumnFilterOpen(false);
    setColumns([]);
    setValidationIssues(null);
    setPreviewData(null);
    if (currentView === "constituency") {
      setBoothState({
        status: "idle",
        progress: 0,
        message: "",
        taskId: null,
        error: null,
        filename: null,
      });
    } else {
      reset();
    }
  }, [reset, currentView]);

  const handleDownload = useCallback(async () => {
    const activeTaskId = currentView === "constituency" ? boothState.taskId : taskId;
    const activeFilename = currentView === "constituency" ? boothState.filename : filename;
    if (!activeTaskId || !activeFilename) return;
    await downloadExcel(activeTaskId, activeFilename);
  }, [taskId, filename, boothState.taskId, boothState.filename, currentView]);

  const isIdle = status === "idle";
  const isProcessing = status === "uploading" || status === "processing";
  const isComplete = status === "completed";
  const isError = status === "error";
  const needsReview = status === "needs_review";

  // Reset all shared state when switching between menu options
  useEffect(() => {
    // Reset shared state to prevent interference between different menu options
    setSelectedFile(null);
    setPreviewOpen(false);
    setColumnFilterOpen(false);
    setColumns([]);
    setValidationIssues(null);
    setPreviewData(null);
    
    // Reset view-specific states
    if (currentView === "constituency") {
      // Reset booth state
      setBoothState({
        status: "idle",
        progress: 0,
        message: "",
        taskId: null,
        error: null,
        filename: null,
      });
    } else if (currentView === "election-results") {
      // Reset election results state
      reset();
    }
    // Note: booth and voters views don't have state yet, but this ensures clean state
  }, [currentView, reset]);

  // Fetch columns and preview when conversion completes
  useEffect(() => {
    const activeTaskId = currentView === "constituency" ? boothState.taskId : taskId;
    const isActiveComplete = currentView === "constituency" 
      ? boothState.status === "completed" 
      : isComplete;

    if (isActiveComplete && activeTaskId && columns.length === 0) {
      getColumns(activeTaskId)
        .then((data) => {
          setColumns(data.columns);
        })
        .catch((err) => {
          console.error("Failed to fetch columns:", err);
          getPreview(activeTaskId)
            .then((data: PreviewData) => {
              setColumns(data.headers);
              setPreviewData(data);
            })
            .catch((fallbackErr) => {
              console.error("Failed to fetch columns from preview:", fallbackErr);
            });
        });

      // Also fetch preview data for stats
      getPreview(activeTaskId)
        .then((data) => {
          setPreviewData(data);
        })
        .catch(console.error);
    }
  }, [isComplete, taskId, boothState.status, boothState.taskId, currentView, columns.length]);

  // Fetch validation issues when needs_review
  useEffect(() => {
    const activeTaskId = currentView === "constituency" ? boothState.taskId : taskId;
    const isActiveNeedsReview = currentView === "constituency"
      ? boothState.status === "needs_review"
      : needsReview;

    if (isActiveNeedsReview && activeTaskId && !validationIssues) {
      getStatus(activeTaskId)
        .then((status) => {
          if (status.validation_issues) {
            setValidationIssues(status.validation_issues);
          }
        })
        .catch((err) => {
          console.error("Failed to fetch validation issues:", err);
        });
    }
  }, [needsReview, taskId, boothState.status, boothState.taskId, currentView, validationIssues]);

  const getMenuLabel = (view: MenuItem): string => {
    const labels: Record<MenuItem, string> = {
      "election-results": "Election results",
      "constituency": "Booth",
      "booth": "Constituency",
      "voters": "Voters",
    };
    return labels[view];
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-50 to-gray-100">
      {/* Navigation Sidebar */}
      <NavigationMenu 
        currentView={currentView} 
        onViewChange={setCurrentView}
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
      />

      {/* Header */}
      <Header onMenuToggle={() => setSidebarOpen(!sidebarOpen)} />

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 md:py-12">
        {/* Menu Name Display */}
        <div className="mb-6">
          <h2 className="text-3xl font-bold text-gray-900">{getMenuLabel(currentView)}</h2>
        </div>
        {/* Content based on current view */}
        {currentView === "election-results" && (
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

            {/* How It Works Section */}
            <HowItWorksSection />
          </>
        )}

        {currentView === "constituency" && (
          <>
            {/* File Upload Area */}
            <div className="mb-12">
              {boothState.status === "idle" && (
                <IdleState onFileSelect={handleFileSelect} />
              )}

              {boothState.status === "uploading" || boothState.status === "processing" ? (
                <ProcessingState
                  filename={boothState.filename || selectedFile?.name || ""}
                  fileSize={selectedFile?.size || 0}
                  progress={boothState.progress}
                  message={boothState.message}
                  onCancel={handleReset}
                />
              ) : null}

              {boothState.status === "completed" && boothState.taskId && (
                <CompletedState
                  filename={boothState.filename || ""}
                  previewData={previewData}
                  onPreview={() => setPreviewOpen(true)}
                  onFilter={() => setColumnFilterOpen(true)}
                  onDownload={handleDownload}
                  onReset={handleReset}
                />
              )}

              {boothState.status === "needs_review" && (
                <NeedsReviewState
                  validationIssues={validationIssues}
                  onReview={() => setPreviewOpen(true)}
                  onReset={handleReset}
                />
              )}

              {boothState.status === "error" && (
                <ErrorState
                  error={boothState.error || boothState.message}
                  onReset={handleReset}
                />
              )}
            </div>

            {/* Features Section */}
            <FeaturesSection />
          </>
        )}

        {currentView === "booth" && (
          <PlaceholderView title="Booth" description="Booth functionality will be developed here." />
        )}

        {currentView === "voters" && (
          <PlaceholderView title="Voters" description="Voters functionality will be developed here." />
        )}
      </main>

      {/* Footer */}
      <Footer />

      {/* Modals */}
      {(taskId || boothState.taskId) && (
        <SpreadsheetEditor
          isOpen={previewOpen}
          onClose={() => setPreviewOpen(false)}
          taskId={taskId || boothState.taskId || ""}
          filename={filename || boothState.filename || "data.pdf"}
          onFilterColumns={() => {
            setPreviewOpen(false);
            setColumnFilterOpen(true);
          }}
        />
      )}

      {(taskId || boothState.taskId) && columns.length > 0 && (
        <ColumnFilter
          isOpen={columnFilterOpen}
          onClose={() => setColumnFilterOpen(false)}
          taskId={taskId || boothState.taskId || ""}
          columns={columns}
          filename={filename || boothState.filename || "data.pdf"}
        />
      )}
    </div>
  );
}

// Header Component
function Header({ onMenuToggle }: { onMenuToggle: () => void }) {
  return (
    <header className="bg-white shadow-sm border-b border-gray-200 sticky top-0 z-30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {/* Menu Toggle Button */}
            <button
              onClick={onMenuToggle}
              className="p-2 rounded-lg hover:bg-gray-100 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500"
              aria-label="Toggle menu"
            >
              <svg
                className="w-6 h-6 text-gray-700"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 6h16M4 12h16M4 18h16"
                />
              </svg>
            </button>
            <div className="w-10 h-10 bg-blue-600 rounded-lg flex items-center justify-center">
              <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
              </svg>
            </div>
            <div>
              <h1 className="text-xl font-bold text-gray-900">PDF to Excel Converter</h1>
              <p className="text-sm text-gray-500">Convert election results in seconds</p>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}

// Placeholder View Component for future functionality
function PlaceholderView({ title, description }: { title: string; description: string }) {
  return (
    <div className="bg-white rounded-xl shadow-lg border border-gray-200 p-12 text-center">
      <div className="w-20 h-20 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-6">
        <svg className="w-10 h-10 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      </div>
      <h3 className="text-2xl font-bold text-gray-900 mb-3">{title}</h3>
      <p className="text-gray-600 max-w-md mx-auto">{description}</p>
    </div>
  );
}

// Idle State - Drop Zone
function IdleState({ onFileSelect }: { onFileSelect: (file: File) => void }) {
  const onDrop = useCallback(
    (acceptedFiles: File[], rejectedFiles: FileRejection[]) => {
      if (rejectedFiles.length > 0) {
        return;
      }
      if (acceptedFiles.length > 0) {
        const file = acceptedFiles[0];
        if (isValidPdfFile(file)) {
          onFileSelect(file);
        }
      }
    },
    [onFileSelect]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "application/pdf": [".pdf"] },
    maxFiles: 1,
    maxSize: MAX_FILE_SIZE,
  });

  return (
    <div
      {...getRootProps()}
      className={`bg-white rounded-xl shadow-lg border-2 border-dashed p-8 md:p-12 text-center cursor-pointer transition-all ${
        isDragActive
          ? "border-blue-500 bg-blue-50"
          : "border-gray-300 hover:border-blue-400"
      }`}
    >
      <input {...getInputProps()} />

      <div className="w-20 h-20 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-6 animate-bounce-slow">
        <svg className="w-10 h-10 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
        </svg>
      </div>

      <h3 className="text-2xl font-bold text-gray-900 mb-2">
        {isDragActive ? "Drop your PDF here" : "Drop your PDF here"}
      </h3>
      <p className="text-gray-600 mb-6">or click to browse files</p>

      <div className="inline-flex items-center gap-2 text-sm text-gray-500 bg-gray-50 px-4 py-2 rounded-lg">
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        PDF files up to 10MB
      </div>
    </div>
  );
}

// Processing State
function ProcessingState({
  filename,
  fileSize,
  progress,
  message,
  onCancel,
}: {
  filename: string;
  fileSize: number;
  progress: number;
  message: string;
  onCancel: () => void;
}) {
  return (
    <div className="bg-white rounded-xl shadow-lg border border-gray-200 p-8">
      <div className="flex items-start gap-4 mb-6">
        <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center flex-shrink-0">
          <svg className="w-6 h-6 text-blue-600 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
        </div>
        <div className="flex-1">
          <h3 className="text-lg font-semibold text-gray-900 mb-1">Processing your file</h3>
          <p className="text-sm text-gray-600">
            {filename} {fileSize > 0 && `(${formatFileSize(fileSize)})`}
          </p>
        </div>
        <button
          onClick={onCancel}
          className="text-gray-400 hover:text-gray-600 p-1 rounded transition-colors"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between text-sm">
          <span className="text-gray-600">{message || "Processing..."}</span>
          <span className="font-semibold text-blue-600">{Math.round(progress)}%</span>
        </div>

        <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
          <div
            className="bg-blue-600 h-2 rounded-full transition-all duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>

        <div className="flex items-center gap-2 text-xs text-gray-500">
          <svg className="w-4 h-4 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          {message || "Processing..."}
        </div>
      </div>
    </div>
  );
}

// Completed State
function CompletedState({
  filename,
  previewData,
  onPreview,
  onFilter,
  onDownload,
  onReset,
}: {
  filename: string;
  previewData: PreviewData | null;
  onPreview: () => void;
  onFilter: () => void;
  onDownload: () => void;
  onReset: () => void;
}) {
  const outputFilename = filename.replace(".pdf", ".xlsx");

  return (
    <div className="bg-white rounded-xl shadow-lg border border-gray-200 p-8">
      <div className="flex items-start gap-4 mb-6">
        <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center flex-shrink-0">
          <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <h3 className="text-lg font-semibold text-gray-900">Conversion Complete!</h3>
            <span className="px-2 py-1 bg-green-100 text-green-700 text-xs font-medium rounded">
              Ready to download
            </span>
          </div>
          <p className="text-sm text-gray-600">{filename} → {outputFilename}</p>
        </div>
      </div>

      {previewData && (
        <div className="bg-gray-50 rounded-lg p-4 mb-6">
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <p className="text-2xl font-bold text-gray-900">{previewData.total_rows}</p>
              <p className="text-xs text-gray-600">Rows extracted</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">{previewData.total_columns}</p>
              <p className="text-xs text-gray-600">Columns found</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-green-600">100%</p>
              <p className="text-xs text-gray-600">Confidence</p>
            </div>
          </div>
        </div>
      )}

      <div className="grid md:grid-cols-3 gap-3 mb-6">
        <button
          onClick={onPreview}
          className="flex items-center justify-center gap-2 px-4 py-3 bg-white border-2 border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 font-medium transition-colors"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
          </svg>
          Preview Data
        </button>

        <button
          onClick={onFilter}
          className="flex items-center justify-center gap-2 px-4 py-3 bg-white border-2 border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 font-medium transition-colors"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
          </svg>
          Edit
        </button>

        <button
          onClick={onDownload}
          className="flex items-center justify-center gap-2 px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium transition-colors"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
          Download Excel
        </button>
      </div>

      <button
        onClick={onReset}
        className="w-full py-2 text-sm text-gray-600 hover:text-gray-900 font-medium transition-colors"
      >
        Convert Another File →
      </button>
    </div>
  );
}

// Needs Review State
function NeedsReviewState({
  validationIssues,
  onReview,
  onReset,
}: {
  validationIssues: ValidationIssues | null;
  onReview: () => void;
  onReset: () => void;
}) {
  return (
    <div className="bg-white rounded-xl shadow-lg border-2 border-yellow-200 p-8">
      <div className="flex items-start gap-4 mb-6">
        <div className="w-12 h-12 bg-yellow-100 rounded-full flex items-center justify-center flex-shrink-0">
          <svg className="w-6 h-6 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>
        <div className="flex-1">
          <h3 className="text-lg font-semibold text-gray-900 mb-1">Review Required</h3>
          <p className="text-sm text-gray-600">
            Extraction completed with{" "}
            <span className="font-semibold text-yellow-700">
              {validationIssues ? `${Math.round(validationIssues.confidence * 100)}%` : "low"} confidence
            </span>
            . Please review the issues below.
          </p>
        </div>
      </div>

      {validationIssues && (
        <div className="space-y-4 mb-6">
          {/* Issues */}
          {validationIssues.issues.length > 0 && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-3">
                <svg className="w-5 h-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span className="font-semibold text-red-900 text-sm">
                  Issues ({validationIssues.issues.length})
                </span>
              </div>
              <ul className="space-y-2 text-sm text-red-800">
                {validationIssues.issues.slice(0, 3).map((issue, idx) => (
                  <li key={idx} className="flex items-start gap-2">
                    <span className="text-red-400 mt-1">•</span>
                    <span>{issue}</span>
                  </li>
                ))}
                {validationIssues.issues.length > 3 && (
                  <li className="text-red-600 ml-4">
                    ... and {validationIssues.issues.length - 3} more
                  </li>
                )}
              </ul>
            </div>
          )}

          {/* Warnings */}
          {validationIssues.warnings.length > 0 && (
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-3">
                <svg className="w-5 h-5 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <span className="font-semibold text-yellow-900 text-sm">
                  Warnings ({validationIssues.warnings.length})
                </span>
              </div>
              <ul className="space-y-2 text-sm text-yellow-800">
                {validationIssues.warnings.slice(0, 2).map((warning, idx) => (
                  <li key={idx} className="flex items-start gap-2">
                    <span className="text-yellow-400 mt-1">•</span>
                    <span>{warning}</span>
                  </li>
                ))}
                {validationIssues.warnings.length > 2 && (
                  <li className="text-yellow-600 ml-4">
                    ... and {validationIssues.warnings.length - 2} more
                  </li>
                )}
              </ul>
            </div>
          )}

          {/* Suggestions */}
          {validationIssues.suggestions.length > 0 && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-3">
                <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
                <span className="font-semibold text-blue-900 text-sm">Suggestions</span>
              </div>
              <ul className="space-y-2 text-sm text-blue-800">
                {validationIssues.suggestions.map((suggestion, idx) => (
                  <li key={idx} className="flex items-start gap-2">
                    <span className="text-blue-400 mt-1">•</span>
                    <span>{suggestion}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      <div className="flex gap-3">
        <button
          onClick={onReview}
          className="flex-1 py-3 px-4 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium transition-colors"
        >
          Review & Edit Data
        </button>
        <button
          onClick={onReset}
          className="px-6 py-3 bg-white border-2 border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 font-medium transition-colors"
        >
          Try Again
        </button>
      </div>
    </div>
  );
}

// Error State
function ErrorState({
  error,
  onReset,
}: {
  error: string;
  onReset: () => void;
}) {
  return (
    <div className="bg-white rounded-xl shadow-lg border-2 border-red-200 p-8">
      <div className="flex items-start gap-4 mb-6">
        <div className="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center flex-shrink-0">
          <svg className="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </div>
        <div className="flex-1">
          <h3 className="text-lg font-semibold text-gray-900 mb-1">Conversion Failed</h3>
          <p className="text-sm text-gray-600">We couldn't process your file. Please try again.</p>
        </div>
      </div>

      <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
        <div className="flex items-start gap-2">
          <svg className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <div className="flex-1">
            <p className="font-semibold text-red-900 text-sm mb-1">Error Details:</p>
            <p className="text-sm text-red-800">{error || "An unknown error occurred."}</p>
          </div>
        </div>
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
        <p className="font-semibold text-blue-900 text-sm mb-2">Troubleshooting tips:</p>
        <ul className="space-y-1 text-sm text-blue-800">
          <li className="flex items-start gap-2">
            <span className="text-blue-400">•</span>
            <span>Ensure the PDF contains tabular data</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-blue-400">•</span>
            <span>Check if the file is password protected</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-blue-400">•</span>
            <span>Try uploading a different PDF file</span>
          </li>
        </ul>
      </div>

      <button
        onClick={onReset}
        className="w-full py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium transition-colors"
      >
        Try Again
      </button>
    </div>
  );
}

// Features Section
function FeaturesSection() {
  return (
    <div className="grid md:grid-cols-3 gap-6 mb-12">
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center mb-4">
          <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
        </div>
        <h3 className="text-lg font-bold text-gray-900 mb-2">Lightning Fast</h3>
        <p className="text-gray-600 text-sm">
          Convert your PDFs to Excel in seconds with our optimized processing engine.
        </p>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center mb-4">
          <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
          </svg>
        </div>
        <h3 className="text-lg font-bold text-gray-900 mb-2">Privacy First</h3>
        <p className="text-gray-600 text-sm">
          Your files are processed securely and deleted immediately after conversion.
        </p>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center mb-4">
          <svg className="w-6 h-6 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <h3 className="text-lg font-bold text-gray-900 mb-2">No Limits</h3>
        <p className="text-gray-600 text-sm">
          Process unlimited files with no restrictions. Perfect for bulk conversions.
        </p>
      </div>
    </div>
  );
}

// How It Works Section
function HowItWorksSection() {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
      <h2 className="text-2xl font-bold text-gray-900 mb-6 text-center">How It Works</h2>
      <div className="grid md:grid-cols-3 gap-8">
        <div className="text-center">
          <div className="w-16 h-16 bg-blue-600 text-white rounded-full flex items-center justify-center text-2xl font-bold mx-auto mb-4">
            1
          </div>
          <h3 className="font-semibold text-gray-900 mb-2">Upload PDF</h3>
          <p className="text-sm text-gray-600">
            Drag and drop your election results PDF or click to browse
          </p>
        </div>
        <div className="text-center">
          <div className="w-16 h-16 bg-blue-600 text-white rounded-full flex items-center justify-center text-2xl font-bold mx-auto mb-4">
            2
          </div>
          <h3 className="font-semibold text-gray-900 mb-2">Auto Convert</h3>
          <p className="text-sm text-gray-600">
            Our AI extracts tables and converts them to Excel format
          </p>
        </div>
        <div className="text-center">
          <div className="w-16 h-16 bg-blue-600 text-white rounded-full flex items-center justify-center text-2xl font-bold mx-auto mb-4">
            3
          </div>
          <h3 className="font-semibold text-gray-900 mb-2">Download</h3>
          <p className="text-sm text-gray-600">
            Preview, filter columns, and download your Excel file
          </p>
        </div>
      </div>
    </div>
  );
}

// Footer
function Footer() {
  return (
    <footer className="bg-white border-t border-gray-200 mt-12">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <p className="text-center text-sm text-gray-600">
          © {new Date().getFullYear()} PDF to Excel Converter. All rights reserved.
        </p>
      </div>
    </footer>
  );
}
