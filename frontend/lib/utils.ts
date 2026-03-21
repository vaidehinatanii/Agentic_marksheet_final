import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatPercent(value: number | null | undefined, decimals: number = 2): string {
  if (value === null || value === undefined) return "N/A"
  return `${value.toFixed(decimals)}%`
}

export function getSubjectStatusColor(status: string): string {
  switch (status) {
    case "OK":
      return "text-green-600"
    case "AB":
      return "text-red-600 font-semibold"
    case "COMPARTMENT":
      return "text-orange-600 font-semibold"
    case "NON_NUMERIC":
      return "text-yellow-600 font-semibold"
    default:
      return "text-gray-500"
  }
}

export function getRecordStatusColor(status: string): string {
  switch (status) {
    case "completed":
      return "bg-green-100 text-green-800"
    case "processing":
      return "bg-blue-100 text-blue-800"
    case "error":
      return "bg-red-100 text-red-800"
    case "needs_review":
      return "bg-yellow-100 text-yellow-800"
    case "pending":
      return "bg-gray-100 text-gray-600"
    default:
      return "bg-gray-100 text-gray-800"
  }
}
