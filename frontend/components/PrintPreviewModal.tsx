"use client";

import { useState, useEffect, useMemo } from "react";
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import {
  Loader2,
  Plus,
  Minus,
  ChevronDown,
  ChevronRight,
  Download,
  X,
} from "lucide-react";
import { getPreview } from "@/lib/api";
import type { PreviewData } from "@/types";

interface PrintPreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  taskId: string;
  onDownload: () => void;
}

type PaperSize = "letter" | "legal" | "a4" | "a3";
type Orientation = "portrait" | "landscape";
type ScaleOption = "fit_to_width" | "fit_to_page" | "actual_size" | "custom";
type MarginPreset = "normal" | "narrow" | "wide" | "custom";

interface PrintSettings {
  paperSize: PaperSize;
  orientation: Orientation;
  scale: ScaleOption;
  customScale: number;
  margins: MarginPreset;
  topMargin: string;
  bottomMargin: string;
  leftMargin: string;
  rightMargin: string;
}

const PAPER_SIZES: Record<PaperSize, { label: string; width: number; height: number }> = {
  letter: { label: 'Letter (8.5" x 11")', width: 8.5, height: 11 },
  legal: { label: 'Legal (8.5" x 14")', width: 8.5, height: 14 },
  a4: { label: "A4 (210mm x 297mm)", width: 8.27, height: 11.69 },
  a3: { label: "A3 (297mm x 420mm)", width: 11.69, height: 16.54 },
};

const ROWS_PER_PAGE = 35;

