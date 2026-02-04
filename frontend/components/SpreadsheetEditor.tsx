"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import {
  Loader2,
  Download,
  X,
  Filter,
  MapPin,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";
import {
  getFullPreview,
  downloadModifiedExcel,
  startGeocoding,
  subscribeToGeocodeProgress,
  applyGeocoding,
  cancelGeocoding,
} from "@/lib/api";
import type { FullPreviewData, CellValue, GeocodeProgressEvent } from "@/types";

interface SpreadsheetEditorProps {
  isOpen: boolean;
  onClose: () => void;
  taskId: string;
  filename: string;
  onFilterColumns?: () => void;
}

interface ContextMenuPosition {
  x: number;
  y: number;
  row: number;
  col: number;
}

export function SpreadsheetEditor({
  isOpen,
  onClose,
  taskId,
  filename,
  onFilterColumns,
}: SpreadsheetEditorProps) {
  const [previewData, setPreviewData] = useState<FullPreviewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);
  const [editedData, setEditedData] = useState<{
    headers: string[];
    rows: CellValue[][];
  } | null>(null);
  const [contextMenu, setContextMenu] = useState<ContextMenuPosition | null>(null);
  const contextMenuRef = useRef<HTMLDivElement>(null);

  // Geocoding state
  const [geocodeDialogOpen, setGeocodeDialogOpen] = useState(false);
  const [geocoding, setGeocoding] = useState(false);
  const [geocodeProgress, setGeocodeProgress] = useState<GeocodeProgressEvent | null>(null);
  const [geocodeTaskId, setGeocodeTaskId] = useState<string | null>(null);
  const [selectedAddressColumn, setSelectedAddressColumn] = useState<string>("");
  const [regionHint, setRegionHint] = useState("Tamil Nadu, India");
  const [useRegionHint, setUseRegionHint] = useState(true);
  const [geocodeResult, setGeocodeResult] = useState<{ successful: number; failed: number } | null>(null);
  const geocodeUnsubscribeRef = useRef<(() => void) | null>(null);

  // Fetch preview data when modal opens
  useEffect(() => {
    if (isOpen && taskId) {
      setLoading(true);
      setError(null);

      getFullPreview(taskId)
        .then((data) => {
          setPreviewData(data);
          setEditedData({
            headers: [...data.headers],
            rows: data.rows.map(row => [...row]),
          });
        })
        .catch((err) => setError(err.message))
        .finally(() => setLoading(false));
    }
  }, [isOpen, taskId]);

  // Close context menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (contextMenuRef.current && !contextMenuRef.current.contains(e.target as Node)) {
        setContextMenu(null);
      }
    };

    if (contextMenu) {
      document.addEventListener("click", handleClickOutside);
      return () => document.removeEventListener("click", handleClickOutside);
    }
  }, [contextMenu]);

  // Handle cell edit
  const handleCellEdit = useCallback((rowIndex: number, colIndex: number, value: string) => {
    if (!editedData) return;

    const newRows = editedData.rows.map((row, rIdx) =>
      rIdx === rowIndex
        ? row.map((cell, cIdx) => (cIdx === colIndex ? value : cell))
        : row
    );

    setEditedData({
      ...editedData,
      rows: newRows,
    });
  }, [editedData]);

  // Handle context menu
  const handleContextMenu = useCallback((e: React.MouseEvent, row: number, col: number) => {
    e.preventDefault();
    setContextMenu({
      x: e.clientX,
      y: e.clientY,
      row,
      col,
    });
  }, []);

  // Context menu actions
  const handleCopyCell = useCallback(() => {
    if (!contextMenu || !editedData) return;
    const value = editedData.rows[contextMenu.row]?.[contextMenu.col];
    if (value !== null && value !== undefined) {
      navigator.clipboard.writeText(String(value));
    }
    setContextMenu(null);
  }, [contextMenu, editedData]);

  const handleInsertRowAbove = useCallback(() => {
    if (!contextMenu || !editedData) return;
    const newRow = Array(editedData.headers.length).fill(null);
    const newRows = [
      ...editedData.rows.slice(0, contextMenu.row),
      newRow,
      ...editedData.rows.slice(contextMenu.row),
    ];
    setEditedData({ ...editedData, rows: newRows });
    setContextMenu(null);
  }, [contextMenu, editedData]);

  const handleInsertRowBelow = useCallback(() => {
    if (!contextMenu || !editedData) return;
    const newRow = Array(editedData.headers.length).fill(null);
    const newRows = [
      ...editedData.rows.slice(0, contextMenu.row + 1),
      newRow,
      ...editedData.rows.slice(contextMenu.row + 1),
    ];
    setEditedData({ ...editedData, rows: newRows });
    setContextMenu(null);
  }, [contextMenu, editedData]);

  const handleDeleteRow = useCallback(() => {
    if (!contextMenu || !editedData) return;
    const newRows = editedData.rows.filter((_, idx) => idx !== contextMenu.row);
    setEditedData({ ...editedData, rows: newRows });
    setContextMenu(null);
  }, [contextMenu, editedData]);

  // Download Excel with edited data
  const handleDownload = useCallback(async () => {
    if (!taskId || !editedData) return;

    setDownloading(true);
    try {
      await downloadModifiedExcel(
        taskId,
        editedData.headers,
        editedData.rows,
        filename,
        previewData?.document_title
      );
    } catch (err) {
      console.error("Download failed:", err);
      setError(err instanceof Error ? err.message : "Download failed");
    } finally {
      setDownloading(false);
    }
  }, [taskId, editedData, filename, previewData]);

  // Geocoding handlers
  const openGeocodeDialog = useCallback(() => {
    if (editedData && editedData.headers.length > 0) {
      // Try to auto-select the address column
      const addressColumnIndex = editedData.headers.findIndex(
        (h) =>
          h.toLowerCase().includes("location") ||
          h.toLowerCase().includes("address") ||
          h.toLowerCase().includes("building")
      );
      setSelectedAddressColumn(
        addressColumnIndex >= 0 ? editedData.headers[addressColumnIndex] : editedData.headers[0]
      );
    }
    setGeocodeResult(null);
    setGeocodeProgress(null);
    setGeocodeDialogOpen(true);
  }, [editedData]);

  const handleStartGeocoding = useCallback(async () => {
    if (!taskId || !editedData || !selectedAddressColumn) return;

    setGeocoding(true);
    setGeocodeResult(null);
    setGeocodeProgress(null);

    try {
      const response = await startGeocoding(
        taskId,
        selectedAddressColumn,
        useRegionHint ? regionHint : ""
      );

      setGeocodeTaskId(response.geocode_task_id);

      // Subscribe to progress updates
      const unsubscribe = subscribeToGeocodeProgress(
        response.geocode_task_id,
        (event) => {
          setGeocodeProgress(event);
        },
        async (event) => {
          // Geocoding completed - apply results
          try {
            const result = await applyGeocoding(
              response.geocode_task_id,
              taskId,
              editedData.headers,
              editedData.rows
            );

            // Update the spreadsheet data with new columns
            setEditedData({
              headers: result.headers,
              rows: result.rows,
            });

            setGeocodeResult({
              successful: result.successful,
              failed: result.failed,
            });
          } catch (err) {
            console.error("Failed to apply geocoding:", err);
            setError(err instanceof Error ? err.message : "Failed to apply geocoding results");
          } finally {
            setGeocoding(false);
          }
        },
        (err) => {
          console.error("Geocoding error:", err);
          setError(err.message);
          setGeocoding(false);
        }
      );

      geocodeUnsubscribeRef.current = unsubscribe;
    } catch (err) {
      console.error("Failed to start geocoding:", err);
      setError(err instanceof Error ? err.message : "Failed to start geocoding");
      setGeocoding(false);
    }
  }, [taskId, editedData, selectedAddressColumn, useRegionHint, regionHint]);

  const handleCancelGeocoding = useCallback(async () => {
    if (geocodeTaskId) {
      try {
        await cancelGeocoding(geocodeTaskId);
      } catch (err) {
        console.error("Failed to cancel geocoding:", err);
      }
    }
    if (geocodeUnsubscribeRef.current) {
      geocodeUnsubscribeRef.current();
      geocodeUnsubscribeRef.current = null;
    }
    setGeocoding(false);
  }, [geocodeTaskId]);

  const closeGeocodeDialog = useCallback(() => {
    if (geocoding) {
      handleCancelGeocoding();
    }
    setGeocodeDialogOpen(false);
  }, [geocoding, handleCancelGeocoding]);

  // Cleanup geocoding subscription on unmount
  useEffect(() => {
    return () => {
      if (geocodeUnsubscribeRef.current) {
        geocodeUnsubscribeRef.current();
      }
    };
  }, []);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl/Cmd + S to download
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        handleDownload();
      }
      // Escape to close
      if (e.key === 'Escape') {
        onClose();
      }
    };

    if (isOpen) {
      window.addEventListener('keydown', handleKeyDown);
      return () => window.removeEventListener('keydown', handleKeyDown);
    }
  }, [isOpen, handleDownload, onClose]);

  const outputFilename = filename.replace(".pdf", ".xlsx");

  return (
    <DialogPrimitive.Root open={isOpen} onOpenChange={onClose}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/50" />
        <DialogPrimitive.Content
          className="fixed inset-0 z-50 bg-white flex flex-col"
          style={{ width: '100vw', height: '100vh', maxWidth: '100vw', maxHeight: '100vh' }}
          aria-describedby="spreadsheet-description"
        >
          <DialogPrimitive.Title className="sr-only">
            {previewData?.document_title || outputFilename || "Spreadsheet Editor"}
          </DialogPrimitive.Title>
          <DialogPrimitive.Description id="spreadsheet-description" className="sr-only">
            {editedData ? `Edit and download spreadsheet with ${editedData.rows.length} rows and ${editedData.headers.length} columns` : "Loading spreadsheet data"}
          </DialogPrimitive.Description>

          {/* Header */}
          <header className="bg-white border-b border-gray-200 h-16 flex items-center px-6 sticky top-0 z-50 shrink-0">
            <div className="flex items-center justify-between w-full">
              <div className="flex items-center gap-4">
                <button
                  onClick={onClose}
                  className="text-gray-600 hover:text-gray-900 p-2 hover:bg-gray-100 rounded-lg transition-colors"
                  aria-label="Close"
                >
                  <X className="w-6 h-6" />
                </button>
                <div>
                  <h1 className="text-lg font-semibold text-gray-900">
                    {outputFilename}
                  </h1>
                  {editedData && (
                    <p className="text-xs text-gray-500">
                      {editedData.rows.length} rows × {editedData.headers.length} columns
                    </p>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-3">
                {onFilterColumns && (
                  <button
                    onClick={onFilterColumns}
                    disabled={loading || !!error}
                    className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <Filter className="w-4 h-4" />
                    Filter Columns
                  </button>
                )}

                <button
                  onClick={openGeocodeDialog}
                  disabled={loading || !!error || geocoding}
                  className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <MapPin className="w-4 h-4" />
                  Geocode Addresses
                </button>

                <button
                  onClick={handleDownload}
                  disabled={loading || !!error || downloading}
                  className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {downloading ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Download className="w-4 h-4" />
                  )}
                  Download Excel
                </button>
              </div>
            </div>
          </header>

          {/* Loading State */}
          {loading && (
            <div className="flex items-center justify-center h-[calc(100vh-64px)]">
              <div className="text-center">
                <Loader2 className="w-12 h-12 text-blue-600 animate-spin mx-auto mb-4" />
                <p className="text-gray-600 font-medium">Loading spreadsheet data...</p>
              </div>
            </div>
          )}

          {/* Error State */}
          {error && (
            <div className="flex items-center justify-center h-[calc(100vh-64px)]">
              <div className="text-center max-w-md">
                <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
                  <X className="w-8 h-8 text-red-600" />
                </div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">Failed to Load Data</h3>
                <p className="text-gray-600 mb-4">{error}</p>
                <button
                  onClick={onClose}
                  className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium transition-colors"
                >
                  Go Back
                </button>
              </div>
            </div>
          )}

          {/* Spreadsheet Content */}
          {!loading && !error && editedData && (
            <div className="flex-1 overflow-auto">
              <table className="w-full border-collapse text-[13px]">
                <thead>
                  <tr>
                    <th className="bg-[#366092] text-white font-semibold p-3 text-center border border-[#2d5078] sticky top-0 left-0 z-20 text-[11px] whitespace-nowrap min-w-[60px]">
                      PS No.
                    </th>
                    {editedData.headers.map((header, idx) => (
                      <th
                        key={idx}
                        className="bg-[#366092] text-white font-semibold p-3 text-center border border-[#2d5078] sticky top-0 z-10 text-[11px] whitespace-nowrap min-w-[80px]"
                      >
                        {header}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {editedData.rows.map((row, rowIndex) => (
                    <tr key={rowIndex} className="hover:bg-gray-50">
                      <td className="bg-gray-100 font-semibold text-gray-600 p-2 border border-gray-300 text-center sticky left-0 z-5 min-w-[60px]">
                        {rowIndex + 1}
                      </td>
                      {row.map((cell, colIndex) => (
                        <td
                          key={colIndex}
                          className="p-2 border border-gray-300 text-center bg-white min-w-[80px] focus:outline focus:outline-2 focus:outline-blue-500 focus:outline-offset-[-1px]"
                          contentEditable
                          suppressContentEditableWarning
                          onBlur={(e) => handleCellEdit(rowIndex, colIndex, e.currentTarget.textContent || "")}
                          onContextMenu={(e) => handleContextMenu(e, rowIndex, colIndex)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' && !e.shiftKey) {
                              e.preventDefault();
                              (e.currentTarget as HTMLElement).blur();
                            }
                          }}
                        >
                          {cell !== null && cell !== undefined ? String(cell) : ""}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Context Menu */}
          {contextMenu && (
            <div
              ref={contextMenuRef}
              className="fixed bg-white border border-gray-200 shadow-lg rounded-lg py-1 z-[60] min-w-[180px]"
              style={{ left: contextMenu.x, top: contextMenu.y }}
            >
              <button
                onClick={handleCopyCell}
                className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-100 flex items-center gap-2"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3" />
                </svg>
                Copy
              </button>
              <div className="border-t border-gray-200 my-1"></div>
              <button
                onClick={handleInsertRowAbove}
                className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-100 flex items-center gap-2"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                </svg>
                Insert Row Above
              </button>
              <button
                onClick={handleInsertRowBelow}
                className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-100 flex items-center gap-2"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                </svg>
                Insert Row Below
              </button>
              <button
                onClick={handleDeleteRow}
                className="w-full px-4 py-2 text-left text-sm text-red-600 hover:bg-red-50 flex items-center gap-2"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
                Delete Row
              </button>
            </div>
          )}

          {/* Geocode Dialog */}
          {geocodeDialogOpen && (
            <div className="fixed inset-0 z-[70] flex items-center justify-center">
              <div
                className="absolute inset-0 bg-black/30"
                onClick={closeGeocodeDialog}
              />
              <div className="relative bg-white rounded-xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
                {/* Dialog Header */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
                  <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                    <MapPin className="w-5 h-5 text-blue-600" />
                    Geocode Addresses
                  </h2>
                  <button
                    onClick={closeGeocodeDialog}
                    className="p-1 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>

                {/* Dialog Content */}
                <div className="px-6 py-4">
                  {!geocoding && !geocodeResult && (
                    <>
                      {/* Address Column Selection */}
                      <div className="mb-4">
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                          Address Column
                        </label>
                        <select
                          value={selectedAddressColumn}
                          onChange={(e) => setSelectedAddressColumn(e.target.value)}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                        >
                          {editedData?.headers.map((header, idx) => (
                            <option key={idx} value={header}>
                              {header}
                            </option>
                          ))}
                        </select>
                      </div>

                      {/* Region Hint */}
                      <div className="mb-4">
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={useRegionHint}
                            onChange={(e) => setUseRegionHint(e.target.checked)}
                            className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                          />
                          <span className="text-sm font-medium text-gray-700">
                            Add region hint for better accuracy
                          </span>
                        </label>
                        {useRegionHint && (
                          <input
                            type="text"
                            value={regionHint}
                            onChange={(e) => setRegionHint(e.target.value)}
                            placeholder="e.g., Tamil Nadu, India"
                            className="w-full mt-2 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                          />
                        )}
                      </div>

                      {/* Info */}
                      <div className="p-3 bg-blue-50 rounded-lg mb-4">
                        <p className="text-sm text-blue-800">
                          This will add <strong>Latitude</strong> and <strong>Longitude</strong> columns
                          to your spreadsheet by geocoding addresses using OpenStreetMap.
                        </p>
                      </div>
                    </>
                  )}

                  {/* Progress State */}
                  {geocoding && geocodeProgress && (
                    <div className="py-4">
                      <div className="mb-4">
                        <div className="flex justify-between text-sm text-gray-600 mb-2">
                          <span>Geocoding addresses...</span>
                          <span>{geocodeProgress.current} / {geocodeProgress.total}</span>
                        </div>
                        <div className="w-full bg-gray-200 rounded-full h-2.5">
                          <div
                            className="bg-blue-600 h-2.5 rounded-full transition-all duration-300"
                            style={{
                              width: `${(geocodeProgress.current / geocodeProgress.total) * 100}%`,
                            }}
                          />
                        </div>
                      </div>

                      <div className="flex gap-4 text-sm">
                        <div className="flex items-center gap-1 text-green-600">
                          <CheckCircle2 className="w-4 h-4" />
                          <span>{geocodeProgress.success_count} successful</span>
                        </div>
                        <div className="flex items-center gap-1 text-amber-600">
                          <AlertCircle className="w-4 h-4" />
                          <span>{geocodeProgress.failed_count} not found</span>
                        </div>
                      </div>

                      <p className="mt-3 text-xs text-gray-500 truncate">
                        {geocodeProgress.message}
                      </p>
                    </div>
                  )}

                  {/* Result State */}
                  {geocodeResult && (
                    <div className="py-4 text-center">
                      <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                        <CheckCircle2 className="w-8 h-8 text-green-600" />
                      </div>
                      <h3 className="text-lg font-semibold text-gray-900 mb-2">
                        Geocoding Complete!
                      </h3>
                      <div className="flex justify-center gap-6 text-sm mb-4">
                        <div className="text-green-600">
                          <span className="font-semibold">{geocodeResult.successful}</span> successful
                        </div>
                        <div className="text-amber-600">
                          <span className="font-semibold">{geocodeResult.failed}</span> not found
                        </div>
                      </div>
                      <p className="text-sm text-gray-600">
                        Latitude and Longitude columns have been added to your spreadsheet.
                      </p>
                    </div>
                  )}
                </div>

                {/* Dialog Footer */}
                <div className="flex justify-end gap-3 px-6 py-4 border-t border-gray-200 bg-gray-50">
                  {!geocoding && !geocodeResult && (
                    <>
                      <button
                        onClick={closeGeocodeDialog}
                        className="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={handleStartGeocoding}
                        disabled={!selectedAddressColumn}
                        className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                      >
                        <MapPin className="w-4 h-4" />
                        Start Geocoding
                      </button>
                    </>
                  )}

                  {geocoding && (
                    <button
                      onClick={handleCancelGeocoding}
                      className="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
                    >
                      Cancel
                    </button>
                  )}

                  {geocodeResult && (
                    <button
                      onClick={closeGeocodeDialog}
                      className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors"
                    >
                      Done
                    </button>
                  )}
                </div>
              </div>
            </div>
          )}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
