"use client";

import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Loader2, Table, ChevronLeft, ChevronRight, Columns } from "lucide-react";
import { getPreview } from "@/lib/api";
import type { PreviewData } from "@/types";

interface PreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  taskId: string;
  onDownload: () => void;
  onFilterColumns?: () => void;
}

export function PreviewModal({
  isOpen,
  onClose,
  taskId,
  onDownload,
  onFilterColumns,
}: PreviewModalProps) {
  const [previewData, setPreviewData] = useState<PreviewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen && taskId) {
      setLoading(true);
      setError(null);

      getPreview(taskId)
        .then(setPreviewData)
        .catch((err) => setError(err.message))
        .finally(() => setLoading(false));
    }
  }, [isOpen, taskId]);

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl max-h-[80vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Table className="h-5 w-5" />
            Data Preview
          </DialogTitle>
          <DialogDescription>
            Preview of the first 10 rows of extracted data
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-hidden">
          {loading && (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 text-blue-600 animate-spin" />
              <span className="ml-2 text-gray-600">Loading preview...</span>
            </div>
          )}

          {error && (
            <div className="text-center py-12 text-red-600">
              <p>Failed to load preview: {error}</p>
            </div>
          )}

          {previewData && !loading && (
            <div className="space-y-4">
              {/* Stats */}
              <div className="flex gap-4 text-sm text-gray-600 border-b pb-3 items-center justify-between">
                <div className="flex gap-4">
                  <span>
                    <strong>{previewData.total_rows}</strong> rows
                  </span>
                  <span>
                    <strong>{previewData.total_columns}</strong> columns
                  </span>
                  <span>
                    <strong>{previewData.pages_processed}</strong> pages processed
                  </span>
                </div>
                {onFilterColumns && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={onFilterColumns}
                    className="gap-2"
                  >
                    <Columns className="h-4 w-4" />
                    Filter Columns
                  </Button>
                )}
              </div>

              {/* Column List */}
              {previewData.headers.length > 0 && (
                <div className="bg-gray-50 rounded-lg p-3 mb-4">
                  <p className="text-xs font-medium text-gray-700 mb-2">Available Columns:</p>
                  <div className="flex flex-wrap gap-2">
                    {previewData.headers.map((header, index) => (
                      <span
                        key={index}
                        className="text-xs px-2 py-1 bg-white border border-gray-200 rounded"
                      >
                        {header}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Table */}
              <div className="overflow-auto max-h-[400px] border rounded-lg">
                <table className="min-w-full divide-y divide-gray-200 preview-table" dir="ltr">
                  <thead className="bg-[#366092] sticky top-0">
                    <tr>
                      {previewData.headers.map((header, index) => (
                        <th
                          key={index}
                          className="px-4 py-3 text-left text-xs font-bold text-white uppercase tracking-wider whitespace-nowrap"
                        >
                          {header || `Column ${index + 1}`}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {previewData.rows.map((row, rowIndex) => (
                      <tr
                        key={rowIndex}
                        className={rowIndex % 2 === 0 ? "bg-white" : "bg-gray-50"}
                      >
                        {row.map((cell, cellIndex) => (
                          <td
                            key={cellIndex}
                            className="px-4 py-2 text-sm text-gray-900 whitespace-nowrap"
                          >
                            {cell !== null ? String(cell) : ""}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {previewData.total_rows > 10 && (
                <p className="text-sm text-gray-500 text-center">
                  Showing 10 of {previewData.total_rows} rows
                </p>
              )}
            </div>
          )}
        </div>

        <DialogFooter className="border-t pt-4">
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>
          <Button onClick={onDownload} disabled={loading || !!error}>
            Download Excel
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
