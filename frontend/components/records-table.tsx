"use client"

import React, { useState } from "react"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Edit, AlertTriangle, ChevronDown, ChevronRight } from "lucide-react"
import { formatPercent, getRecordStatusColor, getSubjectStatusColor } from "@/lib/utils"
import type { MarksheetRecord } from "@/lib/types"

interface RecordsTableProps {
  records: MarksheetRecord[]
  onEdit: (record: MarksheetRecord) => void
  onRerun?: (recordId: string) => void
}

export function RecordsTable({ records, onEdit, onRerun }: RecordsTableProps) {
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set())

  const toggleRow = (id: string) => {
    const newExpanded = new Set(expandedRows)
    if (newExpanded.has(id)) {
      newExpanded.delete(id)
    } else {
      newExpanded.add(id)
    }
    setExpandedRows(newExpanded)
  }

  if (records.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-lg border border-dashed p-12 text-center">
        <p className="text-lg font-medium text-muted-foreground">
          No records yet
        </p>
        <p className="mt-1 text-sm text-muted-foreground">
          Upload marksheets above to start extracting data
        </p>
      </div>
    )
  }

  return (
    <div className="rounded-lg border">
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[40px]"></TableHead>
              <TableHead className="w-[180px]">Filename</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Student Name</TableHead>
              <TableHead>Roll No</TableHead>
              <TableHead>Best 5 %</TableHead>
              <TableHead>Core %</TableHead>
              <TableHead>Review</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {records.map((record) => {
              const isExpanded = expandedRows.has(record.id)
              return (
                <React.Fragment key={record.id}>
                  {/* Main row */}
                  <TableRow className="cursor-pointer hover:bg-muted/50" onClick={() => toggleRow(record.id)}>
                    <TableCell>
                      <Button variant="ghost" size="sm" className="h-6 w-6 p-0">
                        {isExpanded ? (
                          <ChevronDown className="h-4 w-4" />
                        ) : (
                          <ChevronRight className="h-4 w-4" />
                        )}
                      </Button>
                    </TableCell>
                    <TableCell className="font-medium">{record.filename}</TableCell>
                    <TableCell>
                      <Badge className={getRecordStatusColor(record.status)}>
                        {record.status}
                      </Badge>
                    </TableCell>
                    <TableCell>{record.student_name || "—"}</TableCell>
                    <TableCell>{record.roll_no || "—"}</TableCell>
                    <TableCell>
                      <span
                        className={
                          record.overall_percent === null
                            ? "text-yellow-600"
                            : ""
                        }
                      >
                        {formatPercent(record.overall_percent)}
                      </span>
                    </TableCell>
                    <TableCell>
                      <span
                        className={
                          record.pcm_percent === null ? "text-yellow-600" : ""
                        }
                      >
                        {formatPercent(record.pcm_percent)}
                      </span>
                    </TableCell>
                    <TableCell>
                      {record.needs_review ? (
                        <div className="flex items-center gap-1 text-orange-600">
                          <AlertTriangle className="h-4 w-4" />
                          <span className="text-xs">Yes</span>
                        </div>
                      ) : (
                        <span className="text-green-600">No</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation()
                          onEdit(record)
                        }}
                      >
                        <Edit className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>

                  {/* Expanded subject details row */}
                  {isExpanded && (
                    <TableRow>
                      <TableCell colSpan={9} className="bg-muted/30 p-4">
                        <div className="space-y-3">
                          <h4 className="text-sm font-semibold text-muted-foreground">
                            Subject Details
                          </h4>
                          <div className="grid gap-2">
                            {record.subjects.map((subject, idx) => (
                              <div
                                key={idx}
                                className="flex items-center gap-4 rounded border bg-background p-3 text-sm"
                              >
                                <span className="w-20 font-medium">
                                  Subj {idx + 1}
                                </span>
                                <span className="w-32 font-medium">
                                  {subject.normalized_name}
                                </span>
                                <span className="w-24 text-center">
                                  {subject.obtained_marks ?? "—"}/{subject.max_marks ?? "—"}
                                </span>
                                <Badge
                                  className={getSubjectStatusColor(subject.status)}
                                  variant="outline"
                                >
                                  {subject.status}
                                </Badge>
                                {subject.category !== "OTHER" && (
                                  <span className="ml-auto text-xs text-muted-foreground">
                                    {subject.category}
                                  </span>
                                )}
                              </div>
                            ))}
                          </div>
                          {record.review_reasons && record.review_reasons.length > 0 && (
                            <div className="mt-2 rounded bg-orange-50 p-2 text-xs text-orange-700">
                              <span className="font-semibold">Review Reasons:</span>{" "}
                              {record.review_reasons.join(", ")}
                            </div>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  )}
                </React.Fragment>
              )
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
