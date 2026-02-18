"use client";

import { useCallback } from "react";
import { useDropzone, FileRejection } from "react-dropzone";
import { formatFileSize, isValidPdfFile } from "@/lib/utils";
import type { PreviewData, ValidationIssues } from "@/types";

const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB

// Idle State - Drop Zone
export function IdleState({ onFileSelect }: { onFileSelect: (file: File) => void }) {
  const onDrop = useCallback(
    (acceptedFiles: File[], rejectedFiles: FileRejection[]) => {
      // If dropzone rejected (e.g. wrong MIME), still accept .pdf by name (scanned/OCR PDFs often have octet-stream type)
      if (acceptedFiles.length > 0) {
        const file = acceptedFiles[0];
        if (isValidPdfFile(file)) {
          onFileSelect(file);
          return;
        }
      }
      if (rejectedFiles.length > 0) {
        const file = rejectedFiles[0].file;
        if (isValidPdfFile(file) && file.size <= MAX_FILE_SIZE) {
          onFileSelect(file);
          return;
        }
      }
    },
    [onFileSelect]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
      "application/octet-stream": [".pdf"],
    },
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
        PDF files up to 50MB
      </div>
    </div>
  );
}

// Processing State
export function ProcessingState({
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
export function CompletedState({
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
export function NeedsReviewState({
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
export function ErrorState({
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
export function FeaturesSection() {
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
export function HowItWorksSection() {
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

// Placeholder View Component for future functionality
export function PlaceholderView({ title, description }: { title: string; description: string }) {
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
