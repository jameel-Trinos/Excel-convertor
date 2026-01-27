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
import { Loader2, Columns, CheckSquare, Square, Search } from "lucide-react";
import { filterExcel } from "@/lib/api";
import { matchPartyLabel } from "@/lib/partyHeaderMapper";

interface ColumnFilterProps {
  isOpen: boolean;
  onClose: () => void;
  taskId: string;
  columns: string[];
  filename: string;
}

// Party label mapping (high-precision). If we’re not confident, we keep the original header.

export function ColumnFilter({
  isOpen,
  onClose,
  taskId,
  columns,
  filename,
}: ColumnFilterProps) {
  const [selectedColumns, setSelectedColumns] = useState<Set<string>>(new Set());
  const [searchQuery, setSearchQuery] = useState("");
  const [includeOthers, setIncludeOthers] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Initialize all columns as selected by default
  useEffect(() => {
    if (isOpen) {
      setSelectedColumns(new Set(columns));
      setSearchQuery("");
      setIncludeOthers(false);
      setError(null);
    }
  }, [isOpen, columns]);

  // Group columns by mapped party label (or by their original header when no confident match)
  const columnGroups = useMemo(() => {
    const groups: Record<string, { cols: string[]; examples: string[] }> = {};

    for (const col of columns) {
      const match = matchPartyLabel(col);
      const key = match ? match.label : col; // no forced "OTHERS"; keep original if unsure

      if (!groups[key]) groups[key] = { cols: [], examples: [] };
      groups[key].cols.push(col);
      if (groups[key].examples.length < 2) groups[key].examples.push(col);
    }
    
    return groups;
  }, [columns]);

  const sortedGroupKeys = useMemo(() => {
    const keys = Object.keys(columnGroups);
    const knownPartyOrder = [
      "DMK Votes",
      "AIADMK Votes",
      "BJP Votes",
      "CONGRESS Votes",
      "VCK Votes",
      "PMK Votes",
      "NTK Votes",
      "AMMK Votes",
      "DMDK Votes",
      "NDK Votes",
      "CPI Votes",
      "NOTA Votes",
      "IND Votes",
    ];

    const partyKeys = knownPartyOrder.filter((k) => keys.includes(k));
    const rest = keys.filter((k) => !knownPartyOrder.includes(k));
    return [...partyKeys, ...rest];
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
    if (selectedColumns.size === columns.length) {
      // Deselect all
      setSelectedColumns(new Set());
    } else {
      // Select all
      setSelectedColumns(new Set(columns));
    }
  };

  const handleSubmit = async () => {
    if (selectedColumns.size === 0 && !includeOthers) {
      setError("Please select at least one column");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const columnsToInclude = Array.from(selectedColumns);
      // Build header overrides so downloaded Excel uses the same display labels shown in this UI
      const headerOverrides: Record<string, string> = {};
      for (const [groupKey, group] of Object.entries(columnGroups)) {
        for (const col of group.cols) {
          if (!selectedColumns.has(col)) continue;
          // Only override when the UI label differs from the original header
          if (groupKey !== col) headerOverrides[col] = groupKey;
        }
      }

      await filterExcel(taskId, columnsToInclude, filename, includeOthers, headerOverrides);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to filter Excel");
    } finally {
      setLoading(false);
    }
  };

  const allSelected = selectedColumns.size === columns.length;
  const someSelected = selectedColumns.size > 0 && selectedColumns.size < columns.length;
  const totalColumnsToDownload = selectedColumns.size + (includeOthers ? 1 : 0);

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Columns className="h-5 w-5" />
            Filter Columns
          </DialogTitle>
          <DialogDescription>
            Search and select columns to include in the filtered Excel file.
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-hidden flex flex-col gap-4">
          {/* Search Box */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
            <input
              type="text"
              placeholder="Search columns or parties..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          {/* Select All / Deselect All */}
          <div className="border-b pb-3">
            <button
              onClick={toggleAll}
              className="flex items-center gap-2 text-sm font-medium text-gray-700 hover:text-gray-900 transition-colors"
            >
              {allSelected ? (
                <CheckSquare className="h-5 w-5 text-blue-600" />
              ) : someSelected ? (
                <div className="h-5 w-5 border-2 border-blue-600 rounded bg-blue-100 flex items-center justify-center">
                  <div className="w-2.5 h-0.5 bg-blue-600" />
                </div>
              ) : (
                <Square className="h-5 w-5 text-gray-400" />
              )}
              <span>
                {allSelected ? "Deselect All" : "Select All"} ({selectedColumns.size}/{columns.length} columns)
              </span>
            </button>
          </div>

          {/* Column List */}
          <div className="flex-1 overflow-auto">
            {filteredGroupKeys.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                <p>No columns match "{searchQuery}"</p>
              </div>
            ) : (
              <div className="space-y-2">
                {filteredGroupKeys.map((groupKey) => {
                  const group = columnGroups[groupKey];
                  const cols = group?.cols ?? [];
                  const selected = isGroupSelected(groupKey);
                  const partial = isGroupPartial(groupKey);
                  const isHighlighted =
                    !!searchQuery.trim() &&
                    (groupKey.toLowerCase().includes(searchQuery.toLowerCase()) ||
                      cols.some((c) => c.toLowerCase().includes(searchQuery.toLowerCase())));

                  // If groupKey is exactly an original column (no match), treat as single-column entry
                  const isSingle = cols.length === 1 && cols[0] === groupKey;
                  
                  return (
                    <label
                      key={groupKey}
                      className={`flex items-center gap-3 p-3 rounded-lg border-2 cursor-pointer transition-all ${
                        selected
                          ? "border-blue-500 bg-blue-50"
                          : partial
                          ? "border-blue-300 bg-blue-25"
                          : "border-gray-200 bg-white hover:border-gray-300 hover:bg-gray-50"
                      } ${isHighlighted ? "ring-2 ring-yellow-300" : ""}`}
                    >
                      <input
                        type="checkbox"
                        checked={selected}
                        onChange={() => (isSingle ? toggleColumn(groupKey) : toggleGroup(groupKey))}
                        className="sr-only"
                      />
                      {selected ? (
                        <CheckSquare className="h-5 w-5 text-blue-600 flex-shrink-0" />
                      ) : partial ? (
                        <div className="h-5 w-5 border-2 border-blue-600 rounded bg-blue-100 flex items-center justify-center">
                          <div className="w-2.5 h-0.5 bg-blue-600" />
                        </div>
                      ) : (
                        <Square className="h-5 w-5 text-gray-400 flex-shrink-0" />
                      )}
                      <div className="flex-1">
                        <span className={`text-sm font-medium ${selected ? "text-gray-900" : "text-gray-700"}`}>
                          {groupKey}
                        </span>
                        {!isSingle && cols.length > 1 && (
                          <p className="text-xs text-gray-500 mt-0.5">
                            {cols.length} columns (e.g. {group.examples.join(" • ")})
                          </p>
                        )}
                      </div>
                    </label>
                  );
                })}

                {/* OTHERS Checkbox */}
                {selectedColumns.size < columns.length && (
                  <div className="pt-2 mt-2 border-t">
                    <label
                      className={`flex items-center gap-3 p-3 rounded-lg border-2 cursor-pointer transition-all ${
                        includeOthers
                          ? "border-green-500 bg-green-50"
                          : "border-gray-200 bg-white hover:border-gray-300 hover:bg-gray-50"
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={includeOthers}
                        onChange={() => setIncludeOthers(!includeOthers)}
                        className="sr-only"
                      />
                      {includeOthers ? (
                        <CheckSquare className="h-5 w-5 text-green-600 flex-shrink-0" />
                      ) : (
                        <Square className="h-5 w-5 text-gray-400 flex-shrink-0" />
                      )}
                      <div className="flex-1">
                        <span className={`text-sm font-medium ${includeOthers ? "text-gray-900" : "text-gray-700"}`}>
                          OTHERS
                        </span>
                        <p className="text-xs text-gray-600 mt-1">
                          Sum of unselected numeric columns
                        </p>
                      </div>
                    </label>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Selected Count */}
          <div className="text-sm text-gray-600 border-t pt-3">
            Selected: <strong>{selectedColumns.size}</strong> column{selectedColumns.size !== 1 ? 's' : ''}
            {includeOthers && <span> + OTHERS</span>}
          </div>

          {/* Error Message */}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-3">
              <p className="text-sm text-red-600">{error}</p>
            </div>
          )}
        </div>

        <DialogFooter className="border-t pt-4">
          <Button variant="outline" onClick={onClose} disabled={loading}>
            Cancel
          </Button>
          <Button 
            onClick={handleSubmit} 
            disabled={loading || (selectedColumns.size === 0 && !includeOthers)}
          >
            {loading ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Processing...
              </>
            ) : (
              `Apply Filter & Download`
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}




