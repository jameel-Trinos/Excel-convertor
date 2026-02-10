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
  Languages,
  ChevronDown,
  Edit,
  Users,
  RotateCcw,
} from "lucide-react";
import { AllianceModal } from "@/components/AllianceModal";
import { ALLIANCE_CONFIG, ASSEMBLY_ALLIANCE_CONFIG } from "@/lib/allianceConfig";
import {
  getFullPreview,
  downloadModifiedExcel,
  startGeocoding,
  subscribeToGeocodeProgress,
  applyGeocoding,
  cancelGeocoding,
  addBoothNameColumn,
} from "@/lib/api";
import {
  startTranslation,
  subscribeToTranslateProgress,
  downloadTranslatedExcel,
  getTranslateStatus,
  getTranslatedFullPreview,
} from "@/lib/translation-api";
import type {
  FullPreviewData,
  CellValue,
  GeocodeProgressEvent,
  TranslateProgressEvent,
  Language,
} from "@/types";

function safeNumber(val: CellValue): number {
  if (val === null || val === undefined || val === "") return 0;
  const n = Number(val);
  return isNaN(n) ? 0 : n;
}

interface SpreadsheetEditorProps {
  isOpen: boolean;
  onClose: () => void;
  taskId: string;
  filename: string;
  onFilterColumns?: () => void;
  isBoothView?: boolean;
  onColumnsChange?: (columns: string[]) => void;
  onDataChange?: (data: { headers: string[]; rows: CellValue[][] }) => void;
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
  isBoothView = false,
  onColumnsChange,
  onDataChange,
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

  // Translation state
  const [currentLanguage, setCurrentLanguage] = useState<Language>("original");
  const [translating, setTranslating] = useState(false);
  const [translationProgress, setTranslationProgress] = useState(0);
  const [translationProgressMessage, setTranslationProgressMessage] = useState("");
  const [showLanguageDropdown, setShowLanguageDropdown] = useState(false);
  const [availableTranslations, setAvailableTranslations] = useState({
    tamil: false,
    hindi: false,
    english: false,
  });
  const translateUnsubscribeRef = useRef<(() => void) | null>(null);
  const languageDropdownRef = useRef<HTMLDivElement>(null);

  // Booth name column state
  const [boothNameDialogOpen, setBoothNameDialogOpen] = useState(false);
  const [selectedSourceColumn, setSelectedSourceColumn] = useState<string>("");
  const [addingBoothName, setAddingBoothName] = useState(false);

  // Alliance state
  const [allianceModalOpen, setAllianceModalOpen] = useState(false);
  const [allianceDropdownOpen, setAllianceDropdownOpen] = useState(false);
  const [selectedAllianceType, setSelectedAllianceType] = useState<"loksabha" | "assembly" | null>(null);
  const [preAllianceData, setPreAllianceData] = useState<{
    headers: string[];
    rows: CellValue[][];
  } | null>(null);
  const [allianceApplied, setAllianceApplied] = useState(false);
  const [allianceWarnings, setAllianceWarnings] = useState<string[]>([]);
  const allianceDropdownRef = useRef<HTMLDivElement>(null);

  // Fetch preview data when modal opens or language changes
  useEffect(() => {
    if (isOpen && taskId) {
      // Don't refetch if we have alliance data or local edits (preserve user changes)
      if (allianceApplied || preAllianceData) {
        console.log("SpreadsheetEditor - Skipping refetch (alliance data exists)");
        setLoading(false); // Ensure loading is false so table renders
        setError(null);
        return;
      }

      setLoading(true);
      setError(null);

      const loadPreview = async () => {
        try {
          let data: FullPreviewData;
          if (currentLanguage === "original") {
            data = await getFullPreview(taskId);
          } else {
            data = await getTranslatedFullPreview(taskId, currentLanguage);
          }
          setPreviewData(data);
          setEditedData({
            headers: [...data.headers],
            rows: data.rows.map(row => [...row]),
          });
        } catch (err) {
          setError(err instanceof Error ? err.message : "Failed to load preview");
        } finally {
          setLoading(false);
        }
      };

      loadPreview();
    }
  }, [isOpen, taskId, currentLanguage, allianceApplied, preAllianceData]);

