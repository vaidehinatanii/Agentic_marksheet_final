"use client"

import React from "react"
import { Progress } from "@/components/ui/progress"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { CheckCircle, XCircle, Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"

interface ProgressPanelProps {
  progress: number
  currentStep: string
  totalFiles: number
  completedFiles: number
  failedFiles: number
  isProcessing: boolean
  isComplete: boolean
}

export function ProgressPanel({
  progress,
  currentStep,
  totalFiles,
  completedFiles,
  failedFiles,
  isProcessing,
  isComplete,
}: ProgressPanelProps) {
  const getStepLabel = (step: string) => {
    const stepLabels: Record<string, string> = {
      ingest: "Reading files...",
      canonicalize: "Converting to images...",
      preprocess: "Enhancing images...",
      extract: "Extracting data with AI...",
      validate: "Validating results...",
      repair: "Fixing extraction issues...",
      normalize: "Normalizing subjects...",
      compute: "Computing percentages...",
      checkpoint: "Finalizing results...",
      cleanup: "Cleaning up...",
      cleanup_complete: "Done!",
      completed: "Processing complete!",
    }
    return stepLabels[step] || step
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>Processing Status</span>
          {isProcessing && (
            <Loader2 className="h-5 w-5 animate-spin text-primary" />
          )}
          {isComplete && (
            <CheckCircle className="h-5 w-5 text-green-600" />
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <Progress value={progress} className="h-2" />

        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">
            {currentStep ? getStepLabel(currentStep) : "Waiting to start..."}
          </span>
          <span className="font-medium">{Math.round(progress)}%</span>
        </div>

        <div className="grid grid-cols-3 gap-4 pt-2">
          <div className="flex flex-col items-center rounded-lg bg-muted/50 p-3">
            <span className="text-2xl font-semibold">{totalFiles}</span>
            <span className="text-xs text-muted-foreground">Total Files</span>
          </div>
          <div className="flex flex-col items-center rounded-lg bg-green-100 p-3">
            <span className="text-2xl font-semibold text-green-700">
              {completedFiles}
            </span>
            <span className="text-xs text-green-700">Completed</span>
          </div>
          <div
            className={cn(
              "flex flex-col items-center rounded-lg p-3",
              failedFiles > 0
                ? "bg-red-100"
                : "bg-muted/50"
            )}
          >
            <span
              className={cn(
                "text-2xl font-semibold",
                failedFiles > 0 ? "text-red-700" : ""
              )}
            >
              {failedFiles}
            </span>
            <span
              className={cn(
                "text-xs",
                failedFiles > 0 ? "text-red-700" : "text-muted-foreground"
              )}
            >
              Failed
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
