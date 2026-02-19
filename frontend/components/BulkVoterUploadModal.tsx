"use client";

import { useState, useCallback, useRef } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import {
  Upload,
  FolderOpen,
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  FileText,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useBulkVotersUpload } from "@/hooks/useBulkVotersUpload";

interface BulkVoterUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function BulkVoterUploadModal({
  isOpen,
  onClose,
}: BulkVoterUploadModalProps) {
  const [files, setFiles] = useState<File[]>([]);
  const [showErrors, setShowErrors] = useState(false);
  const folderInputRef = useRef<HTMLInputElement>(null);
  const filesInputRef = useRef<HTMLInputElement>(null);

  const {
    status,
    totalFiles,
    uploadedFiles,
    completedPdfs,
    totalVoters,
    currentFile,
    failedCount,
    error,
    summary,
    startBulkUpload,
    reset,
    downloadResult,
  } = useBulkVotersUpload();

  const handleClose = useCallback(() => {
    if (status !== "uploading" && status !== "processing") {
      reset();
      setFiles([]);
      setShowErrors(false);
      onClose();
    }
  }, [status, reset, onClose]);

  const handleFolderSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const selected = Array.from(e.target.files || []).filter((f) =>
        f.name.toLowerCase().endsWith(".pdf")
      );
      if (selected.length > 0) {
        setFiles(selected);
      }
      // Reset input so same folder can be re-selected
      e.target.value = "";
    },
    []
  );

  const handleFilesSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const selected = Array.from(e.target.files || []).filter((f) =>
        f.name.toLowerCase().endsWith(".pdf")
      );
      if (selected.length > 0) {
        setFiles(selected);
      }
      e.target.value = "";
    },
    []
  );

  const handleStart = useCallback(() => {
    if (files.length > 0) {
      startBulkUpload(files);
    }
  }, [files, startBulkUpload]);

  const handleReset = useCallback(() => {
    reset();
    setFiles([]);
    setShowErrors(false);
  }, [reset]);

  const isWorking = status === "uploading" || status === "processing";
  const isIdle = status === "idle";
  const isComplete = status === "completed";
  const isError = status === "error";

  const processingPercent =
    totalFiles > 0
      ? Math.round((completedPdfs / totalFiles) * 100)
      : 0;

  const uploadPercent =
    totalFiles > 0
      ? Math.round((uploadedFiles / totalFiles) * 100)
      : 0;

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && handleClose()}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FolderOpen className="h-5 w-5 text-purple-600" />
            Bulk Voter PDF Processing
          </DialogTitle>
          <DialogDescription>
            Select a constituency folder or multiple PDFs to extract all voter
            data into one consolidated Excel file.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 pt-2">
          {/* File Selection - only show when idle and no files selected */}
          {isIdle && files.length === 0 && (
            <div className="space-y-3">
              {/* Folder Upload */}
              <button
                onClick={() => folderInputRef.current?.click()}
                className="w-full border-2 border-dashed border-purple-300 rounded-xl p-6 text-center cursor-pointer hover:border-purple-500 hover:bg-purple-50 transition-all duration-200"
              >
                <FolderOpen className="h-10 w-10 mx-auto mb-2 text-purple-500" />
                <p className="font-medium text-gray-700">
                  Select Constituency Folder
                </p>
                <p className="text-sm text-gray-500 mt-1">
                  All PDFs in the folder will be processed
                </p>
              </button>
              <input
                ref={folderInputRef}
                type="file"
                className="hidden"
                // @ts-expect-error webkitdirectory is a non-standard attribute
                webkitdirectory=""
                directory=""
                multiple
                onChange={handleFolderSelect}
              />

              {/* Or separator */}
              <div className="flex items-center gap-3">
                <div className="flex-1 h-px bg-gray-200" />
                <span className="text-sm text-gray-400">or</span>
                <div className="flex-1 h-px bg-gray-200" />
              </div>

              {/* Multiple Files */}
              <button
                onClick={() => filesInputRef.current?.click()}
                className="w-full border-2 border-dashed border-gray-300 rounded-xl p-6 text-center cursor-pointer hover:border-gray-400 hover:bg-gray-50 transition-all duration-200"
              >
                <Upload className="h-10 w-10 mx-auto mb-2 text-gray-400" />
                <p className="font-medium text-gray-700">
                  Select Multiple PDFs
                </p>
                <p className="text-sm text-gray-500 mt-1">
                  Choose individual PDF files
                </p>
              </button>
              <input
                ref={filesInputRef}
                type="file"
                className="hidden"
                multiple
                accept=".pdf"
                onChange={handleFilesSelect}
              />
            </div>
          )}

          {/* Files Selected - Ready to Start */}
          {isIdle && files.length > 0 && (
            <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
              <div className="flex items-center gap-3">
                <FileText className="h-8 w-8 text-purple-600 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-purple-900">
                    {files.length} PDF files selected
                  </p>
                  <p className="text-sm text-purple-600">
                    Ready to process with 8 concurrent workers
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Upload Progress */}
          {status === "uploading" && (
            <div className="space-y-2">
              <div className="flex justify-between text-sm text-gray-600">
                <span>
                  Uploading files to server...
                </span>
                <span className="font-medium">
                  {uploadedFiles}/{totalFiles}
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2.5 overflow-hidden">
                <div
                  className="bg-purple-600 h-2.5 rounded-full transition-all duration-500 ease-out"
                  style={{ width: `${uploadPercent}%` }}
                />
              </div>
            </div>
          )}

          {/* Processing Progress */}
          {status === "processing" && (
            <div className="space-y-3">
              <div className="space-y-2">
                <div className="flex justify-between text-sm text-gray-600">
                  <span>Processing PDFs...</span>
                  <span className="font-medium">
                    {completedPdfs}/{totalFiles} ({processingPercent}%)
                  </span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
                  <div
                    className="bg-purple-600 h-3 rounded-full transition-all duration-500 ease-out"
                    style={{ width: `${processingPercent}%` }}
                  />
                </div>
              </div>

              {/* Stats during processing */}
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div className="bg-blue-50 rounded-lg p-2 text-center">
                  <p className="text-blue-600 font-semibold">
                    {totalVoters.toLocaleString()}
                  </p>
                  <p className="text-blue-500 text-xs">Voters Found</p>
                </div>
                <div
                  className={cn(
                    "rounded-lg p-2 text-center",
                    failedCount > 0 ? "bg-red-50" : "bg-green-50"
                  )}
                >
                  <p
                    className={cn(
                      "font-semibold",
                      failedCount > 0 ? "text-red-600" : "text-green-600"
                    )}
                  >
                    {failedCount}
                  </p>
                  <p
                    className={cn(
                      "text-xs",
                      failedCount > 0 ? "text-red-500" : "text-green-500"
                    )}
                  >
                    Failed PDFs
                  </p>
                </div>
              </div>

              {currentFile && (
                <p className="text-xs text-gray-500 truncate">
                  Current: {currentFile}
                </p>
              )}
            </div>
          )}

          {/* Completed */}
          {isComplete && summary && (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-green-700 bg-green-50 border border-green-200 rounded-lg p-3">
                <CheckCircle2 className="h-5 w-5 flex-shrink-0" />
                <div>
                  <p className="font-medium">Bulk Processing Complete!</p>
                  <p className="text-sm">
                    {summary.total_voters.toLocaleString()} voters from{" "}
                    {summary.successful_pdfs}/{summary.total_pdfs} PDFs
                  </p>
                </div>
              </div>

              {/* Summary stats */}
              <div className="grid grid-cols-3 gap-2 text-sm">
                <div className="bg-blue-50 rounded-lg p-2 text-center">
                  <p className="text-blue-700 font-semibold">
                    {summary.total_voters.toLocaleString()}
                  </p>
                  <p className="text-blue-500 text-xs">Total Voters</p>
                </div>
                <div className="bg-green-50 rounded-lg p-2 text-center">
                  <p className="text-green-700 font-semibold">
                    {summary.successful_pdfs}
                  </p>
                  <p className="text-green-500 text-xs">Booths OK</p>
                </div>
                <div
                  className={cn(
                    "rounded-lg p-2 text-center",
                    summary.failed_pdfs.length > 0
                      ? "bg-red-50"
                      : "bg-gray-50"
                  )}
                >
                  <p
                    className={cn(
                      "font-semibold",
                      summary.failed_pdfs.length > 0
                        ? "text-red-700"
                        : "text-gray-500"
                    )}
                  >
                    {summary.failed_pdfs.length}
                  </p>
                  <p
                    className={cn(
                      "text-xs",
                      summary.failed_pdfs.length > 0
                        ? "text-red-500"
                        : "text-gray-400"
                    )}
                  >
                    Failed
                  </p>
                </div>
              </div>

              {/* Failed PDFs expandable list */}
              {summary.failed_pdfs.length > 0 && (
                <div className="border border-red-200 rounded-lg overflow-hidden">
                  <button
                    onClick={() => setShowErrors((s) => !s)}
                    className="w-full flex items-center justify-between px-3 py-2 bg-red-50 text-red-700 text-sm font-medium hover:bg-red-100 transition-colors"
                  >
                    <span>
                      {summary.failed_pdfs.length} failed PDF
                      {summary.failed_pdfs.length > 1 ? "s" : ""}
                    </span>
                    {showErrors ? (
                      <ChevronUp className="h-4 w-4" />
                    ) : (
                      <ChevronDown className="h-4 w-4" />
                    )}
                  </button>
                  {showErrors && (
                    <div className="max-h-40 overflow-y-auto divide-y divide-red-100">
                      {summary.failed_pdfs.map((fp, i) => (
                        <div key={i} className="px-3 py-2 text-xs">
                          <p className="font-medium text-gray-800 truncate">
                            {fp.filename}
                          </p>
                          <p className="text-red-500 truncate">{fp.error}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Error */}
          {isError && (
            <div className="flex items-start gap-2 text-red-600 text-sm bg-red-50 border border-red-200 rounded-lg p-3">
              <AlertCircle className="h-4 w-4 flex-shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex gap-3 pt-2">
            {isIdle && (
              <>
                <Button
                  variant="outline"
                  onClick={handleClose}
                  className="flex-1"
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleStart}
                  className="flex-1 bg-purple-600 hover:bg-purple-700"
                  disabled={files.length === 0}
                >
                  Process {files.length > 0 ? `${files.length} PDFs` : ""}
                </Button>
              </>
            )}

            {isWorking && (
              <Button variant="outline" className="flex-1" disabled>
                <svg
                  className="w-4 h-4 animate-spin mr-2"
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
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
                {status === "uploading" ? "Uploading..." : "Processing..."}
              </Button>
            )}

            {isComplete && (
              <>
                <Button
                  variant="outline"
                  onClick={handleReset}
                  className="flex-1"
                >
                  Process Another
                </Button>
                <Button
                  onClick={downloadResult}
                  className="flex-1 bg-green-600 hover:bg-green-700"
                >
                  Download Excel
                </Button>
              </>
            )}

            {isError && (
              <>
                <Button
                  variant="outline"
                  onClick={handleClose}
                  className="flex-1"
                >
                  Close
                </Button>
                <Button onClick={handleReset} className="flex-1">
                  Try Again
                </Button>
              </>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