  // Check available translations when modal opens
  useEffect(() => {
    if (isOpen && taskId) {
      getTranslateStatus(taskId)
        .then((status) => {
          setAvailableTranslations({
            tamil: status.has_tamil_version,
            hindi: status.has_hindi_version,
            english: status.has_english_version,
          });
        })
        .catch((err) => {
          console.error("Failed to get translation status:", err);
        });
    }
  }, [isOpen, taskId]);

  // Notify parent of data changes (for alliance → filter flow)
  useEffect(() => {
    if (editedData && onDataChange) {
      onDataChange(editedData);
    }
  }, [editedData, onDataChange]);

  // Close language dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (languageDropdownRef.current && !languageDropdownRef.current.contains(event.target as Node)) {
        setShowLanguageDropdown(false);
      }
    }

    if (showLanguageDropdown) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => {
        document.removeEventListener("mousedown", handleClickOutside);
      };
    }
  }, [showLanguageDropdown]);

  // Close alliance dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (allianceDropdownRef.current && !allianceDropdownRef.current.contains(event.target as Node)) {
        setAllianceDropdownOpen(false);
      }
    }

    if (allianceDropdownOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => {
        document.removeEventListener("mousedown", handleClickOutside);
      };
    }
  }, [allianceDropdownOpen]);

  // Cleanup translation subscription on unmount
  useEffect(() => {
    return () => {
      if (translateUnsubscribeRef.current) {
        translateUnsubscribeRef.current();
      }
    };
  }, []);

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

  // Alliance: apply alliance vote sums
  // allianceMap: { mainPartyColumnHeader: [allyColumnHeader, ...] }
  // 1. Sum alliance columns into main party column (create column if missing)
  // 2. Remove the alliance columns from the table
  const handleApplyAlliance = useCallback(
    async (allianceMap: Record<string, string[]>) => {
      console.log("SpreadsheetEditor - Received Alliance Map:", allianceMap);
      console.log("SpreadsheetEditor - Current Headers:", editedData?.headers);

      if (!editedData) {
        console.error("SpreadsheetEditor - Cannot apply alliance: editedData is null");
        return;
      }

      // Snapshot current data for reset
      setPreAllianceData({
        headers: editedData.headers.map((h) => h),
        rows: editedData.rows.map((row) => [...row]),
      });
      setAllianceWarnings([]);

      // Client-side alliance logic
      // Sums alliance party votes into main party column, then removes alliance columns.
      let newHeaders = [...editedData.headers];
      let newRows = editedData.rows.map((row) => [...row]);
      const columnsToRemove = new Set<string>();

      for (const [mainCol, allyCols] of Object.entries(allianceMap)) {
        let mainIdx = newHeaders.indexOf(mainCol);
        if (mainIdx === -1) {
          // Main party column not in data — create new column
          console.log(`SpreadsheetEditor - Creating new column: ${mainCol}`);
          newHeaders = [...newHeaders, mainCol];
          mainIdx = newHeaders.length - 1;
          newRows = newRows.map((row) => [...row, 0]);
        } else {
          console.log(`SpreadsheetEditor - Using existing column: ${mainCol} at index ${mainIdx}`);
        }

        for (let r = 0; r < newRows.length; r++) {
          let mainVal = safeNumber(newRows[r][mainIdx]);
          for (const allyCol of allyCols) {
            const allyIdx = newHeaders.indexOf(allyCol);
            if (allyIdx === -1) {
              console.warn(`SpreadsheetEditor - Alliance column not found: ${allyCol}`);
              continue;
            }
            const allyVal = safeNumber(newRows[r][allyIdx]);
            mainVal += allyVal;
          }
          newRows[r][mainIdx] = mainVal;
        }
        // Mark alliance columns for removal
        for (const allyCol of allyCols) {
          if (newHeaders.indexOf(allyCol) !== -1) {
            columnsToRemove.add(allyCol);
          }
        }
      }

      // Remove alliance columns
      if (columnsToRemove.size > 0) {
        const keepIndices = newHeaders
          .map((h, i) => ({ h, i }))
          .filter(({ h }) => !columnsToRemove.has(h))
          .map(({ i }) => i);
        newHeaders = keepIndices.map((i) => newHeaders[i]);
        newRows = newRows.map((row) => keepIndices.map((i) => row[i]));
      }

      const updatedData = { headers: newHeaders, rows: newRows };
      console.log("SpreadsheetEditor - Updated Headers:", newHeaders);
      console.log("SpreadsheetEditor - Columns Removed:", Array.from(columnsToRemove));
      console.log("SpreadsheetEditor - Alliance applied successfully. Rows:", newRows.length);

      setEditedData(updatedData);
      setAllianceApplied(true);
      onColumnsChange?.(newHeaders);
      onDataChange?.(updatedData);  // ✅ CRITICAL: Notify parent of data change

      console.log("SpreadsheetEditor - State updated: allianceApplied=true, editedData rows=", updatedData.rows.length);
    },
    [editedData, taskId, onColumnsChange, onDataChange]
  );

  // Alliance: reset to pre-alliance data
  const handleResetAlliance = useCallback(() => {
    if (!preAllianceData) return;
    setEditedData({
      headers: preAllianceData.headers.map((h) => h),
      rows: preAllianceData.rows.map((row) => [...row]),
    });
    setPreAllianceData(null);
    setAllianceApplied(false);
    setAllianceWarnings([]);
    onColumnsChange?.(preAllianceData.headers);
  }, [preAllianceData, onColumnsChange]);

  // Download Excel with edited data
  const handleDownload = useCallback(async () => {
    if (!taskId || !editedData) return;

    setDownloading(true);
    try {
      // If current language is not original, download translated version
      if (currentLanguage !== "original") {
        await downloadTranslatedExcel(taskId, currentLanguage, filename);
      } else {
        await downloadModifiedExcel(
          taskId,
          editedData.headers,
          editedData.rows,
          filename,
          previewData?.document_title
        );
      }
    } catch (err) {
      console.error("Download failed:", err);
      setError(err instanceof Error ? err.message : "Download failed");
    } finally {
      setDownloading(false);
    }
  }, [taskId, editedData, filename, previewData, currentLanguage]);

  // Language options
  const LANGUAGE_OPTIONS: { value: Language; label: string; emoji: string }[] = [
    { value: "original", label: "English (Original)", emoji: "🇬🇧" },
    { value: "tamil", label: "Tamil", emoji: "தமிழ்" },
    { value: "hindi", label: "Hindi", emoji: "हिंदी" },
    { value: "english", label: "English", emoji: "English" },
  ];

  // Translation handlers
  const handleLanguageSelect = useCallback(
    async (targetLang: Language) => {
      setShowLanguageDropdown(false);

      if (targetLang === currentLanguage) {
        return;
      }

      // If switching to original, just update state
      if (targetLang === "original") {
        setCurrentLanguage("original");
        return;
      }

      // If translation exists, just switch
      if (availableTranslations[targetLang]) {
        setCurrentLanguage(targetLang);
        return;
      }

      // Need to translate
      setTranslating(true);
      setTranslationProgress(0);
      setTranslationProgressMessage("Starting translation...");

      try {
        const response = await startTranslation(taskId, targetLang);

        // Check if it's a cached response
        if (response.translate_task_id.startsWith("cached_")) {
          setTranslating(false);
          setAvailableTranslations((prev) => ({ ...prev, [targetLang]: true }));
          setCurrentLanguage(targetLang);
          return;
        }

        // Subscribe to progress
        const unsubscribe = subscribeToTranslateProgress(
          response.translate_task_id,
          (event: TranslateProgressEvent) => {
            const progressPercent =
              event.total > 0 ? (event.current / event.total) * 100 : 0;
            setTranslationProgress(progressPercent);
            setTranslationProgressMessage(event.message);
          },
          async () => {
            // Complete
            setTranslating(false);
            setAvailableTranslations((prev) => ({ ...prev, [targetLang]: true }));
            setCurrentLanguage(targetLang);
            if (translateUnsubscribeRef.current) {
              translateUnsubscribeRef.current();
              translateUnsubscribeRef.current = null;
            }
            // Refresh translation status
            try {
              const status = await getTranslateStatus(taskId);
              setAvailableTranslations({
                tamil: status.has_tamil_version,
                hindi: status.has_hindi_version,
                english: status.has_english_version,
              });
            } catch (err) {
              console.error("Failed to refresh translation status:", err);
            }
          },
          (err: Error) => {
            // Error
            console.error("Translation failed:", err);
            setTranslationProgressMessage(`Error: ${err.message}`);
            setTranslating(false);
            if (translateUnsubscribeRef.current) {
              translateUnsubscribeRef.current();
              translateUnsubscribeRef.current = null;
            }
          }
        );

        translateUnsubscribeRef.current = unsubscribe;
      } catch (err) {
        console.error("Failed to start translation:", err);
        setTranslationProgressMessage(err instanceof Error ? err.message : "Translation failed");
        setTranslating(false);
      }
    },
    [taskId, currentLanguage, availableTranslations]
  );

  const getCurrentLanguageDisplay = () => {
    const option = LANGUAGE_OPTIONS.find((opt) => opt.value === currentLanguage);
    return option ? `${option.emoji} ${option.label}` : "Select Language";
  };

  // Geocoding handlers
  const openGeocodeDialog = useCallback(() => {
    if (editedData && editedData.headers.length > 0) {
      // Try to auto-select the address column with better detection
      const addressKeywords = [
        "address", "location", "building", "place", "area", 
        "street", "road", "venue", "site", "premises"
      ];
      
      // First, try exact matches or strong keyword matches
      let addressColumnIndex = editedData.headers.findIndex((h) => {
        const headerLower = h.toLowerCase();
        return addressKeywords.some(keyword => 
          headerLower.includes(keyword) || 
          headerLower === keyword ||
          headerLower.startsWith(keyword + " ") ||
          headerLower.endsWith(" " + keyword)
        );
      });
      
      // If no match found, use first column as fallback
      if (addressColumnIndex < 0) {
        addressColumnIndex = 0;
      }
      
      setSelectedAddressColumn(editedData.headers[addressColumnIndex]);
    } else {
      // If no data, set empty string
      setSelectedAddressColumn("");
    }
    setGeocodeResult(null);
    setGeocodeProgress(null);
    setError(null); // Clear any previous errors
    setGeocodeDialogOpen(true);
  }, [editedData]);

  const handleStartGeocoding = useCallback(async () => {
    if (!taskId || !editedData || !selectedAddressColumn) {
      setError("Missing required data. Please ensure the spreadsheet is loaded.");
      return;
    }

    // Validate that selected column exists
    if (!editedData.headers.includes(selectedAddressColumn)) {
      setError(`Column "${selectedAddressColumn}" not found in the spreadsheet.`);
      return;
    }

    setGeocoding(true);
    setGeocodeResult(null);
    setGeocodeProgress(null);
    setError(null); // Clear previous errors

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
          // Clear error on successful progress update
          if (event.status === "geocoding") {
            setError(null);
          }
        },
        async (event) => {
          // Geocoding completed - apply results
          try {
            if (event.status === "failed") {
              setError(event.message || "Geocoding failed. Please try again.");
              setGeocoding(false);
              return;
            }

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
            const errorMessage = err instanceof Error ? err.message : "Failed to apply geocoding results";
            setError(errorMessage);
          } finally {
            setGeocoding(false);
          }
        },
        (err) => {
          console.error("Geocoding error:", err);
          setError(err.message || "An error occurred during geocoding. Please try again.");
          setGeocoding(false);
        }
      );

      geocodeUnsubscribeRef.current = unsubscribe;
    } catch (err) {
      console.error("Failed to start geocoding:", err);
      const errorMessage = err instanceof Error 
        ? err.message 
        : "Failed to start geocoding. Please check your connection and try again.";
      setError(errorMessage);
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

  // Booth name column handlers
  const handleAddBoothNameColumn = useCallback(async () => {
    if (!taskId || !editedData || !selectedSourceColumn) {
      setError("Missing required data. Please ensure the spreadsheet is loaded and a column is selected.");
      return;
    }

    // Validate that selected column exists
    if (!editedData.headers.includes(selectedSourceColumn)) {
      setError(`Column "${selectedSourceColumn}" not found in the spreadsheet.`);
      return;
    }

    setAddingBoothName(true);
    setError(null);

    try {
      const result = await addBoothNameColumn(taskId, selectedSourceColumn);

      // Update the spreadsheet data with new column
      setEditedData({
        headers: result.headers,
        rows: result.rows,
      });

      // Update preview data
      setPreviewData(result);

      // Close dialog
      setBoothNameDialogOpen(false);
    } catch (err) {
      console.error("Failed to add booth name column:", err);
      const errorMessage = err instanceof Error 
        ? err.message 
        : "Failed to add booth name column. Please try again.";
      setError(errorMessage);
    } finally {
      setAddingBoothName(false);
    }
  }, [taskId, editedData, selectedSourceColumn]);

  const closeBoothNameDialog = useCallback(() => {
    setBoothNameDialogOpen(false);
    setError(null);
  }, []);

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
    <>
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
                  type="button"
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
                {isBoothView && (
                  <button
                    type="button"
                    onClick={() => {
                      if (editedData && editedData.headers.length > 0) {
                        setSelectedSourceColumn(editedData.headers[0]);
                      }
                      setBoothNameDialogOpen(true);
                    }}
                    disabled={loading || !!error || !editedData}
                    className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <Edit className="w-4 h-4" />
                    Edit
                  </button>
                )}
                {onFilterColumns && (
                  <button
                    type="button"
                    onClick={onFilterColumns}
                    disabled={loading || !!error}
                    className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <Filter className="w-4 h-4" />
                    Filter Columns
                  </button>
                )}

                {!isBoothView && (
                  <>
                    <div className="relative" ref={allianceDropdownRef}>
                      <button
                        type="button"
                        onClick={() => !allianceApplied && setAllianceDropdownOpen(!allianceDropdownOpen)}
                        disabled={loading || !!error || allianceApplied}
                        className="flex items-center gap-2 px-4 py-2 bg-white border border-blue-300 text-blue-700 rounded-lg hover:bg-blue-50 font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        <Users className="w-4 h-4" />
                        Add Alliance
                        <ChevronDown className="w-4 h-4" />
                      </button>

                      {allianceDropdownOpen && (
                        <div className="absolute top-full right-0 mt-1 w-48 bg-white border border-gray-300 rounded-lg shadow-lg z-10 overflow-hidden">
                          <button
                            onClick={() => {
                              setSelectedAllianceType("loksabha");
                              setAllianceDropdownOpen(false);
                              setAllianceModalOpen(true);
                            }}
                            className="w-full px-4 py-2.5 text-left hover:bg-blue-50 transition-colors text-sm font-medium text-gray-700 flex items-center gap-2"
                          >
                            Loksabha
                          </button>
                          <button
                            onClick={() => {
                              setSelectedAllianceType("assembly");
                              setAllianceDropdownOpen(false);
                              setAllianceModalOpen(true);
                            }}
                            className="w-full px-4 py-2.5 text-left hover:bg-blue-50 transition-colors text-sm font-medium text-gray-700 flex items-center gap-2 border-t border-gray-100"
                          >
                            Assembly
                          </button>
                        </div>
                      )}
                    </div>
                    {allianceApplied && (
                      <button
                        type="button"
                        onClick={handleResetAlliance}
                        className="flex items-center gap-2 px-4 py-2 bg-white border border-red-300 text-red-700 rounded-lg hover:bg-red-50 font-medium transition-colors"
                      >
                        <RotateCcw className="w-4 h-4" />
                        Reset Alliance
                      </button>
                    )}
                  </>
                )}

                {allianceWarnings.length > 0 && (
                  <div className="flex items-center gap-2 px-3 py-1.5 bg-yellow-50 border border-yellow-200 rounded-lg">
                    <AlertCircle className="w-4 h-4 text-yellow-600 flex-shrink-0" />
                    <span className="text-xs text-yellow-700">
                      {allianceWarnings.length} column{allianceWarnings.length > 1 ? "s" : ""} not found
                    </span>
                  </div>
                )}

                <button
                  type="button"
                  onClick={openGeocodeDialog}
                  disabled={loading || !!error || geocoding}
                  className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <MapPin className="w-4 h-4" />
                  Geocode Addresses
                </button>

                {/* Language Dropdown */}
                <div className="relative" ref={languageDropdownRef}>
                  <button
                    type="button"
                    onClick={() => !translating && !loading && !error && setShowLanguageDropdown(!showLanguageDropdown)}
                    disabled={loading || !!error || translating}
                    className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed min-w-[180px] justify-between"
                    title={translationProgressMessage || undefined}
                  >
                    {translating ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span className="flex-1">Translating... {Math.round(translationProgress)}%</span>
                      </>
                    ) : (
                      <>
                        <Languages className="w-4 h-4" />
                        <span className="flex-1 text-left">{getCurrentLanguageDisplay()}</span>
                        <ChevronDown className="w-4 h-4" />
                      </>
                    )}
                  </button>

                  {showLanguageDropdown && !translating && (
                    <div className="absolute top-full right-0 mt-1 w-full bg-white border border-gray-300 rounded-lg shadow-lg z-10 overflow-hidden">
                      {LANGUAGE_OPTIONS.map((option) => (
                        <button
                          key={option.value}
                          onClick={() => handleLanguageSelect(option.value)}
                          className={`w-full px-4 py-2 text-left hover:bg-gray-100 transition-colors flex items-center gap-2 ${
                            currentLanguage === option.value
                              ? "bg-blue-50 text-blue-700 font-medium"
                              : "text-gray-700"
                          }`}
                        >
                          <span className="text-lg">{option.emoji}</span>
                          <span className="flex-1">{option.label}</span>
                          {option.value !== "original" && availableTranslations[option.value] && (
                            <span className="text-xs text-green-600">✓</span>
                          )}
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                <button
                  type="button"
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
                  {/* Error Display */}
                  {error && (
                    <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
                      <div className="flex items-start gap-2">
                        <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
                        <div className="flex-1">
                          <p className="text-sm font-medium text-red-800">Error</p>
                          <p className="text-sm text-red-700 mt-1">{error}</p>
                        </div>
                        <button
                          onClick={() => setError(null)}
                          className="text-red-400 hover:text-red-600"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  )}

                  {!geocoding && !geocodeResult && (
                    <>
                      {/* Address Column Selection */}
                      <div className="mb-4">
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                          Address Column
                        </label>
                        <select
                          value={selectedAddressColumn}
                          onChange={(e) => {
                            setSelectedAddressColumn(e.target.value);
                            setError(null); // Clear error when column changes
                          }}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                        >
                          {editedData && editedData.headers.length > 0 ? (
                            editedData.headers.map((header, idx) => (
                              <option key={idx} value={header}>
                                {header}
                              </option>
                            ))
                          ) : (
                            <option value="">No columns available</option>
                          )}
                        </select>
                        {editedData && editedData.headers.length > 0 && (
                          <p className="mt-1 text-xs text-gray-500">
                            Select the column containing address or location data
                          </p>
                        )}
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
                      {geocodeProgress.status === "failed" ? (
                        <div className="p-3 bg-red-50 border border-red-200 rounded-lg">
                          <div className="flex items-start gap-2">
                            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
                            <div className="flex-1">
                              <p className="text-sm font-medium text-red-800">Geocoding Failed</p>
                              <p className="text-sm text-red-700 mt-1">
                                {geocodeProgress.message || "An error occurred during geocoding. Please try again."}
                              </p>
                            </div>
                          </div>
                        </div>
                      ) : (
                        <>
                          <div className="mb-4">
                            <div className="flex justify-between text-sm text-gray-600 mb-2">
                              <span>Geocoding addresses...</span>
                              <span>{geocodeProgress.current} / {geocodeProgress.total}</span>
                            </div>
                            <div className="w-full bg-gray-200 rounded-full h-2.5">
                              <div
                                className="bg-blue-600 h-2.5 rounded-full transition-all duration-300"
                                style={{
                                  width: `${geocodeProgress.total > 0 
                                    ? (geocodeProgress.current / geocodeProgress.total) * 100 
                                    : 0}%`,
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
                        </>
                      )}
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
                        disabled={!selectedAddressColumn || !editedData || editedData.headers.length === 0}
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

          {/* Booth Name Dialog */}
          {boothNameDialogOpen && (
            <div className="fixed inset-0 z-[70] flex items-center justify-center">
              <div
                className="absolute inset-0 bg-black/30"
                onClick={closeBoothNameDialog}
              />
              <div className="relative bg-white rounded-xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
                {/* Dialog Header */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
                  <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                    <Edit className="w-5 h-5 text-blue-600" />
                    Add Booth Name Column
                  </h2>
                  <button
                    onClick={closeBoothNameDialog}
                    className="p-1 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>

                {/* Dialog Content */}
                <div className="px-6 py-4">
                  {/* Error Display */}
                  {error && (
                    <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
                      <div className="flex items-start gap-2">
                        <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
                        <div className="flex-1">
                          <p className="text-sm font-medium text-red-800">Error</p>
                          <p className="text-sm text-red-700 mt-1">{error}</p>
                        </div>
                        <button
                          onClick={() => setError(null)}
                          className="text-red-400 hover:text-red-600"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  )}

                  {!addingBoothName && (
                    <>
                      <p className="text-sm text-gray-600 mb-4">
                        Select a column to extract booth names from. The system will extract the core institution/building name by removing pincodes, location details after commas, and truncating after institution keywords (School, College, Hall, etc.).
                      </p>

                      {/* Source Column Selection */}
                      <div className="mb-4">
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                          Source Column
                        </label>
                        <select
                          value={selectedSourceColumn}
                          onChange={(e) => {
                            setSelectedSourceColumn(e.target.value);
                            setError(null);
                          }}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                        >
                          {editedData && editedData.headers.length > 0 ? (
                            editedData.headers.map((header, idx) => (
                              <option key={idx} value={header}>
                                {header}
                              </option>
                            ))
                          ) : (
                            <option value="">No columns available</option>
                          )}
                        </select>
                        {editedData && editedData.headers.length > 0 && (
                          <p className="mt-1 text-xs text-gray-500">
                            Select the column containing building/location names (e.g., "Location and name of the Building...")
                          </p>
                        )}
                      </div>
                    </>
                  )}

                  {addingBoothName && (
                    <div className="py-8 text-center">
                      <Loader2 className="w-8 h-8 text-blue-600 animate-spin mx-auto mb-4" />
                      <p className="text-sm text-gray-600">Adding Booth name column...</p>
                    </div>
                  )}
                </div>

                {/* Dialog Footer */}
                <div className="flex justify-end gap-3 px-6 py-4 border-t border-gray-200 bg-gray-50">
                  {!addingBoothName && (
                    <>
                      <button
                        onClick={closeBoothNameDialog}
                        className="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={handleAddBoothNameColumn}
                        disabled={!selectedSourceColumn || !editedData || editedData.headers.length === 0}
                        className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                      >
                        <Edit className="w-4 h-4" />
                        Add Booth Name Column
                      </button>
                    </>
                  )}
                </div>
              </div>
            </div>
          )}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>

      {/* Alliance Modal */}
      <AllianceModal
        isOpen={allianceModalOpen}
        onClose={() => setAllianceModalOpen(false)}
        onApply={handleApplyAlliance}
        availableColumns={editedData?.headers ?? []}
        allianceConfig={selectedAllianceType === "assembly" ? ASSEMBLY_ALLIANCE_CONFIG : ALLIANCE_CONFIG}
      />
    </>
  );
}
