"use client"

import React, { useState, useCallback, useRef } from "react"
import { Download, Upload, FileSpreadsheet } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Dropzone } from "@/components/dropzone"
import { ProgressPanel } from "@/components/progress-panel"
import { RecordsTable } from "@/components/records-table"
import { EditDrawer } from "@/components/edit-drawer"
import { useToast } from "@/components/ui/use-toast"
import {
  createJob,
  getJob,
  updateRecord,
  exportExcel,
  JobEventStream,
} from "@/lib/api"
import type { MarksheetRecord } from "@/lib/types"

export default function HomePage() {
  const { toast } = useToast()
  const [files, setFiles] = useState<File[]>([])
  const [jobId, setJobId] = useState<string | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [isComplete, setIsComplete] = useState(false)
  const [progress, setProgress] = useState(0)
  const [currentStep, setCurrentStep] = useState("")
  const [totalFiles, setTotalFiles] = useState(0)
  const [completedFiles, setCompletedFiles] = useState(0)
  const [failedFiles, setFailedFiles] = useState(0)
  const [records, setRecords] = useState<MarksheetRecord[]>([])
  const [editingRecord, setEditingRecord] = useState<MarksheetRecord | null>(
    null
  )
  const [isEditOpen, setIsEditOpen] = useState(false)
  const [isExporting, setIsExporting] = useState(false)

  const eventStreamRef = useRef<JobEventStream | null>(null)

  const handleFilesSelected = useCallback((selectedFiles: File[]) => {
    setFiles(selectedFiles)
  }, [])

  const handleStartProcessing = async () => {
    if (files.length === 0) {
      toast({
        title: "No files selected",
        description: "Please select at least one file to process.",
        variant: "destructive",
      })
      return
    }

    setIsProcessing(true)
    setProgress(0)
    setCurrentStep("ingest")
    setTotalFiles(files.length)
    setCompletedFiles(0)
    setFailedFiles(0)
    setRecords([])

    try {
      // Create job
      const response = await createJob(files)
      const newJobId = response.job_id
      setJobId(newJobId)

      // Connect to SSE
      const stream = new JobEventStream(newJobId)
      eventStreamRef.current = stream

      stream.connect(
        // onProgress
        (step, progressValue) => {
          setProgress(progressValue)
          setCurrentStep(step)
        },
        // onRecordComplete
        (recordId, filename, status) => {
          setCompletedFiles((prev) => prev + 1)
          if (status === "error") {
            setFailedFiles((prev) => prev + 1)
          }
        },
        // onComplete
        async (totalRecords) => {
          // Fetch final job state
          const job = await getJob(newJobId)
          setRecords(job.records)
          setIsProcessing(false)
          setIsComplete(true)
          setProgress(100)

          toast({
            title: "Processing complete!",
            description: `Successfully processed ${totalRecords} marksheets.`,
          })
        },
        // onError
        (error) => {
          setIsProcessing(false)
          toast({
            title: "Processing error",
            description: error,
            variant: "destructive",
          })
        }
      )
    } catch (error) {
      setIsProcessing(false)
      toast({
        title: "Failed to start processing",
        description:
          error instanceof Error ? error.message : "Unknown error occurred",
        variant: "destructive",
      })
    }
  }

  const handleEdit = useCallback((record: MarksheetRecord) => {
    setEditingRecord(record)
    setIsEditOpen(true)
  }, [])

  const handleSaveRecord = async (
    recordId: string,
    updates: Partial<MarksheetRecord>
  ) => {
    if (!jobId) return

    try {
      const response = await updateRecord(jobId, recordId, updates)

      // Update local records
      setRecords((prev) =>
        prev.map((r) => (r.id === recordId ? response.record : r))
      )

      toast({
        title: "Record updated",
        description: "Changes saved successfully.",
      })

      return response
    } catch (error) {
      toast({
        title: "Failed to save",
        description:
          error instanceof Error ? error.message : "Unknown error occurred",
        variant: "destructive",
      })
      throw error
    }
  }

  const handleExport = async () => {
    if (!jobId) return

    setIsExporting(true)
    try {
      const blob = await exportExcel(jobId)

      // Download the file
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `marksheet_results_${jobId}.xlsx`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      window.URL.revokeObjectURL(url)

      toast({
        title: "Export complete",
        description: "Excel file downloaded successfully.",
      })
    } catch (error) {
      toast({
        title: "Export failed",
        description:
          error instanceof Error ? error.message : "Unknown error occurred",
        variant: "destructive",
      })
    } finally {
      setIsExporting(false)
    }
  }

  const handleReset = useCallback(() => {
    if (eventStreamRef.current) {
      eventStreamRef.current.disconnect()
      eventStreamRef.current = null
    }
    setFiles([])
    setJobId(null)
    setIsProcessing(false)
    setIsComplete(false)
    setProgress(0)
    setCurrentStep("")
    setTotalFiles(0)
    setCompletedFiles(0)
    setFailedFiles(0)
    setRecords([])
  }, [])

  return (
    <main className="min-h-screen bg-background p-6">
      <div className="mx-auto max-w-7xl space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">CBSE Marksheet Processor</h1>
            <p className="text-sm text-muted-foreground">
              Upload marksheets to extract and compute student marks using AI
            </p>
          </div>
          {isComplete && (
            <Button onClick={handleReset} variant="outline">
              Start New Batch
            </Button>
          )}
        </div>

        {/* Main Content */}
        <div className="grid gap-6 lg:grid-cols-3">
          {/* Left Column - Upload */}
          <div className="lg:col-span-2 space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Upload className="h-5 w-5" />
                  Upload Marksheets
                </CardTitle>
              </CardHeader>
              <CardContent>
                <Dropzone
                  onFilesSelected={handleFilesSelected}
                  disabled={isProcessing}
                  maxFiles={20}
                />
                {files.length > 0 && !isProcessing && !isComplete && (
                  <div className="mt-4 flex justify-end">
                    <Button onClick={handleStartProcessing} size="lg">
                      Start Processing ({files.length} files)
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Records Table */}
            {records.length > 0 && (
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle>Extracted Records</CardTitle>
                    <Button
                      onClick={handleExport}
                      disabled={isExporting}
                      variant="outline"
                      size="sm"
                    >
                      {isExporting ? (
                        "Exporting..."
                      ) : (
                        <>
                          <FileSpreadsheet className="mr-2 h-4 w-4" />
                          Export Excel
                        </>
                      )}
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  <RecordsTable records={records} onEdit={handleEdit} />
                </CardContent>
              </Card>
            )}
          </div>

          {/* Right Column - Progress */}
          <div className="space-y-6">
            <ProgressPanel
              progress={progress}
              currentStep={currentStep}
              totalFiles={totalFiles}
              completedFiles={completedFiles}
              failedFiles={failedFiles}
              isProcessing={isProcessing}
              isComplete={isComplete}
            />

            {/* Quick Stats */}
            {isComplete && records.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle>Summary</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Total Students:</span>
                    <span className="font-medium">{records.length}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Need Review:</span>
                    <span className="font-medium text-orange-600">
                      {records.filter((r) => r.needs_review).length}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Avg Best 5 %:</span>
                    <span className="font-medium">
                      {(() => {
                        const valid = records.filter((r) => r.overall_percent !== null)
                        if (valid.length === 0) return "N/A"
                        const avg = valid.reduce((sum, r) => sum + (r.overall_percent || 0), 0) / valid.length
                        return `${avg.toFixed(2)}%`
                      })()}
                    </span>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </div>

      {/* Edit Drawer */}
      {jobId && (
        <EditDrawer
          record={editingRecord}
          open={isEditOpen}
          onOpenChange={setIsEditOpen}
          onSave={handleSaveRecord}
          jobId={jobId}
        />
      )}
    </main>
  )
}
