import { CreateJobResponse, Job, MarksheetRecord } from "./types"

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

export async function createJob(files: File[]): Promise<CreateJobResponse> {
  const formData = new FormData()
  files.forEach(file => formData.append("files", file))

  const response = await fetch(`${API_BASE}/api/jobs`, {
    method: "POST",
    body: formData,
  })

  if (!response.ok) {
    throw new Error(`Failed to create job: ${response.statusText}`)
  }

  return response.json()
}

export async function getJob(jobId: string): Promise<Job> {
  const response = await fetch(`${API_BASE}/api/jobs/${jobId}`)

  if (!response.ok) {
    throw new Error(`Failed to get job: ${response.statusText}`)
  }

  return response.json()
}

export async function updateRecord(
  jobId: string,
  recordId: string,
  updates: Partial<MarksheetRecord>
): Promise<{ success: boolean; record: MarksheetRecord }> {
  const response = await fetch(`${API_BASE}/api/jobs/${jobId}/records/${recordId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  })

  if (!response.ok) {
    throw new Error(`Failed to update record: ${response.statusText}`)
  }

  return response.json()
}

export async function rerunExtraction(jobId: string, recordId: string): Promise<any> {
  const response = await fetch(`${API_BASE}/api/jobs/${jobId}/records/${recordId}/rerun`, {
    method: "POST",
  })

  if (!response.ok) {
    throw new Error(`Failed to rerun extraction: ${response.statusText}`)
  }

  return response.json()
}

export async function exportExcel(jobId: string): Promise<Blob> {
  const response = await fetch(`${API_BASE}/api/jobs/${jobId}/export`)

  if (!response.ok) {
    throw new Error(`Failed to export: ${response.statusText}`)
  }

  return response.blob()
}

const MAX_SSE_RETRIES = 5
const SSE_RETRY_BASE_DELAY = 1000 // ms
const SSE_MAX_DELAY = 30000 // ms - cap for exponential backoff
const POLL_INTERVAL = 3000 // ms

export class JobEventStream {
  private jobId: string
  private eventSource: EventSource | null = null
  private controllers: AbortController[] = []
  private retryCount = 0
  private isCompleted = false
  private pollTimer: ReturnType<typeof setInterval> | null = null
  private callbacks: {
    onProgress: (step: string, progress: number) => void
    onRecordComplete: (recordId: string, filename: string, status: string) => void
    onComplete: (totalRecords: number) => void
    onError: (error: string) => void
  } | null = null

  constructor(jobId: string) {
    this.jobId = jobId
  }

  connect(
    onProgress: (step: string, progress: number) => void,
    onRecordComplete: (recordId: string, filename: string, status: string) => void,
    onComplete: (totalRecords: number) => void,
    onError: (error: string) => void
  ): void {
    this.callbacks = { onProgress, onRecordComplete, onComplete, onError }
    this.connectSSE()
  }

  private connectSSE(): void {
    if (this.isCompleted || !this.callbacks) return

    const { onProgress, onRecordComplete, onComplete, onError } = this.callbacks
    const url = `${API_BASE}/api/jobs/${this.jobId}/events`
    this.eventSource = new EventSource(url)

    this.eventSource.addEventListener("job_start", (e: MessageEvent) => {
      this.retryCount = 0 // Reset on successful connection
      try {
        const data = JSON.parse(e.data)
        console.log("Job started:", data)
      } catch (err) {
        console.error("Error parsing job_start event:", err)
      }
    })

    this.eventSource.addEventListener("progress", (e: MessageEvent) => {
      this.retryCount = 0
      try {
        const data = JSON.parse(e.data)
        onProgress(data.step, data.progress)
      } catch (err) {
        console.error("Error parsing progress event:", err)
      }
    })

    this.eventSource.addEventListener("record_complete", (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data)
        onRecordComplete(data.record_id, data.filename, data.status)
      } catch (err) {
        console.error("Error parsing record_complete event:", err)
      }
    })

    this.eventSource.addEventListener("complete", (e: MessageEvent) => {
      this.isCompleted = true
      try {
        const data = JSON.parse(e.data)
        onComplete(data.total_records)
      } catch (err) {
        console.error("Error parsing complete event:", err)
      }
      this.disconnect()
    })

    this.eventSource.addEventListener("error", (e: MessageEvent) => {
      this.isCompleted = true
      try {
        const data = JSON.parse(e.data)
        onError(data.error)
      } catch (err) {
        onError("Unknown error occurred")
      }
      this.disconnect()
    })

    this.eventSource.onerror = () => {
      if (this.isCompleted) return

      // Close the broken connection
      if (this.eventSource) {
        this.eventSource.close()
        this.eventSource = null
      }

      if (this.retryCount < MAX_SSE_RETRIES) {
        const delay = Math.min(SSE_RETRY_BASE_DELAY * Math.pow(2, this.retryCount), SSE_MAX_DELAY)
        this.retryCount++
        console.log(`SSE connection lost, retrying in ${delay}ms (attempt ${this.retryCount}/${MAX_SSE_RETRIES})`)
        setTimeout(() => this.connectSSE(), delay)
      } else {
        // Fall back to polling
        console.log("SSE reconnection failed, falling back to polling")
        this.startPolling()
      }
    }
  }

  private startPolling(): void {
    if (this.isCompleted || !this.callbacks) return

    const { onProgress, onComplete, onError } = this.callbacks

    this.pollTimer = setInterval(async () => {
      try {
        const job = await getJob(this.jobId)
        onProgress(job.status, job.progress)

        if (job.status === "completed") {
          this.isCompleted = true
          onComplete(job.records.length)
          this.disconnect()
        } else if (job.status === "error") {
          this.isCompleted = true
          onError(job.error || "Processing failed")
          this.disconnect()
        }
      } catch (err) {
        console.error("Polling error:", err)
      }
    }, POLL_INTERVAL)
  }

  disconnect(): void {
    if (this.eventSource) {
      this.eventSource.close()
      this.eventSource = null
    }
    if (this.pollTimer) {
      clearInterval(this.pollTimer)
      this.pollTimer = null
    }
    this.controllers.forEach(c => c.abort())
    this.controllers = []
  }
}
