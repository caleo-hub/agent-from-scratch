"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import { useAgent } from "@copilotkit/react-core/v2";
import { extractTextFromPdf } from "@/lib/pdf-extract";

export type PendingFile = {
  id: string;
  name: string;
  type: string;
  sizeLabel: string;
  status: "processing" | "ready" | "error";
  syncedToState?: boolean;
  content?: string;
  pageCount?: number;
  charCount?: number;
  errorMessage?: string;
};

type UploadedDocument = {
  id: string;
  name: string;
  content: string;
  page_count: number;
  char_count: number;
  uploaded_at: string;
  mime_type: string;
};

function toUploadedDocument(file: PendingFile): UploadedDocument | null {
  if (!file.content) return null;

  return {
    id: file.id,
    name: file.name,
    content: file.content,
    page_count: file.pageCount ?? 0,
    char_count: file.charCount ?? file.content.length,
    uploaded_at: new Date().toISOString(),
    mime_type: file.type,
  };
}

const ACCEPTED_TYPES = [
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "text/csv",
  "text/plain",
];

const MAX_CONTENT_CHARS = 80_000;

function fmtSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function useFileAttachment() {
  const { agent } = useAgent();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [pendingFiles, setPendingFiles] = useState<PendingFile[]>([]);

  const syncDocumentToState = useCallback(
    (file: PendingFile) => {
      const doc = toUploadedDocument(file);
      if (!doc) return;

      const existing =
        (agent.state?.uploaded_documents as UploadedDocument[] | undefined) ?? [];

      const deduped = existing.filter(
        (d) =>
          d.id !== file.id &&
          !(d.name === file.name && d.char_count === doc.char_count && d.mime_type === file.type),
      );
      const updated = [...deduped, doc];

      agent.setState({
        uploaded_documents: updated,
      });

      console.log("[FileAttachment] 📥 File synced to LangGraph state:", {
        file: file.name,
        docsInState: updated.length,
      });

      setPendingFiles((prev) =>
        prev.map((pf) => (pf.id === file.id ? { ...pf, syncedToState: true } : pf)),
      );
    },
    [agent],
  );

  const parseWithDocling = useCallback(async (file: File) => {
    const formData = new FormData();
    formData.append("file", file);

    const res = await fetch("/api/parse-document", {
      method: "POST",
      body: formData,
    });

    if (!res.ok) {
      throw new Error(`Docling parser failed: ${res.status}`);
    }

    const data = await res.json();
    return {
      text: String(data.text ?? ""),
      pageCount: Number(data.page_count ?? 0),
      charCount: String(data.text ?? "").length,
    };
  }, []);

  // Open file picker dialog
  const openFilePicker = useCallback(() => {
    console.log("[FileAttachment] 🎯 openFilePicker called - opening file dialog");
    fileInputRef.current?.click();
  }, []);

  // Handle file input change
  const onFileInputChange = useCallback(
    async (event: React.ChangeEvent<HTMLInputElement>) => {
      const files = Array.from(event.target.files ?? []);
      console.log("[FileAttachment] 📂 File picker result:", {
        selectedCount: files.length,
        files: files.map((f) => ({ name: f.name, size: f.size, type: f.type })),
      });

      if (files.length === 0) return;

      // Validate file types
      const validFiles = files.filter((f) => {
        const isValid = ACCEPTED_TYPES.some(
          (type) => f.type === type || f.type.startsWith(type.replace("/*", ""))
        );
        if (!isValid) {
          console.warn(`[FileAttachment] ⚠️ Unsupported file type: ${f.type} for ${f.name}`);
        }
        return isValid;
      });

      if (validFiles.length === 0) {
        console.error("[FileAttachment] ❌ No valid files selected");
        return;
      }

      // Create pending file entries
      const newPendingFiles: PendingFile[] = validFiles.map((f) => ({
        id: crypto.randomUUID(),
        name: f.name,
        type: f.type,
        sizeLabel: fmtSize(f.size),
        status: "processing",
      }));

      setPendingFiles((prev) => [...prev, ...newPendingFiles]);

      // Extract content from each file
      console.log("[FileAttachment] 🔄 Starting extraction for:", validFiles.map((f) => f.name));

      for (const file of validFiles) {
        const pendingFile = newPendingFiles.find((pf) => pf.name === file.name);
        if (!pendingFile) continue;

        console.log("[FileAttachment] 🔧 Extracting content from:", file.name);

        try {
          if (file.type === "application/pdf") {
            // Fast path: pdfjs; fallback to Docling for low-density/complex PDF.
            let parsed = await extractTextFromPdf(file);

            if ((parsed.charCount || 0) / Math.max(parsed.pageCount || 1, 1) < 200) {
              try {
                parsed = await parseWithDocling(file);
              } catch (doclingError) {
                console.warn("[FileAttachment] ⚠️ Docling fallback failed, keeping pdfjs output", doclingError);
              }
            }

            const { text, pageCount, charCount } = parsed;
            console.log("[FileAttachment] ✅ Extracted from:", file.name, {
              contentLength: charCount,
              pageCount,
            });

            setPendingFiles((prev) =>
              prev.map((pf) =>
                pf.id === pendingFile.id
                  ? {
                      ...pf,
                      content: text.substring(0, MAX_CONTENT_CHARS),
                      charCount,
                      pageCount,
                      status: "ready",
                      syncedToState: false,
                    }
                  : pf
              )
            );

            syncDocumentToState({
              ...pendingFile,
              content: text.substring(0, MAX_CONTENT_CHARS),
              charCount,
              pageCount,
              status: "ready",
              syncedToState: false,
            });
          } else if (
            file.type ===
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          ) {
            const { text, pageCount, charCount } = await parseWithDocling(file);

            setPendingFiles((prev) =>
              prev.map((pf) =>
                pf.id === pendingFile.id
                  ? {
                      ...pf,
                      content: text.substring(0, MAX_CONTENT_CHARS),
                      charCount,
                      pageCount,
                      status: "ready",
                      syncedToState: false,
                    }
                  : pf
              )
            );

            syncDocumentToState({
              ...pendingFile,
              content: text.substring(0, MAX_CONTENT_CHARS),
              charCount,
              pageCount,
              status: "ready",
              syncedToState: false,
            });
          } else if (file.type === "text/csv" || file.type === "text/plain") {
            // Read text file
            const text = await file.text();
            console.log("[FileAttachment] ✅ Read text file:", file.name, {
              contentLength: text.length,
            });
            setPendingFiles((prev) =>
              prev.map((pf) =>
                pf.id === pendingFile.id
                  ? {
                      ...pf,
                      content: text.substring(0, MAX_CONTENT_CHARS),
                      charCount: text.length,
                      status: "ready",
                      syncedToState: false,
                    }
                  : pf
              )
            );

            syncDocumentToState({
              ...pendingFile,
              content: text.substring(0, MAX_CONTENT_CHARS),
              charCount: text.length,
              status: "ready",
              syncedToState: false,
            });
          }
        } catch (error) {
          console.error("[FileAttachment] ❌ Error extracting from:", file.name, error);
          setPendingFiles((prev) =>
            prev.map((pf) =>
              pf.id === pendingFile.id
                ? {
                    ...pf,
                    status: "error",
                    errorMessage: String(error),
                  }
                : pf
            )
          );
        }
      }

      // Reset file input
      event.target.value = "";
    },
    [parseWithDocling, syncDocumentToState]
  );

  // Submit user message while uploaded docs are already available in state.
  const submitWithFiles = useCallback(
    (message: string) => {
      const syncedFiles = pendingFiles.filter((f) => f.status === "ready" && f.syncedToState);

      console.log("[FileAttachment] 📊 submitWithFiles called:", {
        messageText: message,
        syncedFilesCount: syncedFiles.length,
        syncedFileNames: syncedFiles.map((f) => f.name),
      });

      // If no message and no files, don't send
      if (!message?.trim() && syncedFiles.length === 0) {
        console.warn("[FileAttachment] ⚠️ Empty message and no files, skipping send");
        return;
      }

      const normalizedMessage =
        message?.trim() ||
        (syncedFiles.length > 0
          ? "Analise os arquivos que anexei na conversa."
          : "");

      // Re-sync state right before run to avoid race conditions between setState and runAgent.
      if (syncedFiles.length > 0) {
        const existing =
          (agent.state?.uploaded_documents as UploadedDocument[] | undefined) ?? [];

        const fromPending = syncedFiles
          .map((f) => toUploadedDocument(f))
          .filter((d): d is UploadedDocument => Boolean(d));

        const mergedMap = new Map<string, UploadedDocument>();
        for (const doc of existing) {
          mergedMap.set(doc.id, doc);
        }
        for (const doc of fromPending) {
          mergedMap.set(doc.id, doc);
        }

        const merged = Array.from(mergedMap.values());
        agent.setState({ uploaded_documents: merged });

        // Hidden steering message to make the model consistently query state docs.
        agent.addMessage({
          role: "developer",
          id: crypto.randomUUID(),
          content:
            "Antes de responder sobre anexos, chame get_uploaded_documents e use o conteúdo retornado.",
        });

        console.log("[FileAttachment] 🔒 Re-synced uploaded_documents before run:", {
          existingCount: existing.length,
          pendingCount: fromPending.length,
          mergedCount: merged.length,
        });
      }

      console.log("[FileAttachment] 📤 Sending user message to agent:", {
        messageLength: normalizedMessage.length,
        syncedFilesCount: syncedFiles.length,
      });

      // Send only user text. Uploaded files already live in LangGraph state.
      agent.addMessage({
        role: "user",
        id: crypto.randomUUID(),
        content: normalizedMessage,
      });

      console.log("[FileAttachment] ✅ Message queued, running agent...");
      agent.runAgent();
      setPendingFiles([]);
    },
    [agent, pendingFiles]
  );

  // Render pending files as chips in the input area
  const PendingFilesSlot = useMemo(
    () =>
      ({ children }: { children?: React.ReactNode }) => {
        if (pendingFiles.length === 0) return children;

        const hasProcessingFiles = pendingFiles.some((f) => f.status === "processing");

        return (
          <div className="flex flex-col gap-2">
            <div className="flex flex-wrap gap-1.5">
              {pendingFiles.map((file) => (
                <div
                  key={file.id}
                  className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs ${
                    file.status === "processing"
                      ? "border-blue-200 bg-blue-50 dark:border-blue-700 dark:bg-blue-900"
                      : file.status === "ready"
                        ? "border-green-200 bg-green-50 dark:border-green-700 dark:bg-green-900"
                        : "border-red-200 bg-red-50 dark:border-red-700 dark:bg-red-900"
                  }`}
                >
                  <span className="text-base">
                    {file.status === "processing" && "⏳"}
                    {file.status === "ready" && (file.syncedToState ? "✅" : "↗")}
                    {file.status === "error" && "❌"}
                  </span>
                  <span className="font-medium">{file.name}</span>
                  <span className="text-xs opacity-60">({file.sizeLabel})</span>
                </div>
              ))}
            </div>
            <div className="flex items-center gap-2">
              {hasProcessingFiles && (
                <span className="text-xs text-zinc-500">Aguardando processamento dos arquivos...</span>
              )}
              {!hasProcessingFiles && (
                <span className="text-xs text-zinc-500">Arquivos anexados à conversa. Digite sua mensagem e envie.</span>
              )}
            </div>
            {children}
          </div>
        );
      },
    [pendingFiles]
  );

  return {
    fileInputRef,
    openFilePicker,
    onFileInputChange,
    PendingFilesSlot,
    submitWithFiles,
  };
}
