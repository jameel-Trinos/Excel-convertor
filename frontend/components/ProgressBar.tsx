"use client";

import { Progress } from "@/components/ui/progress";
import { Loader2 } from "lucide-react";

interface ProgressBarProps {
  progress: number;
  message: string;
  showSpinner?: boolean;
}

export function ProgressBar({
  progress,
  message,
  showSpinner = true,
}: ProgressBarProps) {
  return (
    <div className="w-full space-y-3">
      <div className="flex items-center gap-3">
        {showSpinner && (
          <Loader2 className="h-5 w-5 text-blue-600 animate-spin flex-shrink-0" />
        )}
        <span className="text-sm text-gray-600 truncate">{message}</span>
      </div>

      <Progress value={progress} className="h-3" />

      <div className="flex justify-between text-sm">
        <span className="text-gray-500">Processing...</span>
        <span className="font-medium text-gray-700">{progress}%</span>
      </div>
    </div>
  );
}
