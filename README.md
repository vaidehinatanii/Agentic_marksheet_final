# Agentic Marksheet Processor

An AI-powered, agentic web application that automatically extracts, validates, and computes marks from CBSE Class 12 marksheets. Built with a **LangGraph agentic workflow** on the backend and a **Next.js** frontend, it processes batches of marksheet images/PDFs and produces structured, export-ready data with minimal human intervention.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Agentic Workflow (LangGraph Pipeline)](#agentic-workflow-langgraph-pipeline)
  - [Agent 1 — Ingest](#agent-1--ingest)
  - [Agent 2 — Canonicalize](#agent-2--canonicalize)
  - [Agent 3 — Preprocess](#agent-3--preprocess)
  - [Agent 4 — Extract](#agent-4--extract)
  - [Agent 5 — Validate](#agent-5--validate)
  - [Agent 6 — Repair](#agent-6--repair)
  - [Agent 7 — Normalize](#agent-7--normalize)
  - [Agent 8 — Compute](#agent-8--compute)
  - [Agent 9 — Checkpoint](#agent-9--checkpoint)
  - [Agent 10 — Cleanup](#agent-10--cleanup)
- [Frontend Application](#frontend-application)
- [Backend API](#backend-api)
- [Data Models](#data-models)
- [Subject Normalization & Fuzzy Matching](#subject-normalization--fuzzy-matching)
- [Percentage Computation Logic](#percentage-computation-logic)
- [Excel Export](#excel-export)
- [Storage Layer](#storage-layer)
- [Security](#security)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Setup & Installation](#setup--installation)
- [Running the Application](#running-the-application)
- [Running Tests](#running-tests)
- [Environment Variables](#environment-variables)
- [API Reference](#api-reference)
- [Tech Stack](#tech-stack)

---

## Overview

Processing hundreds of CBSE marksheets manually is tedious and error-prone. This application solves that by:

1. **Accepting bulk uploads** — drag-and-drop images, PDFs, or ZIP archives containing marksheets.
2. **Running an agentic AI pipeline** — a 10-node LangGraph workflow ingests files, preprocesses images, calls OpenAI Vision for structured extraction, validates results, auto-repairs failures, normalizes subject names, and computes percentages.
3. **Providing human-in-the-loop review** — extracted data is presented in an editable table where users can correct any AI mistakes before export.
4. **Exporting to Excel** — a formatted `.xlsx` file with conditional highlighting for problematic cells.

All of this happens with **real-time progress streaming** via Server-Sent Events (SSE), so users see each step as it completes.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (Next.js)                       │
│  ┌──────────┐  ┌───────────────┐  ┌────────────┐  ┌──────────┐ │
│  │ Dropzone  │  │ Progress Panel│  │ Records    │  │  Edit    │ │
│  │ (upload)  │  │ (SSE stream)  │  │ Table      │  │  Drawer  │ │
│  └─────┬────┘  └───────┬───────┘  └─────┬──────┘  └────┬─────┘ │
│        │               │                │               │       │
│        └───────────────┼────────────────┼───────────────┘       │
│                        │ REST + SSE     │                       │
└────────────────────────┼────────────────┼───────────────────────┘
                         │                │
┌────────────────────────┼────────────────┼───────────────────────┐
│                    Backend (FastAPI)     │                       │
│  ┌─────────────────────┴────────────────┴─────────────────────┐ │
│  │                    API Routes Layer                         │ │
│  │  POST /api/jobs  GET /api/jobs/:id  GET /api/jobs/:id/events│ │
│  │  PATCH /api/jobs/:id/records/:id    GET /api/jobs/:id/export│ │
│  └─────────────────────┬──────────────────────────────────────┘ │
│                        │                                        │
│  ┌─────────────────────┴──────────────────────────────────────┐ │
│  │              LangGraph Agentic Workflow                     │ │
│  │                                                             │ │
│  │  ingest → canonicalize → preprocess → extract → validate    │ │
│  │                                          │                  │ │
│  │                                    ┌─────┴──────┐           │ │
│  │                                    │ needs      │           │ │
│  │                                    │ repair?    │           │ │
│  │                                    └──┬─────┬───┘           │ │
│  │                                   yes │     │ no            │ │
│  │                                       ▼     │               │ │
│  │                                    repair   │               │ │
│  │                                       │     │               │ │
│  │                                       └──┬──┘               │ │
│  │                                          ▼                  │ │
│  │                    normalize → compute → checkpoint → cleanup│ │
│  └─────────────────────────────────────────────────────────────┘ │
│                        │                                        │
│  ┌─────────────────────┴──────────────────────────────────────┐ │
│  │                    Services Layer                           │ │
│  │  OpenAI Client  │  Preprocess  │  Normalize  │  Excel Export│ │
│  └─────────────────────────────────────────────────────────────┘ │
│                        │                                        │
│  ┌─────────────────────┴──────────────────────────────────────┐ │
│  │              Storage (Redis / In-Memory)                    │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## Agentic Workflow (LangGraph Pipeline)

The core intelligence lives in a **LangGraph `StateGraph`** — a directed acyclic graph of 10 autonomous agent nodes. Each node receives the shared `GraphState`, performs its task, updates the state, and passes it to the next node. The graph includes a **conditional edge** after validation that dynamically routes to a repair agent when extraction quality is insufficient.

**Graph State** — the shared context passed between all agents:

| Field | Type | Description |
|-------|------|-------------|
| `job_id` | `str` | Unique batch job identifier |
| `files` | `List[dict]` | Uploaded file metadata (name, path) |
| `images` | `List[dict]` | Processed image data (bytes, base64) |
| `extractions` | `List[dict]` | Raw AI extraction results |
| `records` | `List[MarksheetRecord]` | Final structured records |
| `errors` | `List[str]` | Accumulated error messages |
| `current_step` | `str` | Name of the currently executing agent |
| `progress` | `float` | Overall progress (0.0 to 100.0) |
| `needs_interrupt` | `bool` | Flag for human-in-the-loop checkpoint |

---

### Agent 1 — Ingest

**File:** `backend/app/graph/nodes.py` — `ingest_node()`

**Purpose:** Accept uploaded files and enumerate valid files for processing.

**What it does:**
- Iterates over all uploaded files in the state.
- Validates file extensions against an allowlist: `.jpg`, `.jpeg`, `.png`, `.pdf`, `.zip`.
- If a file is a **ZIP archive**, it performs security validation (zip-slip protection), then extracts individual members and adds each valid file to the processing list.
- For non-ZIP files, adds them directly to the processing list.
- Sets progress to **10%**.

**Inputs:** Raw uploaded file paths.
**Outputs:** A flat list of individual files (images/PDFs) ready for conversion.

---

### Agent 2 — Canonicalize

**File:** `backend/app/graph/nodes.py` — `canonicalize_node()`

**Purpose:** Convert all files into a uniform image format.

**What it does:**
- Reads each file from disk.
- PDFs are rendered to high-resolution PNG images using **PyMuPDF** at **400 DPI** for maximum OCR accuracy.
- JPEG/PNG files are passed through as-is.
- Other image formats are converted to RGB PNG using Pillow.
- Sets progress to **20%**.

**Inputs:** File paths from the ingest stage.
**Outputs:** Image bytes + MIME type for each file.

---

### Agent 3 — Preprocess

**File:** `backend/app/graph/nodes.py` — `preprocess_node()`

**Purpose:** Enhance images for optimal AI vision extraction.

**What it does:**
- Processes all images **concurrently** using an `asyncio.Semaphore` (bounded by `CONCURRENT_LIMIT`).
- For each image, applies the preprocessing pipeline:
  1. **Resize** — scales down images exceeding 4096px while preserving aspect ratio (Lanczos resampling).
  2. **Deskew** — detects and corrects rotation using OpenCV's Hough transform (`minAreaRect` on thresholded text pixels).
  3. **CLAHE Enhancement** — applies Contrast Limited Adaptive Histogram Equalization in LAB color space for locally-adaptive contrast improvement.
  4. **Contrast boost** — PIL `ImageEnhance.Contrast` at 1.5x.
  5. **Sharpening** — PIL `ImageEnhance.Sharpness` at 2.0x, followed by `UnsharpMask`.
  6. **Denoising** — median filter (3x3 kernel) to reduce noise without losing edges.
- Converts processed images to **base64 data URLs** for the OpenAI API.
- Sets progress to **30%**.

**Inputs:** Raw image bytes.
**Outputs:** Preprocessed base64-encoded images.

---

### Agent 4 — Extract

**File:** `backend/app/graph/nodes.py` — `extract_node()`

**Purpose:** Call OpenAI Vision API to extract structured data from marksheet images.

**What it does:**
- Uses `OpenAIExtractionService` to send each image to the **GPT-4o** model with a detailed system prompt and structured output schema.
- Processes images in **configurable batches** (default batch size: 3) with concurrent API calls within each batch.
- Uses **OpenAI Structured Outputs** (`json_schema` response format with `strict: true`) to guarantee the response matches the extraction schema.
- If the primary model (GPT-4o) fails, automatically retries with the **fallback model** (GPT-4o-mini).
- Extracts: student name, board, exam session, roll number, DOB, school, result status, seat number, and up to 6 subjects with obtained marks, max marks, and status.
- Progress advances from **30% to 65%** across batches.

**System Prompt Highlights:**
- Detailed instructions for identifying the student name vs. mother's/father's name on CBSE marksheets.
- Instructions for extracting TOTAL marks (not theory/practical separately).
- Subject status codes: OK, AB (absent), COMPARTMENT, NON_NUMERIC, UNKNOWN.
- All fields are required in the response (uses empty strings/zeros as defaults).

**Inputs:** Base64-encoded preprocessed images.
**Outputs:** Raw extraction dictionaries with student info and subject marks.

---

### Agent 5 — Validate

**File:** `backend/app/graph/nodes.py` — `validate_and_route_node()`

**Purpose:** Quality-check extractions and decide if repair is needed.

**What it does:**
- For each extraction, checks:
  - Is `student_name` present?
  - Are there at least 5 subjects?
  - Do at least 3 subjects have valid `max_marks`?
- Sets a `needs_repair` flag on any extraction that fails these checks.
- This flag drives the **conditional edge** in the graph — if any extraction needs repair, the graph routes to the Repair agent; otherwise, it skips directly to Normalize.
- Sets progress to **70%**.

**Conditional Routing Logic:**
```python
def should_repair(state) -> "repair" | "normalize":
    for extraction in state["extractions"]:
        if extraction.get("needs_repair"):
            return "repair"
    return "normalize"
```

---

### Agent 6 — Repair

**File:** `backend/app/graph/nodes.py` — `repair_node()`

**Purpose:** Re-extract data for failed marksheets using the fallback model.

**What it does:**
- Only processes extractions where `needs_repair = True`.
- Re-sends the original preprocessed image to the OpenAI API using `extract_with_fallback()` (tries primary model first, then fallback).
- Replaces the failed extraction data with the new result.
- Sets progress to **75%**.

**Inputs:** Failed extractions + original preprocessed images.
**Outputs:** Repaired extraction data (or original if repair also fails).

---

### Agent 7 — Normalize

**File:** `backend/app/graph/nodes.py` — `normalize_node()`

**Purpose:** Standardize subject names and create structured `MarksheetRecord` objects.

**What it does:**
- For each extraction, normalizes subject names using **fuzzy matching** (see [Subject Normalization](#subject-normalization--fuzzy-matching)).
- Creates `MarksheetRecord` objects with normalized subjects, categorized by type (ENGLISH, MATH, SCIENCE, SOCIAL_SCIENCE, SECOND_LANGUAGE, ADDITIONAL).
- Calls `update_record_computations()` to calculate Best-of-5 and Core percentages.
- Sets `needs_review` flags and generates human-readable review reasons.
- Pads to 6 subjects (5 main + 1 additional) if fewer are extracted.
- Sets progress to **85%**.

---

### Agent 8 — Compute

**File:** `backend/app/graph/nodes.py` — `compute_node()`

**Purpose:** Final computation step and progress update.

**What it does:**
- Acts as a finalization checkpoint (primary computation is done in Normalize).
- Sets progress to **95%**.

---

### Agent 9 — Checkpoint

**File:** `backend/app/graph/nodes.py` — `checkpoint_interrupt_node()`

**Purpose:** Human-in-the-loop checkpoint.

**What it does:**
- Marks the job as complete.
- Sets `needs_interrupt = True` to signal the UI that results are ready for human review.
- Sets progress to **100%**.

---

### Agent 10 — Cleanup

**File:** `backend/app/graph/nodes.py` — `cleanup_node()`

**Purpose:** Clean up temporary files and free memory.

**What it does:**
- Deletes temporary image files from `/tmp/marksheet_uploads/`.
- Clears in-memory image bytes and base64 data from the state to free RAM.
- Only deletes files that are within the temp directory (security check via `is_relative_to`).

---

## Frontend Application

**Stack:** Next.js 15, React 19, TypeScript, Tailwind CSS, shadcn/ui, react-dropzone

### Components

| Component | File | Description |
|-----------|------|-------------|
| **Dropzone** | `frontend/components/dropzone.tsx` | Drag-and-drop file upload zone. Accepts JPG, PNG, PDF, and ZIP files. Shows selected files with sizes and allows removal. Max 20 files per batch. |
| **Progress Panel** | `frontend/components/progress-panel.tsx` | Real-time processing status card. Shows a progress bar, current step label (e.g., "Extracting data with AI..."), and counters for total/completed/failed files. Connects to the backend SSE stream. |
| **Records Table** | `frontend/components/records-table.tsx` | Expandable data table showing extracted records. Each row shows filename, status badge, student name, roll number, Best-5 %, Core %, and review flag. Clicking a row expands to show all 6 subjects with marks and status badges. |
| **Edit Drawer** | `frontend/components/edit-drawer.tsx` | Modal dialog for editing a record. Allows modification of student info (name, roll no, session, school, DOB, seat no) and all subject fields (name, obtained marks, max marks, status). Shows a live preview of recomputed percentages. |
| **Toaster** | `frontend/components/ui/toaster.tsx` | Toast notification system for success/error messages. |

### API Client

**File:** `frontend/lib/api.ts`

- `createJob(files)` — POST multipart upload to create a batch job.
- `getJob(jobId)` — GET job status and all records.
- `updateRecord(jobId, recordId, updates)` — PATCH to update a record after review.
- `rerunExtraction(jobId, recordId)` — POST to re-extract a single record.
- `exportExcel(jobId)` — GET to download the Excel file as a blob.
- `JobEventStream` — SSE client class that listens for `job_start`, `progress`, `record_complete`, `complete`, and `error` events.

### Proxy Configuration

The Next.js app proxies `/api/*` requests to the backend at `http://localhost:8000` via `next.config.js` rewrites, eliminating CORS issues during development.

---

## Backend API

**Framework:** FastAPI with async support

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/jobs` | Upload files and create a new batch processing job. Returns `job_id`. |
| `GET` | `/api/jobs/{job_id}` | Get full job status, progress, and all extracted records. |
| `GET` | `/api/jobs/{job_id}/events` | SSE stream for real-time progress updates. |
| `PATCH` | `/api/jobs/{job_id}/records/{record_id}` | Update a record after human review. Server recomputes percentages. |
| `POST` | `/api/jobs/{job_id}/records/{record_id}/rerun` | Re-run extraction for a specific record. |
| `GET` | `/api/jobs/{job_id}/export` | Download results as a formatted Excel file. |
| `GET` | `/api/health` | Health check endpoint. |

### SSE Event Types

| Event | Payload | Description |
|-------|---------|-------------|
| `job_start` | `{job_id, total_files, status}` | Job has been created and processing started |
| `progress` | `{step, progress}` | Current processing step and percentage |
| `record_complete` | `{record_id, filename, status}` | Individual file processing completed |
| `complete` | `{job_id, total_records}` | All files processed |
| `error` | `{error}` | Processing error occurred |

---

## Data Models

**File:** `backend/app/models.py`

### SubjectExtract
Raw subject data as returned by the OpenAI API:
- `subject_name`, `obtained_marks`, `max_marks`, `status` (OK/AB/COMPARTMENT/NON_NUMERIC/UNKNOWN)

### SubjectNormalized
Cleaned subject with category classification:
- `raw_name` — original name from extraction
- `normalized_name` — canonical name after fuzzy matching
- `category` — ENGLISH, MATH, SCIENCE, SOCIAL_SCIENCE, SECOND_LANGUAGE, ADDITIONAL, or OTHER
- `obtained_marks`, `max_marks`, `status`, `needs_review`

### MarksheetRecord
Complete processed record for one student:
- Student info: `student_name`, `board`, `exam_session`, `roll_no`, `dob`, `school`, `result_status`, `seat_no`
- `subjects` — list of 6 `SubjectNormalized` objects
- Computed: `overall_percent` (Best-of-5), `pcm_percent` (Core %), `needs_review`, `review_reasons`

### Job
Batch processing job:
- `id`, `status` (queued/processing/completed/error), `progress`, `total_files`, `completed_files`, `failed_files`, `records`, `created_at`, `completed_at`

---

## Subject Normalization & Fuzzy Matching

**File:** `backend/app/services/normalize.py`

The normalization service maps messy OCR-extracted subject names to canonical forms using a two-step process:

### Step 1: Direct Match
Check the raw name against a dictionary of **80+ known variants** across 20+ canonical subjects:
```
"ENGLISH CORE" → ENGLISH
"Physics (042)" → PHYSICS
"HINDI COURSE A" → HINDI
"MATHEMATICS BASIC" → MATHEMATICS
```

### Step 2: Fuzzy Match (rapidfuzz)
If no direct match, use **weighted ratio scoring** (`fuzz.WRatio`) against all known variant names. A match above **80% similarity** is accepted.

### Category Classification
Each normalized subject is classified into one of 7 categories:
- **ENGLISH** — English Core, English Elective, English Communicative
- **MATH** — Mathematics, Applied Mathematics, Mathematics Basic
- **SCIENCE** — Science, Physics, Chemistry, Biology
- **SOCIAL_SCIENCE** — Social Science, History, Geography, Civics, Political Science, Economics
- **SECOND_LANGUAGE** — Hindi, Sanskrit, French, German, regional languages
- **ADDITIONAL** — Computer Science, Art, Music, Physical Education, 6th subject
- **OTHER** — unrecognized subjects

---

## Percentage Computation Logic

**File:** `backend/app/services/normalize.py`

### Best-of-5 Percentage (`overall_percent`)
1. English, Math, and Science are **mandatory** — they must be included if available with valid marks.
2. From the remaining subjects (Social Science, Second Language, Additional), pick the **top 2 by percentage** to complete the Best 5.
3. Calculate: `(sum of obtained marks for best 5) / (sum of max marks for best 5) * 100`
4. Returns `None` if fewer than 5 valid subjects are available.

### Core Percentage (`pcm_percent`)
1. Requires all 4 core subjects: English, Math, Science, Social Science.
2. Computes the **average of individual subject percentages**.
3. Returns `None` if any core subject is missing or has invalid marks.

### Review Reasons
Automatically generated reasons when a record needs human review:
- Subject has non-OK status (AB, COMPARTMENT, etc.)
- Missing obtained marks or max marks
- Cannot compute Best-of-5 or Core percentage

---

## Excel Export

**File:** `backend/app/services/excel_export.py`

Generates a formatted `.xlsx` file using openpyxl with:

- **Header row** with bold font, gray background, and frozen panes.
- **33 columns**: student info (5) + 6 subjects x 4 fields each (24) + computed fields (4).
- **Conditional formatting**:
  - Red fill for cells with non-OK status (AB, COMPARTMENT, etc.)
  - Yellow fill for missing obtained marks or max marks
  - Red fill for the "Needs Review" and "Review Reasons" columns on flagged records
- **Column auto-sizing** for readability.

---

## Storage Layer

**File:** `backend/app/services/storage.py`

Dual-backend storage service:

| Backend | When Used | TTL |
|---------|-----------|-----|
| **Redis** | When `REDIS_URL` is configured and Redis is reachable | 1 hour per job |
| **In-Memory** | Automatic fallback when Redis is unavailable | Session lifetime |

The storage service manages CRUD operations for `Job` and `MarksheetRecord` objects, serialized as JSON via Pydantic's `model_dump_json()`.

---

## Security

- **ZIP Slip Protection** — validates all ZIP entries for path traversal (`..`) and absolute paths (`/`) before extraction.
- **File Size Limits** — configurable max upload size (default 100 MB).
- **File Type Allowlist** — only `.jpg`, `.jpeg`, `.png`, `.pdf`, and `.zip` files are accepted.
- **CORS Configuration** — restricted to configured origins.
- **Temp File Cleanup** — automatic cleanup of temporary files on job completion and application shutdown.
- **Path Traversal Guard** — cleanup only deletes files verified to be within the temp directory via `is_relative_to()`.

---

## Project Structure

```
MUJ_Marksheet/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI app, routes, SSE, background tasks
│   │   ├── config.py                # Pydantic settings (env vars)
│   │   ├── models.py                # All data models + OpenAI JSON schema
│   │   ├── graph/
│   │   │   ├── __init__.py
│   │   │   ├── batch_graph.py       # LangGraph StateGraph definition + conditional edges
│   │   │   └── nodes.py             # All 10 agent node implementations
│   │   └── services/
│   │       ├── __init__.py
│   │       ├── openai_client.py     # OpenAI Vision API client + system prompts
│   │       ├── preprocess.py        # Image preprocessing (deskew, CLAHE, sharpen)
│   │       ├── normalize.py         # Subject fuzzy matching + % computation
│   │       ├── excel_export.py      # Formatted Excel generation
│   │       └── storage.py           # Redis / in-memory storage service
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_normalize.py        # Subject normalization + computation tests
│   │   ├── test_validation.py       # Pydantic model validation tests
│   │   └── test_zip_security.py     # ZIP slip attack prevention tests
│   ├── requirements.txt             # Python dependencies
│   └── venv/                        # Virtual environment (not committed)
├── frontend/
│   ├── app/
│   │   ├── layout.tsx               # Root layout with Toaster
│   │   ├── page.tsx                 # Main page (upload → process → review → export)
│   │   └── globals.css              # Tailwind base styles
│   ├── components/
│   │   ├── dropzone.tsx             # Drag-and-drop file upload
│   │   ├── progress-panel.tsx       # Real-time progress display
│   │   ├── records-table.tsx        # Expandable results table
│   │   ├── edit-drawer.tsx          # Record editing modal
│   │   └── ui/                      # shadcn/ui primitives (button, card, dialog, etc.)
│   ├── lib/
│   │   ├── api.ts                   # API client + SSE event stream
│   │   ├── types.ts                 # TypeScript type definitions
│   │   └── utils.ts                 # Formatting + status color helpers
│   ├── next.config.js               # API proxy rewrites
│   ├── tailwind.config.ts           # Tailwind configuration
│   ├── postcss.config.js
│   ├── package.json                 # Node dependencies
│   └── tsconfig.json
├── .env.example                     # Environment variable template
├── .gitignore
├── setup.sh                         # One-command setup script
└── README.md                        # This file
```

---

## Prerequisites

| Requirement | Version | Purpose |
|------------|---------|---------|
| Python | 3.11+ | Backend runtime |
| Node.js | 18+ | Frontend runtime |
| OpenAI API Key | — | GPT-4o Vision for extraction (required) |
| Redis | 6+ | Job state persistence (optional — falls back to in-memory) |

---

## Setup & Installation

### Option 1: Automated Setup

```bash
cd /path/to/MUJ_Marksheet
chmod +x setup.sh
./setup.sh
```

This script automatically detects your Python version, creates a virtual environment, installs all backend and frontend dependencies, and creates the `.env` file.

### Option 2: Manual Setup

**Backend:**

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # On Windows: venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
cp ../.env.example .env
```

**Frontend:**

```bash
cd frontend
npm install
```

### Configure Your API Key

Edit `backend/.env` and set your OpenAI API key:

```env
OPENAI_API_KEY=sk-your-actual-openai-api-key
```

---

## Running the Application

You need **two terminals** (three if using Redis):

**Terminal 1 — Backend:**

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 — Frontend:**

```bash
cd frontend
npm run dev
```

**Terminal 3 — Redis (optional):**

```bash
redis-server
```

### Access Points

| URL | Description |
|-----|-------------|
| http://localhost:3000 | Frontend application |
| http://localhost:8000 | Backend API |
| http://localhost:8000/docs | Interactive Swagger API documentation |

---

## Running Tests

```bash
cd backend
source venv/bin/activate
pytest tests/ -v
```

**Test coverage includes:**
- Subject name normalization (English variants, Physics variants, unknown subjects)
- Percentage computations (overall, PCM, edge cases with missing data)
- Pydantic model validation (SubjectExtract, MarksheetExtract, MarksheetRecord)
- ZIP security (zip slip attacks, absolute path attacks, empty ZIPs)
- Review reason generation

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | — | OpenAI API key with GPT-4o access |
| `REDIS_URL` | No | `redis://localhost:6379` | Redis connection URL |
| `MAX_UPLOAD_SIZE` | No | `104857600` (100 MB) | Maximum total upload size in bytes |
| `CONCURRENT_LIMIT` | No | `20` | Maximum concurrent OCR/preprocessing tasks |
| `BATCH_SIZE` | No | `3` | Number of images per extraction batch |
| `ALLOWED_ORIGINS` | No | `http://localhost:3000,http://localhost:3001` | CORS allowed origins |
| `APP_ENV` | No | `development` | Application environment |
| `LOG_LEVEL` | No | `info` | Logging level |
| `OPENAI_PRIMARY_MODEL` | No | `gpt-4o-2024-08-06` | Primary extraction model |
| `OPENAI_FALLBACK_MODEL` | No | `gpt-4o-mini-2024-07-18` | Fallback extraction model |
| `PDF_RENDER_DPI` | No | `400` | DPI for PDF to image conversion |
| `MAX_IMAGE_DIMENSION` | No | `4096` | Max image dimension before resize |

---

## API Reference

### Create Job

```http
POST /api/jobs
Content-Type: multipart/form-data

files: <file1>
files: <file2>
...
```

**Response (201):**
```json
{
  "job_id": "uuid-string",
  "status": "queued"
}
```

### Get Job

```http
GET /api/jobs/{job_id}
```

**Response (200):**
```json
{
  "job_id": "...",
  "status": "completed",
  "progress": 100.0,
  "total_files": 5,
  "completed_files": 5,
  "failed_files": 0,
  "records": [...],
  "created_at": "2024-01-01T00:00:00",
  "completed_at": "2024-01-01T00:01:00"
}
```

### SSE Event Stream

```http
GET /api/jobs/{job_id}/events
Accept: text/event-stream
```

### Update Record

```http
PATCH /api/jobs/{job_id}/records/{record_id}
Content-Type: application/json

{
  "student_name": "Corrected Name",
  "subjects": [...]
}
```

### Export Excel

```http
GET /api/jobs/{job_id}/export
```

Returns: `.xlsx` file download.

---

## Tech Stack

### Backend
| Technology | Purpose |
|-----------|---------|
| **FastAPI** | Async web framework with automatic OpenAPI docs |
| **LangGraph** | Agentic workflow orchestration (StateGraph) |
| **OpenAI API** | GPT-4o Vision for structured data extraction |
| **PyMuPDF (fitz)** | High-quality PDF to image rendering |
| **Pillow + OpenCV** | Image preprocessing (deskew, CLAHE, enhance) |
| **rapidfuzz** | Fuzzy string matching for subject normalization |
| **openpyxl** | Excel file generation with conditional formatting |
| **Pydantic v2** | Data validation and serialization |
| **Redis** | Optional persistent job/record storage |

### Frontend
| Technology | Purpose |
|-----------|---------|
| **Next.js 15** | React framework with App Router |
| **React 19** | UI rendering |
| **TypeScript** | Type safety |
| **Tailwind CSS** | Utility-first styling |
| **shadcn/ui** | Accessible UI component library |
| **react-dropzone** | File upload with drag-and-drop |
| **Lucide React** | Icon library |

---

## License

MIT
