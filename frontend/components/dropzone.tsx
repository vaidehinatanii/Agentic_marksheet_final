"use client"

import React, { useCallback, useRef, useState } from "react"
import { Upload, File, X, AlertCircle } from "lucide-react"
import { cn } from "@/lib/utils"

const MAX_FILE_SIZE = 100 * 1024 * 1024 // 100MB total
const MAX_SINGLE_FILE_SIZE = 25 * 1024 * 1024 // 25MB per file
const ALLOWED_EXTENSIONS = [".jpg", ".jpeg", ".png", ".pdf", ".zip"]
const ACCEPTED_TYPES = "image/jpeg,image/png,application/pdf,application/zip,.jpg,.jpeg,.png,.pdf,.zip"

interface DropzoneProps {
  onFilesSelected: (files: File[]) => void
  maxFiles?: number
  disabled?: boolean
}

function isAllowedFile(file: File): boolean {
  const ext = "." + file.name.split(".").pop()?.toLowerCase()
  return ALLOWED_EXTENSIONS.includes(ext)
}

export function Dropzone({
  onFilesSelected,
  maxFiles = 20,
  disabled = false,
}: DropzoneProps) {
  const [files, setFiles] = useState<File[]>([])
  const [validationError, setValidationError] = useState<string | null>(null)
  const [isDragActive, setIsDragActive] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const addFiles = useCallback(
    (incoming: File[]) => {
      setValidationError(null)

      // Filter allowed types
      const allowed = incoming.filter(isAllowedFile)
      const rejected = incoming.filter((f) => !isAllowedFile(f))
      if (rejected.length > 0) {
        setValidationError(
          `Unsupported file type: ${rejected.map((f) => f.name).join(", ")}. Only JPG, PNG, PDF, and ZIP are allowed.`
        )
        if (allowed.length === 0) return
      }

      // Validate individual file sizes
      const oversized = allowed.filter((f) => f.size > MAX_SINGLE_FILE_SIZE)
      if (oversized.length > 0) {
        setValidationError(
          `${oversized.map((f) => f.name).join(", ")} exceed${oversized.length === 1 ? "s" : ""} the 25MB per-file limit.`
        )
        return
      }

      const newFiles = [...files, ...allowed].slice(0, maxFiles)

      // Validate total size
      const totalSize = newFiles.reduce((sum, f) => sum + f.size, 0)
      if (totalSize > MAX_FILE_SIZE) {
        setValidationError(
          `Total upload size (${(totalSize / 1024 / 1024).toFixed(1)}MB) exceeds the 100MB limit.`
        )
        return
      }

      setFiles(newFiles)
      onFilesSelected(newFiles)
    },
    [files, maxFiles, onFilesSelected]
  )

  const handleClick = () => {
    if (!disabled && inputRef.current) {
      inputRef.current.click()
    }
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      addFiles(Array.from(e.target.files))
    }
    // Reset so the same file can be selected again
    if (inputRef.current) inputRef.current.value = ""
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (!disabled) setIsDragActive(true)
  }

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragActive(false)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragActive(false)
    if (disabled) return
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      addFiles(Array.from(e.dataTransfer.files))
    }
  }

  const removeFile = (index: number) => {
    const newFiles = files.filter((_, i) => i !== index)
    setFiles(newFiles)
    onFilesSelected(newFiles)
    setValidationError(null)
  }

  return (
    <div className="space-y-4">
      <div
        onClick={handleClick}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-12 text-center transition-colors",
          isDragActive
            ? "border-primary bg-primary/5"
            : "border-muted-foreground/25 hover:border-muted-foreground/50",
          disabled && "cursor-not-allowed opacity-50"
        )}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPTED_TYPES}
          onChange={handleInputChange}
          className="hidden"
          disabled={disabled}
        />
        <Upload className="mb-4 h-12 w-12 text-muted-foreground" />
        <p className="text-lg font-medium">
          {isDragActive ? "Drop files here" : "Drag & drop marksheets here"}
        </p>
        <p className="text-sm text-muted-foreground">
          or click to browse (JPG, PNG, PDF, or ZIP)
        </p>
        <p className="mt-2 text-xs text-muted-foreground">
          Max {maxFiles} files, {MAX_SINGLE_FILE_SIZE / 1024 / 1024}MB each
        </p>
      </div>

      {validationError && (
        <div className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{validationError}</span>
        </div>
      )}

      {files.length > 0 && (
        <div className="space-y-2">
          <p className="text-sm font-medium">
            Selected files ({files.length}/{maxFiles})
          </p>
          <div className="max-h-48 space-y-1 overflow-y-auto">
            {files.map((file, index) => (
              <div
                key={index}
                className="flex items-center justify-between rounded-md bg-muted px-3 py-2 text-sm"
              >
                <div className="flex items-center gap-2 overflow-hidden">
                  <File className="h-4 w-4 shrink-0" />
                  <span className="truncate">{file.name}</span>
                  <span className="text-xs text-muted-foreground">
                    ({(file.size / 1024).toFixed(0)} KB)
                  </span>
                </div>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation()
                    removeFile(index)
                  }}
                  className="shrink-0 rounded-full p-1 hover:bg-destructive hover:text-destructive-foreground"
                  disabled={disabled}
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
