"use client";

import { useState, useCallback, useRef } from "react";
import { formatFileSize } from "@/lib/utils";
import { mergeExcelFiles } from "@/lib/api";

type MergeStatus = "idle" | "merging" | "completed" | "error";

interface MergeResult {
  totalRows: number;
  totalFiles: number;
  totalSheets: number;
  blob: Blob;
}

export function ExcelMergeView() {
  const [files, setFiles] = useState<File[]>([]);
  const [status, setStatus] = useState<MergeStatus>("idle");
  const [error, setError] = useState<string>("");
  const [result, setResult] = useState<MergeResult | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFilesSelected = useCallback((newFiles: FileList | null) => {
    if (!newFiles) return;
    const xlsxFiles = Array.from(newFiles).filter((f) =>
      f.name.toLowerCase().endsWith(".xlsx")
    );
    if (xlsxFiles.length === 0) return;
    setFiles((prev) => [...prev, ...xlsxFiles]);
    setStatus("idle");
    setError("");
    setResult(null);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      handleFilesSelected(e.dataTransfer.files);
    },
    [handleFilesSelected]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
  }, []);

  const removeFile = useCallback((index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const handleReset = useCallback(() => {
    setFiles([]);
    setStatus("idle");
    setError("");
    setResult(null);
  }, []);

  const handleMerge = useCallback(async () => {
    if (files.length === 0) return;
    setStatus("merging");
    setError("");

    try {
      const { blob, totalRows, totalFiles, totalSheets } =
        await mergeExcelFiles(files);
      setResult({ blob, totalRows, totalFiles, totalSheets });
      setStatus("completed");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Merge failed";
      setError(msg);
      setStatus("error");
    }
  }, [files]);

  const handleDownload = useCallback(() => {
    if (!result?.blob) return;
    const url = URL.createObjectURL(result.blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "merged_voters.xlsx";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [result]);

  const totalSize = files.reduce((sum, f) => sum + f.size, 0);

  return (
    <>
      {/* Drop zone / file selection */}
      <div className="mb-8">
        <div
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onClick={() => fileInputRef.current?.click()}
          className={`bg-white rounded-xl shadow-lg border-2 border-dashed p-8 md:p-12 text-center cursor-pointer transition-all ${
            status === "merging"
              ? "border-gray-200 opacity-60 pointer-events-none"
              : "border-gray-300 hover:border-green-400"
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".xlsx"
            multiple
            className="hidden"
            onChange={(e) => handleFilesSelected(e.target.files)}
          />

          <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-6">
            <svg
              className="w-10 h-10 text-green-600"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
          </div>

          <h3 className="text-2xl font-bold text-gray-900 mb-2">
            Drop voter Excel file here
          </h3>
          <p className="text-gray-600 mb-4">
            or click to browse — one or more .xlsx files
          </p>

          <div className="inline-flex items-center gap-2 text-sm text-gray-500 bg-gray-50 px-4 py-2 rounded-lg">
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            All sheets in each file will be merged into one flat table
          </div>
        </div>
      </div>

      {/* Selected files list */}
      {files.length > 0 && (
        <div className="bg-white rounded-xl shadow-lg p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h4 className="text-lg font-semibold text-gray-900">
              Selected Files ({files.length})
            </h4>
            <span className="text-sm text-gray-500">
              Total: {formatFileSize(totalSize)}
            </span>
          </div>

          <div className="space-y-2 max-h-64 overflow-y-auto">
            {files.map((file, idx) => (
              <div
                key={`${file.name}-${idx}`}
                className="flex items-center justify-between bg-gray-50 rounded-lg px-4 py-2"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <svg
                    className="w-5 h-5 text-green-600 flex-shrink-0"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                    />
                  </svg>
                  <span className="text-sm text-gray-800 truncate">
                    {file.name}
                  </span>
                  <span className="text-xs text-gray-500 flex-shrink-0">
                    {formatFileSize(file.size)}
                  </span>
                </div>
                {status !== "merging" && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      removeFile(idx);
                    }}
                    className="p-1 rounded hover:bg-red-100 text-gray-400 hover:text-red-600 transition-colors"
                  >
                    <svg
                      className="w-4 h-4"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M6 18L18 6M6 6l12 12"
                      />
                    </svg>
                  </button>
                )}
              </div>
            ))}
          </div>

          {/* Action buttons */}
          <div className="flex items-center gap-3 mt-4 pt-4 border-t border-gray-200">
            {status === "idle" && (
              <>
                <button
                  onClick={handleMerge}
                  disabled={files.length === 0}
                  className="flex items-center gap-2 px-6 py-2.5 bg-green-600 text-white rounded-lg hover:bg-green-700 font-medium text-sm transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <svg
                    className="w-4 h-4"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                    />
                  </svg>
                  Merge &amp; Download
                </button>
                <button
                  onClick={handleReset}
                  className="px-4 py-2.5 text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-lg font-medium text-sm transition-colors"
                >
                  Clear All
                </button>
              </>
            )}

            {status === "merging" && (
              <div className="flex items-center gap-3 text-blue-600">
                <svg
                  className="w-5 h-5 animate-spin"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                  />
                </svg>
                <span className="font-medium">
                  Merging {files.length} file{files.length !== 1 ? "s" : ""}...
                </span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Completed state */}
      {status === "completed" && result && (
        <div className="bg-white rounded-xl shadow-lg p-6 mb-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 bg-green-100 rounded-full flex items-center justify-center">
              <svg
                className="w-6 h-6 text-green-600"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M5 13l4 4L19 7"
                />
              </svg>
            </div>
            <div>
              <h4 className="text-lg font-semibold text-gray-900">
                Merge Complete
              </h4>
              <p className="text-sm text-gray-600">
                {result.totalRows.toLocaleString()} rows from{" "}
                {result.totalSheets} sheet{result.totalSheets !== 1 ? "s" : ""}{" "}
                across {result.totalFiles} file
                {result.totalFiles !== 1 ? "s" : ""}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={handleDownload}
              className="flex items-center gap-2 px-6 py-2.5 bg-green-600 text-white rounded-lg hover:bg-green-700 font-medium text-sm transition-colors shadow-sm"
            >
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                />
              </svg>
              Download Merged Excel
            </button>
            <button
              onClick={handleReset}
              className="px-4 py-2.5 text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-lg font-medium text-sm transition-colors"
            >
              Start Over
            </button>
          </div>
        </div>
      )}

      {/* Error state */}
      {status === "error" && (
        <div className="bg-white rounded-xl shadow-lg p-6 mb-6 border-l-4 border-red-500">
          <div className="flex items-center gap-3 mb-3">
            <svg
              className="w-6 h-6 text-red-600"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <h4 className="text-lg font-semibold text-red-700">Merge Failed</h4>
          </div>
          <p className="text-sm text-gray-700 mb-4">{error}</p>
          <div className="flex items-center gap-3">
            <button
              onClick={handleMerge}
              className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 text-sm font-medium transition-colors"
            >
              Retry
            </button>
            <button
              onClick={handleReset}
              className="px-4 py-2 text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-lg text-sm font-medium transition-colors"
            >
              Start Over
            </button>
          </div>
        </div>
      )}
    </>
  );
}
