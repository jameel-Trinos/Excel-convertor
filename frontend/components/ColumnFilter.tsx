"use client";

import { useState, useEffect, useMemo } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Loader2, X, Download, ArrowLeft, ArrowRight } from "lucide-react";
import { filterExcel, downloadModifiedExcel } from "@/lib/api";
import { matchColumnLabel } from "@/lib/partyHeaderMapper";
import type { CellValue } from "@/types";

interface ColumnFilterProps {
  isOpen: boolean;
  onClose: () => void;
  taskId: string;
  columns: string[];
  filename: string;
  editedData?: { headers: string[]; rows: CellValue[][] } | null;
}

// Color schemes for different party types
const PARTY_COLORS: Record<string, { border: string; bg: string; badge: string; badgeText: string }> = {
  // Major parties
  "DMK Votes": { border: "border-indigo-200", bg: "bg-indigo-50", badge: "bg-indigo-100", badgeText: "text-indigo-700" },
  "AIADMK Votes": { border: "border-green-200", bg: "bg-green-50", badge: "bg-green-100", badgeText: "text-green-700" },
  "BJP Votes": { border: "border-blue-200", bg: "bg-blue-50", badge: "bg-blue-100", badgeText: "text-blue-700" },
  "CONGRESS Votes": { border: "border-cyan-200", bg: "bg-cyan-50", badge: "bg-cyan-100", badgeText: "text-cyan-700" },
  // Alliance / medium parties
  "PMK Votes": { border: "border-lime-200", bg: "bg-lime-50", badge: "bg-lime-100", badgeText: "text-lime-700" },
  "VCK Votes": { border: "border-red-200", bg: "bg-red-50", badge: "bg-red-100", badgeText: "text-red-700" },
  "NTK Votes": { border: "border-pink-200", bg: "bg-pink-50", badge: "bg-pink-100", badgeText: "text-pink-700" },
  "DMDK Votes": { border: "border-teal-200", bg: "bg-teal-50", badge: "bg-teal-100", badgeText: "text-teal-700" },
  "MDMK Votes": { border: "border-emerald-200", bg: "bg-emerald-50", badge: "bg-emerald-100", badgeText: "text-emerald-700" },
  "AMMK Votes": { border: "border-amber-200", bg: "bg-amber-50", badge: "bg-amber-100", badgeText: "text-amber-700" },
  "NDK Votes": { border: "border-stone-200", bg: "bg-stone-50", badge: "bg-stone-100", badgeText: "text-stone-700" },
  // Left parties
  "CPI Votes": { border: "border-red-200", bg: "bg-red-50", badge: "bg-red-100", badgeText: "text-red-700" },
  "CPI(M) Votes": { border: "border-rose-200", bg: "bg-rose-50", badge: "bg-rose-100", badgeText: "text-rose-700" },
  // Congress allies
  "TMC(M) Votes": { border: "border-sky-200", bg: "bg-sky-50", badge: "bg-sky-100", badgeText: "text-sky-700" },
  "IUML Votes": { border: "border-emerald-200", bg: "bg-emerald-50", badge: "bg-emerald-100", badgeText: "text-emerald-700" },
  "AIFB Votes": { border: "border-fuchsia-200", bg: "bg-fuchsia-50", badge: "bg-fuchsia-100", badgeText: "text-fuchsia-700" },
  "RPI(A) Votes": { border: "border-violet-200", bg: "bg-violet-50", badge: "bg-violet-100", badgeText: "text-violet-700" },
  // Smaller / regional parties
  "BSP Votes": { border: "border-purple-200", bg: "bg-purple-50", badge: "bg-purple-100", badgeText: "text-purple-700" },
  "MNM Votes": { border: "border-yellow-200", bg: "bg-yellow-50", badge: "bg-yellow-100", badgeText: "text-yellow-700" },
  "IJK Votes": { border: "border-stone-200", bg: "bg-stone-50", badge: "bg-stone-100", badgeText: "text-stone-700" },
  "KMDK Votes": { border: "border-zinc-200", bg: "bg-zinc-50", badge: "bg-zinc-100", badgeText: "text-zinc-700" },
  "MMK Votes": { border: "border-slate-200", bg: "bg-slate-50", badge: "bg-slate-100", badgeText: "text-slate-700" },
  "SDPI Votes": { border: "border-green-200", bg: "bg-green-50", badge: "bg-green-100", badgeText: "text-green-700" },
  "PT Votes": { border: "border-amber-200", bg: "bg-amber-50", badge: "bg-amber-100", badgeText: "text-amber-700" },
  "AIMIM Votes": { border: "border-teal-200", bg: "bg-teal-50", badge: "bg-teal-100", badgeText: "text-teal-700" },
  "TMK Votes": { border: "border-cyan-200", bg: "bg-cyan-50", badge: "bg-cyan-100", badgeText: "text-cyan-700" },
  // Special
  "IND Votes": { border: "border-gray-200", bg: "bg-gray-50", badge: "bg-gray-100", badgeText: "text-gray-700" },
  "NOTA Votes": { border: "border-orange-200", bg: "bg-orange-50", badge: "bg-orange-100", badgeText: "text-orange-700" },
  "TOTAL": { border: "border-indigo-200", bg: "bg-indigo-50", badge: "bg-indigo-100", badgeText: "text-indigo-700" },
  // Administrative columns
  "Polling Station No.": { border: "border-slate-200", bg: "bg-slate-50", badge: "bg-slate-100", badgeText: "text-slate-700" },
  "Polling Station Name": { border: "border-sky-200", bg: "bg-sky-50", badge: "bg-sky-100", badgeText: "text-sky-700" },
  "SL. NO.": { border: "border-slate-200", bg: "bg-slate-50", badge: "bg-slate-100", badgeText: "text-slate-700" },
  "AC NO.": { border: "border-slate-200", bg: "bg-slate-50", badge: "bg-slate-100", badgeText: "text-slate-700" },
  "Total Valid Votes": { border: "border-indigo-200", bg: "bg-indigo-50", badge: "bg-indigo-100", badgeText: "text-indigo-700" },
  "Rejected Votes": { border: "border-orange-200", bg: "bg-orange-50", badge: "bg-orange-100", badgeText: "text-orange-700" },
  "Tendered Votes": { border: "border-orange-200", bg: "bg-orange-50", badge: "bg-orange-100", badgeText: "text-orange-700" },
  "Total Electors": { border: "border-indigo-200", bg: "bg-indigo-50", badge: "bg-indigo-100", badgeText: "text-indigo-700" },
  "default": { border: "border-gray-200", bg: "bg-white", badge: "bg-gray-100", badgeText: "text-gray-700" },
};

