"use client";

import { useState, useRef, DragEvent } from "react";
import { Upload, FileText, CheckCircle, AlertCircle, Loader2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { uploadDocument } from "@/lib/api";
import type { UploadResponse } from "@/lib/types";

interface UploadModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: () => void;
}

type State = "idle" | "uploading" | "success" | "error";

export function UploadModal({ open, onOpenChange, onSuccess }: UploadModalProps) {
  const [state, setState] = useState<State>("idle");
  const [dragOver, setDragOver] = useState(false);
  const [result, setResult] = useState<UploadResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  function reset() {
    setState("idle");
    setResult(null);
    setErrorMsg("");
  }

  async function handleFile(file: File) {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setErrorMsg("Only PDF files are accepted.");
      setState("error");
      return;
    }
    setState("uploading");
    try {
      const data = await uploadDocument(file);
      setResult(data);
      setState("success");
      onSuccess();
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Upload failed");
      setState("error");
    }
  }

  function onInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  }

  function onDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  }

  const confidenceColor =
    result && result.extracted_info.confidence >= 0.8
      ? "success"
      : result && result.extracted_info.confidence >= 0.5
        ? "warning"
        : "destructive";

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        if (!v) reset();
        onOpenChange(v);
      }}
    >
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Upload Patient Document</DialogTitle>
          <DialogDescription>
            Upload a PDF — we&apos;ll automatically extract the patient&apos;s name and date of birth.
          </DialogDescription>
        </DialogHeader>

        {state === "idle" && (
          <div
            className={`mt-2 flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-10 transition-colors cursor-pointer ${
              dragOver ? "border-blue-500 bg-blue-50" : "border-gray-300 hover:border-blue-400 hover:bg-gray-50"
            }`}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={onDrop}
            onClick={() => inputRef.current?.click()}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === "Enter" && inputRef.current?.click()}
          >
            <Upload className="h-10 w-10 text-gray-400" />
            <p className="mt-3 text-sm font-medium text-gray-700">
              Drop PDF here or{" "}
              <span className="text-blue-600 underline">browse files</span>
            </p>
            <p className="mt-1 text-xs text-gray-400">Max 10 MB</p>
            <input
              ref={inputRef}
              type="file"
              accept=".pdf,application/pdf"
              className="hidden"
              onChange={onInputChange}
            />
          </div>
        )}

        {state === "uploading" && (
          <div className="flex flex-col items-center gap-4 py-8">
            <Loader2 className="h-10 w-10 animate-spin text-blue-600" />
            <p className="text-sm text-gray-600">Extracting patient information…</p>
          </div>
        )}

        {state === "success" && result && (
          <div className="space-y-4">
            <div className="flex items-center gap-2 rounded-lg bg-green-50 p-3">
              <CheckCircle className="h-5 w-5 text-green-600 shrink-0" />
              <p className="text-sm font-medium text-green-800">{result.message}</p>
            </div>

            <div className="rounded-lg border border-gray-200 divide-y divide-gray-100">
              <div className="grid grid-cols-2 px-4 py-3">
                <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">Field</span>
                <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">Extracted Value</span>
              </div>
              <div className="grid grid-cols-2 px-4 py-2.5">
                <span className="text-sm text-gray-600">First Name</span>
                <span className="text-sm font-medium">{result.extracted_info.first_name || "—"}</span>
              </div>
              <div className="grid grid-cols-2 px-4 py-2.5">
                <span className="text-sm text-gray-600">Last Name</span>
                <span className="text-sm font-medium">{result.extracted_info.last_name || "—"}</span>
              </div>
              <div className="grid grid-cols-2 px-4 py-2.5">
                <span className="text-sm text-gray-600">Date of Birth</span>
                <span className="text-sm font-medium">{result.extracted_info.date_of_birth || "—"}</span>
              </div>
              <div className="grid grid-cols-2 items-center px-4 py-2.5">
                <span className="text-sm text-gray-600">Confidence</span>
                <Badge variant={confidenceColor}>
                  {Math.round(result.extracted_info.confidence * 100)}%
                </Badge>
              </div>
            </div>

            <div className="flex items-center gap-2 rounded-lg bg-gray-50 px-4 py-3">
              <FileText className="h-4 w-4 text-gray-400 shrink-0" />
              <span className="text-sm text-gray-600">
                Order <span className="font-mono font-medium text-gray-800">{result.order.id.slice(0, 8)}…</span> created
              </span>
            </div>

            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={reset}>Upload Another</Button>
              <Button onClick={() => { reset(); onOpenChange(false); }}>Done</Button>
            </div>
          </div>
        )}

        {state === "error" && (
          <div className="space-y-4">
            <div className="flex items-start gap-2 rounded-lg bg-red-50 p-3">
              <AlertCircle className="h-5 w-5 text-red-600 shrink-0 mt-0.5" />
              <p className="text-sm text-red-700">{errorMsg}</p>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => onOpenChange(false)}>Close</Button>
              <Button onClick={reset}>Try Again</Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
