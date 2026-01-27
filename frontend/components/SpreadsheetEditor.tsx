"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { Button } from "@/components/ui/button";
import {
  Loader2,
  Download,
  X,
  FileSpreadsheet,
  Columns,
} from "lucide-react";
import { getFullPreview, downloadModifiedExcel } from "@/lib/api";
import type { FullPreviewData, CellValue } from "@/types";
import { Workbook } from "@fortune-sheet/react";
import "@fortune-sheet/react/dist/index.css";

interface SpreadsheetEditorProps {
  isOpen: boolean;
  onClose: () => void;
  taskId: string;
  filename: string;
  onFilterColumns?: () => void;
}

// Fix reversed/mirrored text that sometimes appears in PDFs
function fixReversedText(text: string): string {
  if (!text || typeof text !== 'string') return text;
  
  const trimmed = text.trim();
  if (trimmed.length < 2) return trimmed;
  
  // Known reversed patterns
  const reversedPatterns = [
    '.ON .LS',      // SL. NO.
    '.oN .lS',      // Sl. No.
    'oN noitatS gnilloP',  // Polling Station No
    'noitatS gnilloP',     // Polling Station
    'ATON',         // NOTA
    'LATOT',        // TOTAL
  ];
  
  // Check if text matches known reversed patterns
  for (const pattern of reversedPatterns) {
    if (trimmed.toLowerCase().includes(pattern.toLowerCase())) {
      return trimmed.split('').reverse().join('');
    }
  }
  
  // Check if starts with punctuation but reversed version doesn't
  const reversed = trimmed.split('').reverse().join('');
  if (trimmed[0] === '.' && reversed[0] !== '.') {
    // Check if reversed version looks more natural
    if (/^[A-Z]/.test(reversed)) {
      return reversed;
    }
  }
  
  return trimmed;
}

// Calculate optimal column width based on content
function calculateColumnWidth(header: string, rows: CellValue[][], colIndex: number): number {
  // Start with header length
  let maxLength = String(header).length;

  // Check all rows for max content length (sample every nth row for large datasets)
  const sampleInterval = rows.length > 500 ? Math.floor(rows.length / 100) : 1;
  for (let i = 0; i < rows.length; i += sampleInterval) {
    const cell = rows[i]?.[colIndex];
    if (cell !== null && cell !== undefined) {
      maxLength = Math.max(maxLength, String(cell).length);
    }
  }

  // Convert character count to pixel width (approx 8px per char + padding)
  const width = Math.max(80, Math.min(300, maxLength * 9 + 20));
  return width;
}

// Convert API data to Fortune Sheet format
function convertToFortuneSheetData(
  headers: string[],
  rows: CellValue[][],
  documentTitle?: string
) {
  const cellData: Array<{ r: number; c: number; v: { v: string | number | null; m: string; bg?: string; fc?: string; bl?: number } }> = [];

  // Fix reversed text in headers before displaying
  const fixedHeaders = headers.map(header => fixReversedText(String(header)));

  // Add header row (row 0) with styling
  fixedHeaders.forEach((header, colIndex) => {
    cellData.push({
      r: 0,
      c: colIndex,
      v: {
        v: header,
        m: String(header),
        bg: "#366092",  // Blue background for headers
        fc: "#FFFFFF",  // White text
        bl: 1,          // Bold
      },
    });
  });

  // Add data rows (starting from row 1)
  rows.forEach((row, rowIndex) => {
    row.forEach((cell, colIndex) => {
      if (cell !== null && cell !== undefined && cell !== "") {
        cellData.push({
          r: rowIndex + 1,
          c: colIndex,
          v: {
            v: cell,
            m: String(cell),
          },
        });
      }
    });
  });

  // Calculate optimal column widths
  const columnWidths: Record<number, number> = {};
  headers.forEach((header, idx) => {
    columnWidths[idx] = calculateColumnWidth(header, rows, idx);
  });

  // Add buffer rows/columns to allow editing beyond current data
  // Fortune Sheet uses these to determine the visible/editable area
  const totalRows = Math.max(rows.length + 100, 500); // At least 500 rows or data + 100
  const totalColumns = Math.max(headers.length + 10, 26); // At least 26 columns (A-Z) or data + 10

  return [
    {
      name: documentTitle || "Sheet1",
      celldata: cellData,
      row: totalRows,
      column: totalColumns,
      config: {
        columnlen: columnWidths,
        rowlen: { 0: 30 }, // Header row height
      },
      frozen: {
        type: "row",
        range: { row_focus: 0, column_focus: 0 },
      },
    },
  ];
}

