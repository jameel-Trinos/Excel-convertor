"use client";

import { useState, useMemo, useCallback } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Check } from "lucide-react";
import { ALLIANCE_CONFIG } from "@/lib/allianceConfig";
import { matchPartyLabel, matchColumnLabel } from "@/lib/partyHeaderMapper";

interface AllianceModalProps {
  isOpen: boolean;
  onClose: () => void;
  onApply: (allianceMap: Record<string, string[]>) => void;
  availableColumns: string[];
  allianceConfig?: Record<string, { color: string; allies: string[] }>;
}

/**
 * Given a party abbreviation (e.g. "DMK"), find the column header
 * in availableColumns that matches it. Returns the header string or null.
 */
function findColumnForParty(
  abbr: string,
  columns: string[]
): string | null {
  // Build the label matchPartyLabel would produce, e.g. "DMK Votes"
  const targetLabel = `${abbr} Votes`;

  // First, try exact label matching (most reliable)
  for (const col of columns) {
    const match = matchPartyLabel(col);
    if (match && match.label === targetLabel) {
      return col;
    }
  }

  // Fallback: For cases where matchPartyLabel might not match due to confidence thresholds
  // or unusual column formats, try a more lenient approach
  // This is especially important for AMMK which might appear as reversed text
  // like "lakkaM arttennuM magazak ammA" (AMMA MAKKAL MUNNETRA KAZHAGAM reversed)
  const abbrUpper = abbr.toUpperCase();
  const abbrNormalized = abbrUpper.replace(/[^A-Z0-9]/g, "");
  
  // Only use fallback for abbreviations of 3+ characters to avoid false positives
  if (abbrNormalized.length >= 3) {
    for (const col of columns) {
      // Skip if we already tried this column in the first pass
      const firstPassMatch = matchPartyLabel(col);
      if (firstPassMatch && firstPassMatch.label === targetLabel) {
        continue; // Already handled above
      }
      
      const colUpper = col.toUpperCase();
      const colNormalized = colUpper.replace(/[^A-Z0-9]/g, "");
      
      // Check if abbreviation appears in the normalized column name
      // This handles full party names like "AMMA MAKKAL MUNNETRA KAZHAGAM"
      if (colNormalized.includes(abbrNormalized)) {
        // Verify it's a party column (not an admin column)
        const colMatch = matchColumnLabel(col);
        if (colMatch && colMatch.type === "party") {
          // Try matchPartyLabel one more time - sometimes it works after normalization
          const partyMatch = matchPartyLabel(col);
          
          // If it matches our target label, use it
          if (partyMatch && partyMatch.label === targetLabel) {
            return col;
          }
          
          // If it matches a different party label, check if that label's abbreviation matches
          if (partyMatch && partyMatch.label.endsWith(" Votes")) {
            const labelAbbr = partyMatch.label.replace(" Votes", "").toUpperCase().replace(/[^A-Z0-9]/g, "");
            // If the label abbreviation matches our target abbreviation, use it
            if (labelAbbr === abbrNormalized) {
              return col;
            }
          }
          
          // Last resort: if column is a party column and contains the abbreviation,
          // and matchPartyLabel didn't strongly match another party, use it
          // This helps with edge cases where confidence is just below threshold (e.g., AMMK)
          // Only use this if:
          // 1. No party match at all, OR
          // 2. Party match confidence is below threshold (suggesting uncertain match)
          // AND the abbreviation is clearly present in the column name
          if (!partyMatch || (partyMatch.confidence < 0.90 && partyMatch.label !== targetLabel)) {
            // Additional safety: verify abbreviation appears as a significant part of the column
            // (not just a substring that could match accidentally)
            const abbrIndex = colNormalized.indexOf(abbrNormalized);
            if (abbrIndex !== -1) {
              // Column contains abbreviation, is a party column, and no strong conflicting match
              return col;
            }
          }
        }
      }
    }
  }

  // Also try CONGRESS → INC mapping (INC is listed as abbreviation for CONGRESS)
  if (abbr === "INC") {
    for (const col of columns) {
      const match = matchPartyLabel(col);
      if (match && match.label === "CONGRESS Votes") {
        return col;
      }
    }
  }

  return null;
}

