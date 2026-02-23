"use client";

import { useCallback } from "react";
import { useDropzone, FileRejection } from "react-dropzone";
import { Upload, FileText, AlertCircle } from "lucide-react";
import { cn, formatFileSize, isValidPdfFile } from "@/lib/utils";

interface DropZoneProps {
  onFileSelect: (file: File) => void;
  isDisabled?: boolean;
  acceptedFile?: File | null;
  error?: string | null;
}

const MAX_FILE_SIZE = 55 * 1024 * 1024; // 55MB

export function DropZone({
  onFileSelect,
  isDisabled = false,
  acceptedFile,
  error,
}: DropZoneProps) {
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

  const { getRootProps, getInputProps, isDragActive, fileRejections } =
    useDropzone({
      onDrop,
      accept: { "application/pdf": [".pdf"] },
      maxFiles: 1,
      maxSize: MAX_FILE_SIZE,
      disabled: isDisabled,
    });

  const rejectionError =
    fileRejections.length > 0
      ? fileRejections[0].errors[0]?.code === "file-too-large"
        ? "File is too large. Maximum size is 55MB."
        : fileRejections[0].errors[0]?.code === "file-invalid-type"
          ? "Only PDF files are accepted."
          : "Invalid file"
      : null;

  const displayError = error || rejectionError;

  return (
    <div className="space-y-4">
      <div
        {...getRootProps()}
        className={cn(
          "border-2 border-dashed rounded-xl p-8 md:p-12 text-center cursor-pointer transition-all duration-200",
          isDragActive
            ? "border-blue-500 bg-blue-50"
            : "border-gray-300 hover:border-gray-400 hover:bg-gray-50",
          isDisabled && "opacity-50 cursor-not-allowed",
          displayError && "border-red-300 bg-red-50"
        )}
      >
        <input {...getInputProps()} />

        {acceptedFile ? (
          <div className="space-y-3">
            <FileText className="h-12 w-12 md:h-16 md:w-16 text-blue-600 mx-auto" />
            <div>
              <p className="font-medium text-gray-900 truncate max-w-xs mx-auto">
                {acceptedFile.name}
              </p>
              <p className="text-sm text-gray-500">
                {formatFileSize(acceptedFile.size)}
              </p>
            </div>
            <p className="text-sm text-gray-500">
              Drop a different file to replace
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            <Upload
              className={cn(
                "h-12 w-12 md:h-16 md:w-16 mx-auto dropzone-icon",
                isDragActive ? "text-blue-600" : "text-gray-400"
              )}
            />
            <div>
              <p className="font-medium text-gray-700">
                {isDragActive
                  ? "Drop your PDF here"
                  : "Drag and drop your PDF here"}
              </p>
              <p className="text-sm text-gray-500 mt-1">
                or click to browse (max 10MB)
              </p>
            </div>
          </div>
        )}
      </div>

      {displayError && (
        <div className="flex items-center gap-2 text-red-600 text-sm">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          <span>{displayError}</span>
        </div>
      )}
    </div>
  );
}