// Extract data from Fortune Sheet format back to arrays
function extractFromFortuneSheet(sheetData: any[]): {
  headers: string[];
  rows: CellValue[][];
} {
  if (!sheetData || sheetData.length === 0) {
    return { headers: [], rows: [] };
  }

  const sheet = sheetData[0];

  // Fortune Sheet can store data in 'data' (2D array) or 'celldata' (sparse) format
  // After editing, data is typically in 'data' format
  let data = sheet.data;

  // If data is not available, try to reconstruct from celldata
  if (!data || data.length === 0) {
    if (sheet.celldata && sheet.celldata.length > 0) {
      // Find max row and column from celldata
      let maxRow = 0;
      let maxCol = 0;
      for (const cell of sheet.celldata) {
        maxRow = Math.max(maxRow, cell.r);
        maxCol = Math.max(maxCol, cell.c);
      }

      // Create 2D array from celldata
      data = Array(maxRow + 1).fill(null).map(() => Array(maxCol + 1).fill(null));
      for (const cell of sheet.celldata) {
        data[cell.r][cell.c] = cell.v;
      }
    } else {
      return { headers: [], rows: [] };
    }
  }

  if (data.length === 0) {
    return { headers: [], rows: [] };
  }

  // Find actual data bounds (skip empty rows/columns at the end)
  let maxColWithData = 0;
  let maxRowWithData = 0;

  for (let row = 0; row < data.length; row++) {
    const dataRow = data[row];
    if (!dataRow) continue;
    for (let col = 0; col < dataRow.length; col++) {
      const cell = dataRow[col];
      const value = cell?.v ?? cell?.m ?? cell;
      if (value !== null && value !== undefined && value !== '') {
        maxColWithData = Math.max(maxColWithData, col);
        maxRowWithData = Math.max(maxRowWithData, row);
      }
    }
  }

  // First row is headers
  const headers: string[] = [];
  const firstRow = data[0] || [];
  for (let col = 0; col <= maxColWithData; col++) {
    const cell = firstRow[col];
    // Handle different cell formats from Fortune Sheet
    const value = cell?.v ?? cell?.m ?? cell;
    if (value !== undefined && value !== null && value !== '') {
      headers.push(String(value));
    } else {
      headers.push(`Column ${col + 1}`);
    }
  }

  // Remaining rows are data (only include rows with actual data)
  const rows: CellValue[][] = [];
  for (let row = 1; row <= maxRowWithData; row++) {
    const rowData: CellValue[] = [];
    const dataRow = data[row] || [];

    // Check if row has any data
    let hasData = false;
    for (let col = 0; col <= maxColWithData; col++) {
      const cell = dataRow[col];
      const value = cell?.v ?? cell?.m ?? cell;
      if (value !== null && value !== undefined && value !== '') {
        hasData = true;
        break;
      }
    }

    if (!hasData) continue; // Skip empty rows

    for (let col = 0; col < headers.length; col++) {
      const cell = dataRow[col];
      // Handle different cell formats from Fortune Sheet
      const value = cell?.v ?? cell?.m ?? cell;
      if (value !== undefined && value !== null) {
        rowData.push(value);
      } else {
        rowData.push(null);
      }
    }
    rows.push(rowData);
  }

  return { headers, rows };
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
  const [sheetData, setSheetData] = useState<any[]>([]);
  const workbookRef = useRef<any>(null);

  useEffect(() => {
    if (isOpen && taskId) {
      setLoading(true);
      setError(null);

      getFullPreview(taskId)
        .then((data) => {
          console.log('[SpreadsheetEditor] API Response:', {
            totalRows: data.total_rows,
            totalColumns: data.total_columns,
            headersCount: data.headers?.length,
            rowsCount: data.rows?.length,
          });
          setPreviewData(data);
          const fortuneData = convertToFortuneSheetData(
            data.headers,
            data.rows,
            data.document_title
          );
          console.log('[SpreadsheetEditor] Fortune Sheet data:', {
            sheetName: fortuneData[0]?.name,
            cellDataCount: fortuneData[0]?.celldata?.length,
            configuredRows: fortuneData[0]?.row,
            configuredColumns: fortuneData[0]?.column,
          });
          setSheetData(fortuneData);
        })
        .catch((err) => setError(err.message))
        .finally(() => setLoading(false));
    }
  }, [isOpen, taskId]);

  const handleDownload = useCallback(async () => {
    if (!taskId || !previewData || !sheetData.length) return;

    setDownloading(true);
    try {
      // Extract the current data from Fortune Sheet
      const { headers, rows } = extractFromFortuneSheet(sheetData);
      
      await downloadModifiedExcel(
        taskId,
        headers.length > 0 ? headers : previewData.headers,
        rows.length > 0 ? rows : previewData.rows,
        filename,
        previewData.document_title
      );
    } catch (err) {
      console.error("Download failed:", err);
      setError(err instanceof Error ? err.message : "Download failed");
    } finally {
      setDownloading(false);
    }
  }, [taskId, previewData, sheetData, filename]);

  const handleSheetChange = useCallback((data: any[]) => {
    setSheetData(data);
  }, []);

  return (
    <DialogPrimitive.Root open={isOpen} onOpenChange={onClose}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/50" />
        <DialogPrimitive.Content 
          className="fixed inset-0 z-50 bg-white flex flex-col"
          style={{ width: '100vw', height: '100vh', maxWidth: '100vw', maxHeight: '100vh' }}
          aria-describedby="spreadsheet-description"
        >
          {/* Accessible title and description */}
          <DialogPrimitive.Title className="sr-only">
            {previewData?.document_title || filename || "Spreadsheet Editor"}
          </DialogPrimitive.Title>
          <DialogPrimitive.Description id="spreadsheet-description" className="sr-only">
            {previewData ? `Edit and download spreadsheet with ${previewData.total_rows} rows and ${previewData.total_columns} columns` : "Loading spreadsheet data"}
          </DialogPrimitive.Description>

          {/* Header */}
          <div className="flex items-center justify-between px-4 py-2 border-b bg-gray-50 shrink-0">
            <div className="flex items-center gap-3">
              <FileSpreadsheet className="h-6 w-6 text-green-600" />
              <div>
                <h2 className="font-semibold text-gray-800 text-sm">
                  {previewData?.document_title || filename || "Spreadsheet Editor"}
                </h2>
                {previewData && (
                  <p className="text-xs text-gray-500">
                    {previewData.total_rows} rows × {previewData.total_columns} columns
                  </p>
                )}
              </div>
            </div>
            <div className="flex items-center gap-2">
              {onFilterColumns && previewData && (
                <Button
                  onClick={onFilterColumns}
                  variant="outline"
                  disabled={loading || !!error}
                  className="gap-2 h-8 text-sm"
                >
                  <Columns className="h-4 w-4" />
                  Filter Columns
                </Button>
              )}
              <Button
                onClick={handleDownload}
                disabled={loading || !!error || downloading}
                className="gap-2 bg-green-600 hover:bg-green-700 h-8 text-sm"
              >
                {downloading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Download className="h-4 w-4" />
                )}
                Download Excel
              </Button>
              <button
                onClick={onClose}
                className="p-1.5 rounded-md hover:bg-gray-200 transition-colors"
              >
                <X className="h-5 w-5 text-gray-500" />
              </button>
            </div>
          </div>

          {/* Spreadsheet Area */}
          <div className="flex-1 overflow-hidden" style={{ height: 'calc(100vh - 52px)' }}>
            {loading && (
              <div className="flex items-center justify-center h-full bg-gray-50">
                <div className="text-center">
                  <Loader2 className="h-12 w-12 text-green-600 animate-spin mx-auto mb-4" />
                  <p className="text-gray-600 font-medium">Loading spreadsheet data...</p>
                  <p className="text-sm text-gray-500 mt-1">This may take a moment for large files</p>
                </div>
              </div>
            )}

            {error && (
              <div className="flex items-center justify-center h-full bg-gray-50">
                <div className="text-center max-w-md">
                  <div className="w-16 h-16 rounded-full bg-red-100 flex items-center justify-center mx-auto mb-4">
                    <X className="h-8 w-8 text-red-600" />
                  </div>
                  <h3 className="text-lg font-semibold text-gray-800 mb-2">Failed to Load</h3>
                  <p className="text-red-600">{error}</p>
                  <Button onClick={onClose} variant="outline" className="mt-4">
                    Close
                  </Button>
                </div>
              </div>
            )}

            {!loading && !error && sheetData.length > 0 && (
              <div style={{ width: '100%', height: '100%' }}>
                <Workbook
                  ref={workbookRef}
                  data={sheetData}
                  onChange={handleSheetChange}
                  showToolbar={true}
                  showFormulaBar={true}
                  showSheetTabs={false}
                  allowEdit={true}
                />
              </div>
            )}
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

