// Type definitions mirroring backend Pydantic models

export interface Subject {
  raw_name: string | null
  normalized_name: string
  category: "ENGLISH" | "MATH" | "SCIENCE" | "SOCIAL_SCIENCE" | "SECOND_LANGUAGE" | "ADDITIONAL" | "OTHER"
  obtained_marks: number | null
  max_marks: number | null
  status: "OK" | "AB" | "COMPARTMENT" | "NON_NUMERIC" | "UNKNOWN"
  needs_review: boolean
}

export interface MarksheetRecord {
  id: string
  filename: string
  status: "pending" | "processing" | "completed" | "error" | "needs_review"
  error_message: string | null
  student_name: string | null
  board: string
  exam_session: string | null
  roll_no: string | null
  dob: string | null
  school: string | null
  result_status: "PASS" | "COMPARTMENT" | "FAIL" | "UNKNOWN"
  seat_no: string | null
  subjects: Subject[]
  overall_percent: number | null
  pcm_percent: number | null
  needs_review: boolean
  review_reasons: string[]
}

export interface Job {
  job_id: string
  status: "queued" | "processing" | "completed" | "error" | "cancelled"
  progress: number
  total_files: number
  completed_files: number
  failed_files: number
  records: MarksheetRecord[]
  created_at: string
  completed_at: string | null
  error: string | null
}

export interface CreateJobResponse {
  job_id: string
  status: string
}

export interface JobEvent {
  type: "job_start" | "progress" | "record_complete" | "complete" | "error" | "keepalive"
  data: any
}

export interface ProgressData {
  step: string
  progress: number
}

export interface RecordCompleteData {
  record_id: string
  filename: string
  status: string
}

export interface CompleteData {
  job_id: string
  total_records: number
}