export function AllianceModal({
  isOpen,
  onClose,
  onApply,
  availableColumns,
  allianceConfig: configProp,
}: AllianceModalProps) {
  const activeConfig = configProp ?? ALLIANCE_CONFIG;
  const activeMainParties = Object.keys(activeConfig);

  const [selectedMainParty, setSelectedMainParty] = useState<string>(activeMainParties[0]);
  const [selections, setSelections] = useState<Record<string, Set<string>>>(() => {
    const init: Record<string, Set<string>> = {};
    for (const party of activeMainParties) {
      init[party] = new Set<string>();
    }
    return init;
  });

  // Map each alliance party abbreviation to its actual column header (or null if not found)
  const partyColumnMap = useMemo(() => {
    const map: Record<string, string | null> = {};
    for (const mainParty of activeMainParties) {
      map[mainParty] = findColumnForParty(mainParty, availableColumns);
      for (const ally of activeConfig[mainParty].allies) {
        if (!(ally in map)) {
          map[ally] = findColumnForParty(ally, availableColumns);
        }
      }
    }
    console.log("Alliance Modal - Available Columns:", availableColumns);
    console.log("Alliance Modal - Party Column Map:", map);
    return map;
  }, [availableColumns, activeConfig, activeMainParties]);

  const currentAllies = activeConfig[selectedMainParty]?.allies ?? [];
  const currentSelections = selections[selectedMainParty] ?? new Set();

  const handleToggleAlly = useCallback(
    (ally: string) => {
      setSelections((prev) => {
        const current = new Set(prev[selectedMainParty]);
        if (current.has(ally)) {
          current.delete(ally);
        } else {
          current.add(ally);
        }
        return { ...prev, [selectedMainParty]: current };
      });
    },
    [selectedMainParty]
  );

  const handleSelectAll = useCallback(() => {
    const available = currentAllies.filter((a) => partyColumnMap[a] !== null);
    setSelections((prev) => ({
      ...prev,
      [selectedMainParty]: new Set(available),
    }));
  }, [selectedMainParty, currentAllies, partyColumnMap]);

  const handleDeselectAll = useCallback(() => {
    setSelections((prev) => ({
      ...prev,
      [selectedMainParty]: new Set(),
    }));
  }, [selectedMainParty]);

  // Count total selected across all parties
  const totalSelected = useMemo(() => {
    let count = 0;
    for (const party of activeMainParties) {
      count += (selections[party]?.size ?? 0);
    }
    return count;
  }, [selections]);

  const handleApply = useCallback(() => {
    const allianceMap: Record<string, string[]> = {};
    let totalSelected = 0;
    let totalFound = 0;

    for (const mainParty of activeMainParties) {
      const selected = selections[mainParty];
      if (!selected || selected.size === 0) continue;

      totalSelected += selected.size;
      const allyColumns: string[] = [];

      for (const ally of selected) {
        const col = partyColumnMap[ally];
        if (col) {
          allyColumns.push(col);
          totalFound++;
        }
      }

      if (allyColumns.length > 0) {
        // Use existing column header, or generate new name like "BJP Votes"
        const mainCol = partyColumnMap[mainParty] ?? `${mainParty} Votes`;
        allianceMap[mainCol] = allyColumns;
      }
    }

    console.log("Alliance Modal - Selections:", selections);
    console.log("Alliance Modal - Alliance Map:", allianceMap);

    if (Object.keys(allianceMap).length === 0) {
      console.warn("Alliance Modal - No alliances to apply (empty map)");

      // Show alert to user explaining why alliance couldn't be applied
      if (totalSelected > 0 && totalFound === 0) {
        alert(`Cannot apply alliance:\n\nNone of the selected alliance parties (${totalSelected} selected) were found in your data.\n\nYour PDF contains: ${availableColumns.filter(col => {
          const match = matchColumnLabel(col);
          return match?.type === 'party';
        }).join(', ') || 'no party columns'}\n\nTip: The alliance feature only works when the alliance parties actually exist in your PDF data.`);
      }

      return; // Don't close modal - let user try again
    }

    onApply(allianceMap);
    onClose();
  }, [selections, partyColumnMap, onApply, onClose, activeMainParties, availableColumns]);

  const handleReset = useCallback(() => {
    const init: Record<string, Set<string>> = {};
    for (const party of activeMainParties) {
      init[party] = new Set<string>();
    }
    setSelections(init);
  }, []);

  const mainPartyAvailable = partyColumnMap[selectedMainParty] !== null;

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-2xl max-h-[80vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Add Alliance Votes</DialogTitle>
          <DialogDescription>
            Select alliance parties to sum their votes into the main party column.
          </DialogDescription>
        </DialogHeader>

        <div className="flex gap-4 flex-1 min-h-0 overflow-hidden">
          {/* Left panel: main parties */}
          <div className="w-1/3 border-r pr-4 space-y-2">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
              Main Party
            </p>
            {activeMainParties.map((party) => {
              const config = activeConfig[party];
              const available = partyColumnMap[party] !== null;
              const selCount = selections[party]?.size ?? 0;

              return (
                <button
                  key={party}
                  onClick={() => setSelectedMainParty(party)}
                  className={`w-full text-left px-3 py-3 rounded-lg border-2 transition-all ${
                    selectedMainParty === party
                      ? "border-blue-500 bg-blue-50 shadow-sm"
                      : "border-gray-200 hover:border-gray-300 hover:bg-gray-50"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <div
                      className="w-3 h-3 rounded-full flex-shrink-0"
                      style={{ backgroundColor: config.color }}
                    />
                    <span className="font-semibold text-sm">{party}</span>
                    {selCount > 0 && (
                      <span className="ml-auto text-xs bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded-full font-medium">
                        {selCount}
                      </span>
                    )}
                  </div>
                  {!available && (
                    <p className="text-xs text-blue-500 mt-1">New column will be created</p>
                  )}
                </button>
              );
            })}
          </div>

          {/* Right panel: alliance party checkboxes */}
          <div className="w-2/3 overflow-y-auto">
            <div className="flex items-center justify-between mb-3">
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                {selectedMainParty} Alliance Partners
              </p>
              <div className="flex gap-2">
                <button
                  onClick={handleSelectAll}
                  className="text-xs text-blue-600 hover:text-blue-700 font-medium"
                >
                  Select All
                </button>
                <span className="text-gray-300">|</span>
                <button
                  onClick={handleDeselectAll}
                  className="text-xs text-gray-500 hover:text-gray-700 font-medium"
                >
                  Deselect All
                </button>
              </div>
            </div>

            {!mainPartyAvailable && (
              <p className="text-xs text-blue-500 italic mb-3 px-1">
                A new &quot;{selectedMainParty} Votes&quot; column will be created from selected alliance votes.
              </p>
            )}

            <div className="space-y-1.5">
                {currentAllies.map((ally) => {
                  const allyAvailable = partyColumnMap[ally] !== null;
                  const checked = currentSelections.has(ally);

                  return (
                    <label
                      key={ally}
                      className={`flex items-center gap-3 px-3 py-2.5 rounded-lg border transition-all cursor-pointer ${
                        !allyAvailable
                          ? "border-gray-100 bg-gray-50 opacity-50 cursor-not-allowed"
                          : checked
                          ? "border-blue-200 bg-blue-50"
                          : "border-gray-200 hover:border-gray-300 hover:bg-gray-50"
                      }`}
                    >
                      <div
                        className={`w-5 h-5 rounded border-2 flex items-center justify-center flex-shrink-0 transition-colors ${
                          checked
                            ? "bg-blue-600 border-blue-600"
                            : "border-gray-300 bg-white"
                        } ${!allyAvailable ? "opacity-50" : ""}`}
                      >
                        {checked && <Check className="w-3 h-3 text-white" />}
                      </div>
                      <input
                        type="checkbox"
                        className="sr-only"
                        checked={checked}
                        disabled={!allyAvailable}
                        onChange={() => allyAvailable && handleToggleAlly(ally)}
                      />
                      <span className={`text-sm font-medium ${allyAvailable ? "text-gray-900" : "text-gray-400"}`}>
                        {ally}
                      </span>
                      {!allyAvailable && (
                        <span className="text-xs text-gray-400 ml-auto">Not in data</span>
                      )}
                      {allyAvailable && partyColumnMap[ally] && (
                        <span className="text-xs text-gray-400 ml-auto truncate max-w-[150px]" title={partyColumnMap[ally]!}>
                          {partyColumnMap[ally]}
                        </span>
                      )}
                    </label>
                  );
                })}
              </div>
          </div>
        </div>

        <DialogFooter className="flex items-center justify-between border-t pt-4">
          <div className="flex items-center gap-3">
            <button
              onClick={handleReset}
              className="text-xs text-gray-500 hover:text-gray-700 font-medium"
            >
              Clear All
            </button>
            {totalSelected > 0 && (
              <span className="text-xs text-gray-500">
                {totalSelected} alliance {totalSelected === 1 ? "party" : "parties"} selected
              </span>
            )}
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button onClick={handleApply} disabled={totalSelected === 0}>
              Apply Alliance
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