export function PrintPreviewModal({
  isOpen,
  onClose,
  taskId,
  onDownload,
}: PrintPreviewModalProps) {
  const [previewData, setPreviewData] = useState<PreviewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [zoom, setZoom] = useState(100);
  const [formattingOpen, setFormattingOpen] = useState(false);
  const [headersFootersOpen, setHeadersFootersOpen] = useState(false);

  const [settings, setSettings] = useState<PrintSettings>({
    paperSize: "legal",
    orientation: "landscape",
    scale: "fit_to_width",
    customScale: 100,
    margins: "custom",
    topMargin: "1",
    bottomMargin: "1",
    leftMargin: "0.75",
    rightMargin: "0.75",
  });

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

  // Calculate pages based on data
  const pages = useMemo(() => {
    if (!previewData) return [];

    const allRows = previewData.rows;
    const pageCount = Math.ceil(allRows.length / ROWS_PER_PAGE);
    const result = [];

    for (let i = 0; i < pageCount; i++) {
      const startRow = i * ROWS_PER_PAGE;
      const endRow = Math.min(startRow + ROWS_PER_PAGE, allRows.length);
      result.push({
        pageNumber: i + 1,
        rows: allRows.slice(startRow, endRow),
        isFirst: i === 0,
      });
    }

    return result;
  }, [previewData]);

  const handleZoomIn = () => setZoom((prev) => Math.min(prev + 10, 200));
  const handleZoomOut = () => setZoom((prev) => Math.max(prev - 10, 25));

  const updateSetting = <K extends keyof PrintSettings>(
    key: K,
    value: PrintSettings[K]
  ) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
  };

  // Get page dimensions in pixels based on paper size and orientation
  const getPageDimensions = () => {
    const paper = PAPER_SIZES[settings.paperSize];
    const baseScale = 72; // base pixels per inch for preview
    let width = paper.width * baseScale;
    let height = paper.height * baseScale;

    if (settings.orientation === "landscape") {
      [width, height] = [height, width];
    }

    return { width, height };
  };

  const pageDimensions = getPageDimensions();

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-[95vw] w-[95vw] max-h-[95vh] h-[95vh] p-0 overflow-hidden flex flex-col bg-gray-100">
        <DialogTitle className="sr-only">Print Preview</DialogTitle>
        <DialogDescription className="sr-only">
          Preview and configure print settings for your Excel spreadsheet
        </DialogDescription>
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute right-4 top-4 z-50 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100"
        >
          <X className="h-5 w-5" />
          <span className="sr-only">Close</span>
        </button>

        <div className="flex flex-1 overflow-hidden">
          {/* Main Preview Area */}
          <div className="flex-1 overflow-auto bg-gray-200 p-8">
            {loading && (
              <div className="flex items-center justify-center h-full">
                <Loader2 className="h-8 w-8 text-blue-600 animate-spin" />
                <span className="ml-2 text-gray-600">Loading preview...</span>
              </div>
            )}

            {error && (
              <div className="flex items-center justify-center h-full text-red-600">
                <p>Failed to load preview: {error}</p>
              </div>
            )}

            {previewData && !loading && (
              <div
                className="flex flex-col items-center gap-8"
                style={{ transform: `scale(${zoom / 100})`, transformOrigin: "top center" }}
              >
                {pages.map((page) => (
                  <div
                    key={page.pageNumber}
                    className="bg-white shadow-lg relative"
                    style={{
                      width: pageDimensions.width,
                      minHeight: pageDimensions.height,
                      padding: "20px",
                      border: "1px dashed #4a90d9",
                    }}
                  >
                    {/* Page margins indicators */}
                    <div
                      className="absolute text-xs text-gray-400"
                      style={{ top: "4px", left: "50%", transform: "translateX(-50%)" }}
                    >
                      Top {settings.topMargin}&quot;
                    </div>
                    <div
                      className="absolute text-xs text-gray-400"
                      style={{ bottom: "4px", left: "50%", transform: "translateX(-50%)" }}
                    >
                      Bottom {settings.bottomMargin}&quot;
                    </div>
                    <div
                      className="absolute text-xs text-gray-400"
                      style={{ left: "4px", top: "50%", transform: "translateY(-50%) rotate(-90deg)" }}
                    >
                      Left {settings.leftMargin}&quot;
                    </div>
                    <div
                      className="absolute text-xs text-gray-400"
                      style={{ right: "4px", top: "50%", transform: "translateY(-50%) rotate(90deg)" }}
                    >
                      Right {settings.rightMargin}&quot;
                    </div>

                    {/* Title (only on first page) */}
                    {page.isFirst && (
                      <div className="text-center mb-4 border-b border-gray-300 pb-2">
                        <h2 className="font-bold text-sm">FORM 20 - FINAL RESULT SHEET</h2>
                        <p className="text-xs text-gray-600">GENERAL ELECTIONS TO LOK SABHA</p>
                        <p className="text-xs text-gray-500">
                          Total No. of Electors: {previewData.total_rows.toLocaleString()}
                        </p>
                      </div>
                    )}

                    {/* Table */}
                    <div className="overflow-hidden">
                      <table className="w-full text-[8px] border-collapse">
                        <thead>
                          <tr>
                            {previewData.headers.map((header, idx) => (
                              <th
                                key={idx}
                                className="border border-gray-400 bg-[#366092] text-white px-1 py-1 text-center font-bold"
                                style={{ maxWidth: "60px", overflow: "hidden", textOverflow: "ellipsis" }}
                              >
                                {header}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {page.rows.map((row, rowIdx) => (
                            <tr key={rowIdx} className={rowIdx % 2 === 0 ? "bg-white" : "bg-gray-50"}>
                              {row.map((cell, cellIdx) => (
                                <td
                                  key={cellIdx}
                                  className="border border-gray-300 px-1 py-0.5 text-center"
                                  style={{ maxWidth: "60px", overflow: "hidden", textOverflow: "ellipsis" }}
                                >
                                  {cell !== null ? String(cell) : ""}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>

                    {/* Page number */}
                    <div className="absolute bottom-2 right-4 text-xs text-gray-500">
                      Page {page.pageNumber} of {pages.length}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Right Settings Panel */}
          <div className="w-72 bg-white border-l border-gray-200 flex flex-col overflow-y-auto">
            <div className="p-4 space-y-6">
              {/* Export */}
              <div>
                <label className="block text-sm font-medium text-gray-500 mb-2">Export</label>
                <div className="relative">
                  <select
                    className="w-full appearance-none bg-white border border-gray-300 rounded px-3 py-2 pr-8 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    defaultValue="workbook"
                  >
                    <option value="workbook">Workbook</option>
                    <option value="current_sheet">Current Sheet</option>
                  </select>
                  <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
                </div>
              </div>

              {/* Selection */}
              <div>
                <label className="block text-sm font-medium text-gray-500 mb-2">Selection</label>
                <div className="relative">
                  <select
                    className="w-full appearance-none bg-white border border-gray-300 rounded px-3 py-2 pr-8 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    defaultValue="all_sheets"
                  >
                    <option value="all_sheets">All sheets</option>
                    <option value="current_sheet">Current sheet</option>
                    <option value="selected_cells">Selected cells</option>
                  </select>
                  <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
                </div>
              </div>

              {/* Paper size */}
              <div>
                <label className="block text-sm font-medium text-gray-500 mb-2">Paper size</label>
                <div className="relative">
                  <select
                    className="w-full appearance-none bg-white border border-gray-300 rounded px-3 py-2 pr-8 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    value={settings.paperSize}
                    onChange={(e) => updateSetting("paperSize", e.target.value as PaperSize)}
                  >
                    {Object.entries(PAPER_SIZES).map(([key, { label }]) => (
                      <option key={key} value={key}>
                        {label}
                      </option>
                    ))}
                  </select>
                  <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
                </div>
              </div>

              {/* Page orientation */}
              <div>
                <label className="block text-sm font-medium text-gray-500 mb-2">Page orientation</label>
                <div className="flex gap-6">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="orientation"
                      checked={settings.orientation === "landscape"}
                      onChange={() => updateSetting("orientation", "landscape")}
                      className="w-4 h-4 text-blue-600"
                    />
                    <span className="text-sm">Landscape</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="orientation"
                      checked={settings.orientation === "portrait"}
                      onChange={() => updateSetting("orientation", "portrait")}
                      className="w-4 h-4 text-blue-600"
                    />
                    <span className="text-sm">Portrait</span>
                  </label>
                </div>
              </div>

              {/* Scale */}
              <div>
                <label className="block text-sm font-medium text-gray-500 mb-2">Scale</label>
                <div className="relative">
                  <select
                    className="w-full appearance-none bg-white border border-gray-300 rounded px-3 py-2 pr-8 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    value={settings.scale}
                    onChange={(e) => updateSetting("scale", e.target.value as ScaleOption)}
                  >
                    <option value="fit_to_width">Fit to width</option>
                    <option value="fit_to_page">Fit to page</option>
                    <option value="actual_size">Actual size (100%)</option>
                    <option value="custom">Custom</option>
                  </select>
                  <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
                </div>
              </div>

              {/* Margins */}
              <div>
                <label className="block text-sm font-medium text-gray-500 mb-2">Margins</label>
                <div className="relative">
                  <select
                    className="w-full appearance-none bg-white border border-gray-300 rounded px-3 py-2 pr-8 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    value={settings.margins}
                    onChange={(e) => updateSetting("margins", e.target.value as MarginPreset)}
                  >
                    <option value="normal">Normal</option>
                    <option value="narrow">Narrow</option>
                    <option value="wide">Wide</option>
                    <option value="custom">Custom numbers</option>
                  </select>
                  <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
                </div>
              </div>

              {/* Custom Page Breaks Button */}
              <button className="w-full text-sm text-blue-600 hover:text-blue-800 font-medium py-2 border border-gray-200 rounded hover:bg-gray-50 transition-colors">
                SET CUSTOM PAGE BREAKS
              </button>

              {/* Formatting Section */}
              <div className="border-t border-gray-200 pt-4">
                <button
                  onClick={() => setFormattingOpen(!formattingOpen)}
                  className="flex items-center justify-between w-full text-sm font-medium text-gray-700 hover:text-gray-900"
                >
                  <span>Formatting</span>
                  {formattingOpen ? (
                    <ChevronDown className="h-4 w-4" />
                  ) : (
                    <ChevronRight className="h-4 w-4" />
                  )}
                </button>
                {formattingOpen && (
                  <div className="mt-3 space-y-3 pl-2">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input type="checkbox" defaultChecked className="w-4 h-4 text-blue-600 rounded" />
                      <span className="text-sm text-gray-600">Show gridlines</span>
                    </label>
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input type="checkbox" defaultChecked className="w-4 h-4 text-blue-600 rounded" />
                      <span className="text-sm text-gray-600">Show row and column headings</span>
                    </label>
                  </div>
                )}
              </div>

              {/* Headers & footers Section */}
              <div className="border-t border-gray-200 pt-4">
                <button
                  onClick={() => setHeadersFootersOpen(!headersFootersOpen)}
                  className="flex items-center justify-between w-full text-sm font-medium text-gray-700 hover:text-gray-900"
                >
                  <span>Headers & footers</span>
                  {headersFootersOpen ? (
                    <ChevronDown className="h-4 w-4" />
                  ) : (
                    <ChevronRight className="h-4 w-4" />
                  )}
                </button>
                {headersFootersOpen && (
                  <div className="mt-3 space-y-3 pl-2">
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">Header</label>
                      <input
                        type="text"
                        placeholder="Enter header text"
                        className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">Footer</label>
                      <input
                        type="text"
                        placeholder="Enter footer text"
                        className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Download Button at bottom of panel */}
            <div className="mt-auto p-4 border-t border-gray-200">
              <Button
                onClick={onDownload}
                className="w-full gap-2"
                disabled={loading || !!error}
              >
                <Download className="h-4 w-4" />
                Download Excel
              </Button>
            </div>
          </div>
        </div>

        {/* Zoom Controls - Bottom Right */}
        <div className="absolute bottom-4 right-80 flex items-center gap-1 bg-white rounded-full shadow-lg border border-gray-200">
          <button
            onClick={handleZoomIn}
            className="p-2 hover:bg-gray-100 rounded-l-full transition-colors"
            title="Zoom in"
          >
            <Plus className="h-5 w-5 text-gray-600" />
          </button>
          <span className="px-2 text-sm text-gray-600 min-w-[50px] text-center">{zoom}%</span>
          <button
            onClick={handleZoomOut}
            className="p-2 hover:bg-gray-100 rounded-r-full transition-colors"
            title="Zoom out"
          >
            <Minus className="h-5 w-5 text-gray-600" />
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
