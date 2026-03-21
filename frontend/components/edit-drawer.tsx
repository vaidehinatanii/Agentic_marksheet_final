"use client"

import React, { useEffect, useState } from "react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { formatPercent, getSubjectStatusColor } from "@/lib/utils"
import type { MarksheetRecord, Subject } from "@/lib/types"

interface EditDrawerProps {
  record: MarksheetRecord | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onSave: (recordId: string, updates: Partial<MarksheetRecord>) => Promise<any>
  jobId: string
}

export function EditDrawer({
  record,
  open,
  onOpenChange,
  onSave,
  jobId,
}: EditDrawerProps) {
  const [editingRecord, setEditingRecord] = useState<MarksheetRecord | null>(null)
  const [isSaving, setIsSaving] = useState(false)

  useEffect(() => {
    if (record) {
      setEditingRecord({ ...record })
    }
  }, [record])

  if (!editingRecord) {
    return null
  }

  const updateStudentField = (field: keyof MarksheetRecord, value: string) => {
    setEditingRecord({ ...editingRecord, [field]: value })
  }

  const updateSubject = (index: number, updates: Partial<Subject>) => {
    const newSubjects = [...editingRecord.subjects]
    newSubjects[index] = { ...newSubjects[index], ...updates }
    setEditingRecord({ ...editingRecord, subjects: newSubjects })
  }

  const handleSave = async () => {
    if (!editingRecord) return

    setIsSaving(true)
    try {
      await onSave(editingRecord.id, editingRecord)
      onOpenChange(false)
    } catch (error) {
      console.error("Failed to save record:", error)
    } finally {
      setIsSaving(false)
    }
  }

  // Computed preview (client-side)
  const computeOverallPreview = () => {
    const subjects = editingRecord.subjects
    let totalObtained = 0
    let totalMax = 0

    for (const subj of subjects) {
      if (subj.obtained_marks !== null && subj.max_marks !== null && subj.max_marks > 0) {
        totalObtained += subj.obtained_marks
        totalMax += subj.max_marks
      }
    }

    if (totalMax === 0) return null
    return ((totalObtained / totalMax) * 100).toFixed(2)
  }

  const computeCorePreview = () => {
    const subjects = editingRecord.subjects
    const english = subjects.find((s) => s.category === "ENGLISH")
    const math = subjects.find((s) => s.category === "MATH")
    const science = subjects.find((s) => s.category === "SCIENCE")
    const socialScience = subjects.find((s) => s.category === "SOCIAL_SCIENCE")

    const core = [english, math, science, socialScience].filter(s => s)
    if (core.length < 4) return null

    const percents = core.map(s =>
      s!.obtained_marks && s!.max_marks
        ? (s!.obtained_marks / s!.max_marks) * 100
        : null
    )

    if (percents.some(p => p === null)) return null
    const validPercents = percents.filter((p): p is number => p !== null)
    return (validPercents.reduce((sum, p) => sum + p, 0) / validPercents.length).toFixed(2)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-3xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="truncate">
            Edit Record: {editingRecord.filename}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {/* Student Information */}
          <div className="space-y-4">
            <h3 className="text-lg font-semibold">Student Information</h3>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="student_name">Student Name</Label>
                <Input
                  id="student_name"
                  value={editingRecord.student_name || ""}
                  onChange={(e) =>
                    updateStudentField("student_name", e.target.value)
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="roll_no">Roll No</Label>
                <Input
                  id="roll_no"
                  value={editingRecord.roll_no || ""}
                  onChange={(e) =>
                    updateStudentField("roll_no", e.target.value)
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="exam_session">Exam Session</Label>
                <Input
                  id="exam_session"
                  value={editingRecord.exam_session || ""}
                  onChange={(e) =>
                    updateStudentField("exam_session", e.target.value)
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="school">School</Label>
                <Input
                  id="school"
                  value={editingRecord.school || ""}
                  onChange={(e) =>
                    updateStudentField("school", e.target.value)
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="dob">Date of Birth</Label>
                <Input
                  id="dob"
                  value={editingRecord.dob || ""}
                  onChange={(e) => updateStudentField("dob", e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="seat_no">Seat No</Label>
                <Input
                  id="seat_no"
                  value={editingRecord.seat_no || ""}
                  onChange={(e) =>
                    updateStudentField("seat_no", e.target.value)
                  }
                />
              </div>
            </div>
          </div>

          {/* Subjects */}
          <div className="space-y-4">
            <h3 className="text-lg font-semibold">Subjects</h3>
            <div className="grid gap-4">
              {editingRecord.subjects.map((subject, index) => (
                <div
                  key={index}
                  className="rounded-lg border p-4"
                >
                  <div className="mb-2 flex items-center justify-between">
                    <span className="font-medium">Subject {index + 1}</span>
                    <Badge
                      className={getSubjectStatusColor(subject.status)}
                      variant="outline"
                    >
                      {subject.status}
                    </Badge>
                  </div>
                  <div className="grid grid-cols-4 gap-2">
                    <div className="col-span-1 space-y-1">
                      <Label className="text-xs">Name</Label>
                      <Input
                        value={subject.normalized_name}
                        onChange={(e) =>
                          updateSubject(index, {
                            normalized_name: e.target.value,
                          })
                        }
                      />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">Obtained</Label>
                      <Input
                        type="number"
                        value={subject.obtained_marks ?? ""}
                        onChange={(e) =>
                          updateSubject(index, {
                            obtained_marks: e.target.value
                              ? parseFloat(e.target.value)
                              : null,
                          })
                        }
                      />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">Max</Label>
                      <Input
                        type="number"
                        value={subject.max_marks ?? ""}
                        onChange={(e) =>
                          updateSubject(index, {
                            max_marks: e.target.value
                              ? parseFloat(e.target.value)
                              : null,
                          })
                        }
                      />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">Status</Label>
                      <select
                        className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                        value={subject.status}
                        onChange={(e) =>
                          updateSubject(index, {
                            status: e.target.value as Subject["status"],
                          })
                        }
                      >
                        <option value="OK">OK</option>
                        <option value="AB">AB (Absent)</option>
                        <option value="COMPARTMENT">COMPARTMENT</option>
                        <option value="NON_NUMERIC">NON_NUMERIC</option>
                        <option value="UNKNOWN">UNKNOWN</option>
                      </select>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Computed Preview */}
          <div className="rounded-lg bg-muted p-4">
            <h3 className="mb-2 font-semibold">Computed Values (Preview)</h3>
            <div className="flex gap-6">
              <div>
                <span className="text-sm text-muted-foreground">
                  Best 5 %:{" "}
                </span>
                <span className="font-medium">
                  {computeOverallPreview()
                    ? `${computeOverallPreview()}%`
                    : "N/A"}
                </span>
              </div>
              <div>
                <span className="text-sm text-muted-foreground">
                  Core %:{" "}
                </span>
                <span className="font-medium">
                  {computeCorePreview() ? `${computeCorePreview()}%` : "N/A"}
                </span>
              </div>
            </div>
            <p className="mt-2 text-xs text-muted-foreground">
              Final values will be recomputed on the server after saving.
            </p>
          </div>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isSaving}
          >
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={isSaving} className="min-w-[120px]">
            {isSaving ? "Saving..." : "Save Changes"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