// Helper to get color scheme for a party
function getPartyColors(groupKey: string) {
  return PARTY_COLORS[groupKey] || PARTY_COLORS.default;
}

export function ColumnFilter({
  isOpen,
  onClose,
  taskId,
  columns,
  filename,
  editedData,
}: ColumnFilterProps) {
  const [selectedColumns, setSelectedColumns] = useState<Set<string>>(new Set());
  const [sumOtherSet, setSumOtherSet] = useState<Set<string>>(new Set());
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState<1 | 2>(1);

  // Use editedData.headers if available (post-alliance), otherwise use columns prop
  // This ensures we show only columns that actually exist in the current data state
  const effectiveColumns = useMemo(() => {
    return editedData?.headers ?? columns;
  }, [editedData, columns]);

  // Build unique keys for each column to handle duplicates (e.g., multiple "DNI" columns)
  const uniqueColumns = useMemo(() => {
    const nameCounts: Record<string, number> = {};
    return effectiveColumns.map((col, idx) => {
      nameCounts[col] = (nameCounts[col] || 0) + 1;
      const count = nameCounts[col];
      // For first occurrence keep original name, for duplicates append index
      const uniqueKey = count === 1 ? col : `${col} (${count})`;
      return { uniqueKey, originalName: col, index: idx };
    });
  }, [effectiveColumns]);

  // All unique keys for convenience
  const allUniqueKeys = useMemo(() => uniqueColumns.map(c => c.uniqueKey), [uniqueColumns]);

  // Initialize all columns as selected by default
  useEffect(() => {
    if (isOpen) {
      setSelectedColumns(new Set(allUniqueKeys));
      setSumOtherSet(new Set());
      setSearchQuery("");
      setError(null);
      setStep(1);
    }
  }, [isOpen, allUniqueKeys]);

  // Compute unselected party columns (candidates for "Other" summing)
  const unselectedPartyKeys = useMemo(() => {
    return allUniqueKeys.filter((key) => {
      if (selectedColumns.has(key)) return false;
      const originalName = uniqueColumns.find(c => c.uniqueKey === key)?.originalName || key;
      const match = matchColumnLabel(originalName);
      // Only party vote columns are candidates for "Other"
      return match?.type === "party";
    });
  }, [allUniqueKeys, selectedColumns, uniqueColumns]);

  // Clean up sumOtherSet: remove keys that are no longer unselected party columns
  // (e.g. user re-selected a column). User manually checks the ones they want summed.
  useEffect(() => {
    setSumOtherSet((prev) => {
      const next = new Set(prev);
      for (const key of prev) {
        if (!unselectedPartyKeys.includes(key)) next.delete(key);
      }
      return next;
    });
  }, [unselectedPartyKeys]);

  // Group columns - show each column separately
  const columnGroups = useMemo(() => {
    const groups: Record<string, { cols: string[]; examples: string[] }> = {};

    for (const { uniqueKey } of uniqueColumns) {
      if (!groups[uniqueKey]) groups[uniqueKey] = { cols: [], examples: [] };
      groups[uniqueKey].cols.push(uniqueKey);
      if (groups[uniqueKey].examples.length < 2) groups[uniqueKey].examples.push(uniqueKey);
    }

    return groups;
  }, [uniqueColumns]);

  const sortedGroupKeys = useMemo(() => {
    const keys = Object.keys(columnGroups);
    const knownPartyOrder = [
      "DMK Votes", "AIADMK Votes", "BJP Votes", "CONGRESS Votes",
      "PMK Votes", "VCK Votes", "NTK Votes", "AMMK Votes", "DMDK Votes",
      "MDMK Votes", "NDK Votes", "CPI Votes", "CPI(M) Votes",
      "TMC(M) Votes", "IUML Votes", "AIFB Votes", "RPI(A) Votes",
      "BSP Votes", "MNM Votes", "IJK Votes", "KMDK Votes", "MMK Votes",
      "SDPI Votes", "PT Votes", "AIMIM Votes", "TMK Votes",
      "IND Votes", "NOTA Votes",
    ];

    // Sort columns: first by party label match (if any), then by original order
    const sorted = keys.sort((a, b) => {
      const matchA = matchColumnLabel(a);
      const matchB = matchColumnLabel(b);
      
      // Get party labels for comparison
      const labelA = matchA?.label || "";
      const labelB = matchB?.label || "";
      
      // Find index in known party order
      const indexA = knownPartyOrder.indexOf(labelA);
      const indexB = knownPartyOrder.indexOf(labelB);
      
      // If both are in known order, sort by that order
      if (indexA !== -1 && indexB !== -1) {
        if (indexA !== indexB) return indexA - indexB;
        // If same party label, maintain original order
        return keys.indexOf(a) - keys.indexOf(b);
      }
      
      // If only A is in known order, A comes first
      if (indexA !== -1) return -1;
      // If only B is in known order, B comes first
      if (indexB !== -1) return 1;
      
      // If neither is in known order, maintain original order
      return keys.indexOf(a) - keys.indexOf(b);
    });
    
    return sorted;
  }, [columnGroups]);

  const filteredGroupKeys = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return sortedGroupKeys;

    return sortedGroupKeys.filter((key) => {
      if (key.toLowerCase().includes(q)) return true;
      const cols = columnGroups[key]?.cols ?? [];
      return cols.some((c) => c.toLowerCase().includes(q));
    });
  }, [sortedGroupKeys, columnGroups, searchQuery]);

  const toggleColumn = (columnName: string) => {
    setSelectedColumns((prev) => {
      const next = new Set(prev);
      if (next.has(columnName)) next.delete(columnName);
      else next.add(columnName);
      return next;
    });
  };

  const toggleGroup = (groupKey: string) => {
    const cols = columnGroups[groupKey]?.cols ?? [];
    if (cols.length === 0) return;
    const allSelected = cols.every((c) => selectedColumns.has(c));
    
    setSelectedColumns((prev) => {
      const next = new Set(prev);
      if (allSelected) cols.forEach((c) => next.delete(c));
      else cols.forEach((c) => next.add(c));
      return next;
    });
  };

  const isGroupSelected = (groupKey: string): boolean => {
    const cols = columnGroups[groupKey]?.cols ?? [];
    return cols.length > 0 && cols.every((c) => selectedColumns.has(c));
  };

  const isGroupPartial = (groupKey: string): boolean => {
    const cols = columnGroups[groupKey]?.cols ?? [];
    if (cols.length === 0) return false;
    const selectedCount = cols.filter((c) => selectedColumns.has(c)).length;
    return selectedCount > 0 && selectedCount < cols.length;
  };

  const toggleAll = () => {
    if (selectedColumns.size === allUniqueKeys.length) {
      // Deselect all
      setSelectedColumns(new Set());
    } else {
      // Select all
      setSelectedColumns(new Set(allUniqueKeys));
    }
  };

  const handleSubmit = async () => {
    if (selectedColumns.size === 0) {
      setError("Please select at least one column");
      return;
    }

    if (step === 1) {
      // If there are unselected party columns, go to step 2
      if (unselectedPartyKeys.length > 0) {
        // Default: all unselected party columns selected for "Other"
        setSumOtherSet(new Set(unselectedPartyKeys));
        setStep(2);
        return;
      }
      // No unselected party columns — download directly
    }

    await performFilter();
  };

  // Helper to map unique keys back to original column names
  const uniqueKeyToOriginal = useMemo(() => {
    const map: Record<string, string> = {};
    for (const { uniqueKey, originalName } of uniqueColumns) {
      map[uniqueKey] = originalName;
    }
    return map;
  }, [uniqueColumns]);

  // Helper to map unique keys directly to their column indices (for handling duplicates correctly)
  const uniqueKeyToIndex = useMemo(() => {
    const map: Record<string, number> = {};
    for (const { uniqueKey, index } of uniqueColumns) {
      map[uniqueKey] = index;
    }
    return map;
  }, [uniqueColumns]);

  const performFilter = async () => {
    setLoading(true);
    setError(null);

    try {
      // Map unique keys back to original column names
      const columnsToInclude = Array.from(selectedColumns).map(key => uniqueKeyToOriginal[key] || key);

      // Build header overrides so downloaded Excel uses abbreviated party labels
      const headerOverrides: Record<string, string> = {};
      for (const col of columnsToInclude) {
        const match = matchColumnLabel(col);
        if (match) {
          headerOverrides[col] = match.label;
        }
      }

      // Map manually selected "sum into Other" keys back to original column names
      const sumOtherColumns: string[] = Array.from(sumOtherSet).map(
        (key) => uniqueKeyToOriginal[key] || key
      );

      if (editedData) {
        // Client-side filtering: use post-alliance data directly
        const srcHeaders = editedData.headers;
        const srcRows = editedData.rows;

        // Build reverse mapping from selected unique keys to their indices
        // This handles duplicate column names correctly
        const selectedUniqueKeys = Array.from(selectedColumns);
        const selectedIndices: number[] = selectedUniqueKeys
          .map(key => uniqueKeyToIndex[key])
          .filter(idx => idx !== undefined);

        // Build filtered headers with overrides applied
        const filteredHeaders = selectedIndices.map((i) => {
          const orig = srcHeaders[i];
          return headerOverrides[orig] || orig;
        });

        // Build filtered rows
        let filteredRows: CellValue[][] = srcRows.map((row) =>
          selectedIndices.map((i) => row[i])
        );

        // Compute "Others Votes" from unselected party columns
        // Use indices directly to handle duplicate column names correctly
        if (sumOtherSet.size > 0) {
          const otherIndices: number[] = Array.from(sumOtherSet)
            .map(key => uniqueKeyToIndex[key])
            .filter(idx => idx !== undefined);

          if (otherIndices.length > 0) {
            console.log("ColumnFilter - Computing Others Votes from indices:", otherIndices);
            filteredHeaders.push("Others Votes");
            filteredRows = filteredRows.map((row, rowIdx) => {
              let othersSum = 0;
              for (const oi of otherIndices) {
                const val = Number(srcRows[rowIdx][oi]);
                if (!isNaN(val)) othersSum += val;
              }
              return [...row, othersSum];
            });
          }
        }

        await downloadModifiedExcel(taskId, filteredHeaders, filteredRows, filename);
      } else {
        // Backend filtering: original Excel file flow
        await filterExcel(
          taskId,
          columnsToInclude,
          filename,
          headerOverrides,
          sumOtherColumns.length > 0 ? sumOtherColumns : undefined
        );
      }

      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to filter Excel");
    } finally {
      setLoading(false);
    }
  };

  const allSelected = selectedColumns.size === allUniqueKeys.length;
  const someSelected = selectedColumns.size > 0 && selectedColumns.size < allUniqueKeys.length;

  return (
    <>
      {isOpen && (
        <>
          {/* Backdrop with blur */}
          <div
            className="fixed inset-0 bg-black/50 backdrop-blur-sm z-40"
            onClick={onClose}
          />

          {/* Modal Content */}
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
            <div className="w-full max-w-lg max-h-[80vh] bg-white rounded-xl shadow-2xl overflow-hidden flex flex-col pointer-events-auto">
              {/* Header */}
              <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
                <div>
                  <h2 className="text-base font-bold text-gray-900">
                    {step === 1 ? "Select Columns to Export" : "Sum into \"Other\" Column"}
                  </h2>
                  <p className="text-xs text-gray-600 mt-0.5">
                    {step === 1
                      ? "Choose which columns to include in your Excel file"
                      : "Select which deselected party columns to sum into an \"Other\" column"}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  {step === 2 && (
                    <span className="text-[10px] text-gray-400 font-medium">Step 2 of 2</span>
                  )}
                  <button
                    onClick={onClose}
                    className="text-gray-400 hover:text-gray-600 p-1 hover:bg-gray-100 rounded-lg transition-colors"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>
              </div>

              {/* Content */}
              <div className="flex-1 overflow-hidden flex flex-col gap-3 px-4 py-3">
                {step === 1 ? (
                  <>
                    {/* Search Box */}
                    <div className="relative">
                      <svg
                        className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                        />
                      </svg>
                      <input
                        type="text"
                        placeholder="Search columns or parties..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="w-full pl-9 pr-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      />
                    </div>

                    {/* Select All / Deselect All */}
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <button
                          onClick={() => setSelectedColumns(new Set(allUniqueKeys))}
                          className="text-xs text-blue-600 hover:text-blue-700 font-medium transition-colors"
                        >
                          Select All
                        </button>
                        <button
                          onClick={() => setSelectedColumns(new Set())}
                          className="text-xs text-blue-600 hover:text-blue-700 font-medium transition-colors"
                        >
                          Deselect All
                        </button>
                      </div>
                      <span className="text-xs text-gray-600">
                        <span className="font-semibold text-gray-900">{selectedColumns.size}</span> of {allUniqueKeys.length} selected
                      </span>
                    </div>

                    {/* Column List */}
                    <div className="flex-1 overflow-auto">
                      {filteredGroupKeys.length === 0 ? (
                        <div className="text-center py-6 text-gray-500">
                          <p className="text-sm">No columns match &quot;{searchQuery}&quot;</p>
                        </div>
                      ) : (
                        <div className="space-y-2">
                          {filteredGroupKeys.map((groupKey) => {
                            const group = columnGroups[groupKey];
                            const cols = group?.cols ?? [];
                            const selected = isGroupSelected(groupKey);
                            const isHighlighted =
                              !!searchQuery.trim() &&
                              (groupKey.toLowerCase().includes(searchQuery.toLowerCase()) ||
                                cols.some((c) => c.toLowerCase().includes(searchQuery.toLowerCase())));

                            const match = matchColumnLabel(groupKey);
                            const displayLabel = match?.label || groupKey;
                            const colors = getPartyColors(displayLabel);

                            let badgeText = "Numeric";
                            let badgeColor = colors.badge + " " + colors.badgeText;

                            if (match?.type === "identifier") {
                              badgeText = "ID";
                              badgeColor = "bg-slate-100 text-slate-700";
                            } else if (match?.type === "location") {
                              badgeText = "Location";
                              badgeColor = "bg-sky-100 text-sky-700";
                            } else if (match?.type === "count" || groupKey.includes("TOTAL")) {
                              badgeText = "Count";
                              badgeColor = "bg-indigo-100 text-indigo-700";
                            }

                            return (
                              <label
                                key={groupKey}
                                className={`flex items-start gap-2.5 p-3 rounded-lg border cursor-pointer transition-all ${
                                  selected
                                    ? `${colors.border} ${colors.bg}`
                                    : `${colors.border} bg-white hover:${colors.bg}`
                                } ${isHighlighted ? "ring-1 ring-yellow-300" : ""}`}
                              >
                                <input
                                  type="checkbox"
                                  checked={selected}
                                  onChange={() => toggleColumn(groupKey)}
                                  className="w-4 h-4 text-blue-600 rounded mt-0.5"
                                />
                                <div className="flex-1 min-w-0">
                                  <div className="flex items-center gap-1.5 mb-0.5">
                                    <h3 className="font-semibold text-gray-900 text-sm truncate">{displayLabel}</h3>
                                    <span className={`px-1.5 py-0.5 ${badgeColor} text-xs font-medium rounded flex-shrink-0`}>
                                      {badgeText}
                                    </span>
                                  </div>
                                  {groupKey !== displayLabel && (
                                    <p className="text-xs text-gray-600 truncate">{groupKey}</p>
                                  )}
                                </div>
                              </label>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  </>
                ) : (
                  <>
                    {/* Step 2: Sum into "Other" column */}
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <button
                          onClick={() => setSumOtherSet(new Set(unselectedPartyKeys))}
                          className="text-xs text-blue-600 hover:text-blue-700 font-medium transition-colors"
                        >
                          Select All
                        </button>
                        <button
                          onClick={() => setSumOtherSet(new Set())}
                          className="text-xs text-blue-600 hover:text-blue-700 font-medium transition-colors"
                        >
                          Deselect All
                        </button>
                      </div>
                      <span className="text-xs text-gray-600">
                        <span className="font-semibold text-gray-900">{sumOtherSet.size}</span> of {unselectedPartyKeys.length} selected
                      </span>
                    </div>

                    <div className="flex-1 overflow-auto">
                      <div className="space-y-2">
                        {unselectedPartyKeys.map((key) => {
                          const originalName = uniqueColumns.find(c => c.uniqueKey === key)?.originalName || key;
                          const match = matchColumnLabel(originalName);
                          const displayLabel = match?.label || key;
                          const colors = getPartyColors(displayLabel);
                          const checked = sumOtherSet.has(key);

                          return (
                            <label
                              key={key}
                              className={`flex items-start gap-2.5 p-3 rounded-lg border cursor-pointer transition-all ${
                                checked
                                  ? `${colors.border} ${colors.bg}`
                                  : `${colors.border} bg-white hover:${colors.bg}`
                              }`}
                            >
                              <input
                                type="checkbox"
                                checked={checked}
                                onChange={() => {
                                  setSumOtherSet((prev) => {
                                    const next = new Set(prev);
                                    if (next.has(key)) next.delete(key);
                                    else next.add(key);
                                    return next;
                                  });
                                }}
                                className="w-4 h-4 text-amber-600 rounded mt-0.5"
                              />
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-1.5 mb-0.5">
                                  <h3 className="font-semibold text-gray-900 text-sm truncate">{displayLabel}</h3>
                                  <span className="px-1.5 py-0.5 bg-amber-100 text-amber-700 text-xs font-medium rounded flex-shrink-0">
                                    Party
                                  </span>
                                </div>
                                {key !== displayLabel && (
                                  <p className="text-xs text-gray-600 truncate">{key}</p>
                                )}
                              </div>
                            </label>
                          );
                        })}
                      </div>
                    </div>
                  </>
                )}

                {/* Error Message */}
                {error && (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-2.5">
                    <div className="flex items-start gap-1.5">
                      <svg
                        className="w-4 h-4 text-red-600 flex-shrink-0 mt-0.5"
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
                      <p className="text-xs text-red-600">{error}</p>
                    </div>
                  </div>
                )}
              </div>

              {/* Footer */}
              <div className="flex items-center gap-2 px-4 py-3 border-t border-gray-200">
                {step === 1 ? (
                  <>
                    <Button
                      variant="outline"
                      onClick={onClose}
                      disabled={loading}
                      className="px-3 py-2 text-xs h-8"
                    >
                      Cancel
                    </Button>
                    <Button
                      onClick={handleSubmit}
                      disabled={loading || selectedColumns.size === 0}
                      className="flex-1 px-4 py-2 text-xs h-8 bg-blue-600 text-white hover:bg-blue-700 flex items-center justify-center gap-1.5"
                    >
                      {loading ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Processing...
                        </>
                      ) : (
                        <>
                          <ArrowRight className="h-4 w-4" />
                          Continue
                        </>
                      )}
                    </Button>
                  </>
                ) : (
                  <>
                    <Button
                      variant="outline"
                      onClick={() => setStep(1)}
                      disabled={loading}
                      className="px-3 py-2 text-xs h-8 flex items-center gap-1.5"
                    >
                      <ArrowLeft className="h-3.5 w-3.5" />
                      Back
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => {
                        setSumOtherSet(new Set());
                        performFilter();
                      }}
                      disabled={loading}
                      className="px-3 py-2 text-xs h-8"
                    >
                      Skip
                    </Button>
                    <Button
                      onClick={handleSubmit}
                      disabled={loading}
                      className="flex-1 px-4 py-2 text-xs h-8 bg-blue-600 text-white hover:bg-blue-700 flex items-center justify-center gap-1.5"
                    >
                      {loading ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Processing...
                        </>
                      ) : (
                        <>
                          <Download className="h-4 w-4" />
                          Download
                        </>
                      )}
                    </Button>
                  </>
                )}
              </div>
            </div>
          </div>
        </>
      )}
    </>
  );
}




