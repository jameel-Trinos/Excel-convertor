"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { Languages, Loader2, ChevronDown } from "lucide-react";
import {
  startTranslation,
  subscribeToTranslateProgress,
  getTranslateStatus,
  cancelTranslation,
} from "@/lib/translation-api";
import type { Language, TranslateProgressEvent } from "@/types";

interface TranslationToggleProps {
  taskId: string;
  currentLanguage: Language;
  onLanguageChange: (language: Language, translateTaskId?: string) => void;
  disabled?: boolean;
}

type TargetLanguage = "tamil" | "hindi" | "english";

const LANGUAGE_OPTIONS: { value: TargetLanguage; label: string; emoji: string }[] = [
  { value: "tamil", label: "Tamil", emoji: "தமிழ்" },
  { value: "hindi", label: "Hindi", emoji: "हिंदी" },
  { value: "english", label: "English", emoji: "English" },
];

export function TranslationToggle({
  taskId,
  currentLanguage,
  onLanguageChange,
  disabled,
}: TranslationToggleProps) {
  const [translating, setTranslating] = useState(false);
  const [progress, setProgress] = useState(0);
  const [progressMessage, setProgressMessage] = useState("");
  const [availableLanguages, setAvailableLanguages] = useState({
    tamil: false,
    hindi: false,
    english: false,
  });
  const [error, setError] = useState<string | null>(null);
  const [showDropdown, setShowDropdown] = useState(false);
  const unsubscribeRef = useRef<(() => void) | null>(null);
  const currentTranslateTaskIdRef = useRef<string | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Check available translations on mount
  useEffect(() => {
    getTranslateStatus(taskId)
      .then((status) => {
        setAvailableLanguages({
          tamil: status.has_tamil_version,
          hindi: status.has_hindi_version,
          english: status.has_english_version,
        });
      })
      .catch((err) => {
        console.error("Failed to get translation status:", err);
      });
  }, [taskId]);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setShowDropdown(false);
      }
    }

    if (showDropdown) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => {
        document.removeEventListener("mousedown", handleClickOutside);
      };
    }
  }, [showDropdown]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (unsubscribeRef.current) {
        unsubscribeRef.current();
      }
    };
  }, []);

  const handleLanguageSelect = useCallback(
    async (targetLang: TargetLanguage) => {
      setShowDropdown(false);

      if (translating || disabled) return;

      setError(null);

      // If selecting the current language, do nothing
      if (targetLang === currentLanguage) {
        return;
      }

      // If switching back to original, just update state
      if (currentLanguage !== "original" && targetLang === "english") {
        // Assuming English is the original language
        // If you want to go back to original, you might need to add "original" to the dropdown
        // For now, we'll just switch to English
      }

      // If translation exists, just switch
      if (availableLanguages[targetLang]) {
        onLanguageChange(targetLang);
        return;
      }

      // Need to translate
      setTranslating(true);
      setProgress(0);
      setProgressMessage("Starting translation...");

      try {
        const response = await startTranslation(taskId, targetLang);

        // Check if it's a cached response
        if (response.translate_task_id.startsWith("cached_")) {
          setTranslating(false);
          setAvailableLanguages((prev) => ({ ...prev, [targetLang]: true }));
          onLanguageChange(targetLang, response.translate_task_id);
          return;
        }

        currentTranslateTaskIdRef.current = response.translate_task_id;

        // Subscribe to progress
        const unsubscribe = subscribeToTranslateProgress(
          response.translate_task_id,
          (event: TranslateProgressEvent) => {
            const progressPercent =
              event.total > 0 ? (event.current / event.total) * 100 : 0;
            setProgress(progressPercent);
            setProgressMessage(event.message);
          },
          () => {
            // Complete
            setTranslating(false);
            setAvailableLanguages((prev) => ({ ...prev, [targetLang]: true }));
            onLanguageChange(targetLang, response.translate_task_id);
            currentTranslateTaskIdRef.current = null;
          },
          (err: Error) => {
            // Error
            console.error("Translation failed:", err);
            setError(err.message);
            setTranslating(false);
            currentTranslateTaskIdRef.current = null;
          }
        );

        unsubscribeRef.current = unsubscribe;
      } catch (err) {
        console.error("Failed to start translation:", err);
        setError(err instanceof Error ? err.message : "Translation failed");
        setTranslating(false);
      }
    },
    [taskId, currentLanguage, availableLanguages, translating, disabled, onLanguageChange]
  );

  const handleCancel = useCallback(async () => {
    if (currentTranslateTaskIdRef.current) {
      try {
        await cancelTranslation(currentTranslateTaskIdRef.current);
      } catch (err) {
        console.error("Failed to cancel translation:", err);
      }
    }
    if (unsubscribeRef.current) {
      unsubscribeRef.current();
      unsubscribeRef.current = null;
    }
    setTranslating(false);
    currentTranslateTaskIdRef.current = null;
  }, []);

  // Get current language display
  const getCurrentLanguageDisplay = () => {
    if (currentLanguage === "original") {
      return "English (Original)";
    }
    const option = LANGUAGE_OPTIONS.find((opt) => opt.value === currentLanguage);
    return option ? `${option.emoji} ${option.label}` : "Select Language";
  };

  return (
    <div className="flex items-center gap-2">
      <div className="relative" ref={dropdownRef}>
        <button
          onClick={() => !translating && !disabled && setShowDropdown(!showDropdown)}
          disabled={disabled || translating}
          className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed min-w-[200px] justify-between"
          title={error ? error : undefined}
        >
          {translating ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span className="flex-1">Translating... {Math.round(progress)}%</span>
            </>
          ) : (
            <>
              <Languages className="w-4 h-4" />
              <span className="flex-1 text-left">{getCurrentLanguageDisplay()}</span>
              <ChevronDown className="w-4 h-4" />
            </>
          )}
        </button>

        {showDropdown && !translating && (
          <div className="absolute top-full left-0 mt-1 w-full bg-white border border-gray-300 rounded-lg shadow-lg z-10 overflow-hidden">
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
                {availableLanguages[option.value] && (
                  <span className="text-xs text-green-600">✓ Available</span>
                )}
              </button>
            ))}
            <button
              onClick={() => {
                setShowDropdown(false);
                onLanguageChange("original");
              }}
              className={`w-full px-4 py-2 text-left hover:bg-gray-100 transition-colors border-t border-gray-200 ${
                currentLanguage === "original"
                  ? "bg-blue-50 text-blue-700 font-medium"
                  : "text-gray-700"
              }`}
            >
              <span className="flex-1">English (Original)</span>
            </button>
          </div>
        )}
      </div>

      {translating && (
        <button
          onClick={handleCancel}
          className="px-3 py-2 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
        >
          Cancel
        </button>
      )}

      {error && !translating && (
        <span className="text-sm text-red-600" title={error}>
          Translation failed
        </span>
      )}

      {translating && progressMessage && (
        <span className="text-sm text-gray-500">{progressMessage}</span>
      )}
    </div>
  );
}
