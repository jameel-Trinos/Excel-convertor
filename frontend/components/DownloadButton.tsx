"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Download, Loader2, CheckCircle } from "lucide-react";
import { downloadExcel } from "@/lib/api";

interface DownloadButtonProps {
  taskId: string;
  filename: string;
  disabled?: boolean;
}

export function DownloadButton({
  taskId,
  filename,
  disabled = false,
}: DownloadButtonProps) {
  const [downloading, setDownloading] = useState(false);
  const [downloaded, setDownloaded] = useState(false);

  const handleDownload = async () => {
    if (downloading || disabled) return;

    setDownloading(true);
    try {
      await downloadExcel(taskId, filename);
      setDownloaded(true);

      // Reset downloaded state after 3 seconds
      setTimeout(() => setDownloaded(false), 3000);
    } catch (error) {
      console.error("Download failed:", error);
    } finally {
      setDownloading(false);
    }
  };

  return (
    <Button
      onClick={handleDownload}
      disabled={disabled || downloading}
      className="gap-2"
      size="lg"
    >
      {downloading ? (
        <>
          <Loader2 className="h-5 w-5 animate-spin" />
          Downloading...
        </>
      ) : downloaded ? (
        <>
          <CheckCircle className="h-5 w-5" />
          Downloaded!
        </>
      ) : (
        <>
          <Download className="h-5 w-5" />
          Download Excel
        </>
      )}
    </Button>
  );
}
