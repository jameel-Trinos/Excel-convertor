import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merge Tailwind CSS classes with clsx
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Format file size to human-readable string
 */
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return "0 B";

  const units = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  const size = bytes / Math.pow(1024, i);

  return `${size.toFixed(1)} ${units[i]}`;
}

/**
 * Validate if a file is a valid PDF
 */
export function isValidPdfFile(file: File): boolean {
  return (
    file.type === "application/pdf" ||
    file.name.toLowerCase().endsWith(".pdf")
  );
}

/**
 * Get file extension from filename
 */
export function getFileExtension(filename: string): string {
  return filename.slice(((filename.lastIndexOf(".") - 1) >>> 0) + 2);
}

/**
 * Replace file extension
 */
export function replaceExtension(
  filename: string,
  newExtension: string
): string {
  const lastDot = filename.lastIndexOf(".");
  if (lastDot === -1) return `${filename}.${newExtension}`;
  return `${filename.substring(0, lastDot)}.${newExtension}`;
}

/**
 * Truncate filename if too long
 */
export function truncateFilename(
  filename: string,
  maxLength: number = 30
): string {
  if (filename.length <= maxLength) return filename;

  const extension = getFileExtension(filename);
  const name = filename.slice(0, filename.length - extension.length - 1);
  const truncatedName = name.slice(0, maxLength - extension.length - 4) + "...";

  return `${truncatedName}.${extension}`;
}

/**
 * Clean filename by removing 'xx_' or 'ACxxx_' prefixes and '_modified' suffix.
 */
export function cleanFilename(filename: string): string {
  if (!filename) return "data";

  // Remove extension first
  const extension = getFileExtension(filename);
  let name = filename;
  if (extension) {
     name = filename.substring(0, filename.lastIndexOf("."));
  }
  
  // Remove _modified suffix if present (case insensitive)
  name = name.replace(/_modified$/i, "");
  
  // Remove "xx_" or "ACxxx_" prefix if present
  // Matches starting with alphanumeric (up to 6 chars) followed by underscore or hyphen
  // e.g., "01_Name" -> "Name", "AC001-Name" -> "Name", "149_Ariyalur" -> "Ariyalur"
  const match = name.match(/^([A-Za-z0-9]{1,6})[-_]\s*(.+)$/);
  if (match) {
      name = match[2];
  }
  
  return extension ? `${name}.${extension}` : name;
}
