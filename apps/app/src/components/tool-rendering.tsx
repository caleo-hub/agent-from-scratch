"use client";

import { useEffect, useRef } from "react";

interface ToolReasoningProps {
  name: string;
  args?: object | unknown;
  status: string;
}

export interface AgenticRagResult {
  query?: string;
  context?: string;
  substeps?: string[];
  queries_planned?: string[];
  queries_built?: string[];
  total_retrieved?: number;
  sources?: Array<{
    rank?: number;
    source?: string;
    source_url?: string;
    id?: string;
    score?: number;
    rerank_score?: number;
    subquery?: string;
    snippet?: string;
    metadata?: Record<string, unknown>;
  }>;
}

const statusIndicator = {
  executing: (
    <span className="inline-block h-3 w-3 rounded-full border-2 border-gray-400 border-t-transparent animate-spin" />
  ),
  inProgress: (
    <span className="inline-block h-3 w-3 rounded-full border-2 border-gray-400 border-t-transparent animate-spin" />
  ),
  complete: <span className="text-green-500 text-xs">✓</span>,
};

function formatValue(value: unknown): string {
  if (Array.isArray(value)) return `[${value.length} items]`;
  if (typeof value === "object" && value !== null)
    return `{${Object.keys(value).length} keys}`;
  if (typeof value === "string") return `"${value}"`;
  return String(value);
}

export function ToolReasoning({ name, args, status }: ToolReasoningProps) {
  const entries = args ? Object.entries(args) : [];
  const detailsRef = useRef<HTMLDetailsElement>(null);
  const toolStatus = status as "complete" | "inProgress" | "executing";

  // Auto-open while executing, auto-close when complete
  useEffect(() => {
    if (!detailsRef.current) return;
    detailsRef.current.open = status === "executing";
  }, [status]);

  return (
    <div className="my-2 text-sm">
      {entries.length > 0 ? (
        <details ref={detailsRef} open>
          <summary className="flex items-center gap-2 text-gray-600 dark:text-gray-400 cursor-pointer list-none">
            {statusIndicator[toolStatus]}
            <span className="font-medium">{name}</span>
            <span className="text-[10px]">▼</span>
          </summary>
          <div className="pl-5 mt-1 space-y-1 text-xs text-gray-500 dark:text-zinc-400">
            {entries.map(([key, value]) => (
              <div key={key} className="flex gap-2 min-w-0">
                <span className="font-medium shrink-0">{key}:</span>
                <span className="text-gray-600 dark:text-gray-400 truncate">
                  {formatValue(value)}
                </span>
              </div>
            ))}
          </div>
        </details>
      ) : (
        <div className="flex items-center gap-2 text-gray-600 dark:text-gray-400">
          {statusIndicator[toolStatus]}
          <span className="font-medium">{name}</span>
        </div>
      )}
    </div>
  );
}

const ragSteps = [
  "plan_queries",
  "build_queries",
  "retrieve_fanout",
  "rerank",
  "merge_docs",
];

function titleize(step: string) {
  return step.replaceAll("_", " ");
}

export function AgenticRagToolCard({
  status,
  result,
}: {
  status: string;
  result?: AgenticRagResult;
}) {
  const isComplete = status === "complete";
  const sources = result?.sources || [];

  return (
    <section
      className="my-3 rounded-lg border border-zinc-200 bg-zinc-50 p-3 dark:border-zinc-700 dark:bg-zinc-900"
      aria-live="polite"
      aria-label="Execucao da ferramenta de busca documental"
    >
      <header className="mb-2 flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-zinc-800 dark:text-zinc-100">
          Agentic RAG
        </h3>
        <span
          className={`text-xs ${
            isComplete ? "text-emerald-600" : "text-amber-600"
          }`}
        >
          {isComplete ? "concluido" : "executando"}
        </span>
      </header>

      <ol className="mb-3 space-y-1 text-xs text-zinc-600 dark:text-zinc-300" aria-label="Subetapas">
        {ragSteps.map((step) => (
          <li key={step} className="flex items-center gap-2">
            <span
              className={`inline-block h-2.5 w-2.5 rounded-full ${
                isComplete ? "bg-emerald-500" : "bg-amber-500"
              }`}
              aria-hidden
            />
            <span>{titleize(step)}</span>
          </li>
        ))}
      </ol>

      {result?.query ? (
        <p className="mb-2 text-xs text-zinc-700 dark:text-zinc-200">
          <strong>Pergunta:</strong> {result.query}
        </p>
      ) : null}

      {typeof result?.total_retrieved === "number" ? (
        <p className="mb-2 text-xs text-zinc-700 dark:text-zinc-200">
          <strong>Documentos recuperados:</strong> {result.total_retrieved}
        </p>
      ) : null}

      {sources.length > 0 ? (
        <div>
          <h4 className="mb-1 text-xs font-semibold text-zinc-800 dark:text-zinc-100">
            Sources
          </h4>
          <ul className="space-y-2" aria-label="Fontes utilizadas">
            {sources.map((source, idx) => (
              <li
                key={`${source.id || source.source || "source"}-${idx}`}
                className="rounded-md border border-zinc-200 bg-white p-2 dark:border-zinc-700 dark:bg-zinc-950"
              >
                <details>
                  <summary className="cursor-pointer list-none text-xs font-medium text-zinc-800 dark:text-zinc-100">
                    {source.rank || idx + 1}. {source.source || "Fonte sem nome"}
                  </summary>
                  <div className="mt-2 space-y-1">
                    {source.source_url ? (
                      <a
                        href={source.source_url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-block text-xs text-blue-600 underline dark:text-blue-400"
                      >
                        Abrir fonte
                      </a>
                    ) : null}
                    {typeof source.score === "number" ? (
                      <p className="text-[11px] text-zinc-500 dark:text-zinc-400">
                        score: {source.score.toFixed(4)}
                        {typeof source.rerank_score === "number"
                          ? ` | rerank: ${source.rerank_score.toFixed(4)}`
                          : ""}
                      </p>
                    ) : null}
                    {source.subquery ? (
                      <p className="text-[11px] text-zinc-500 dark:text-zinc-400">
                        subquery: {source.subquery}
                      </p>
                    ) : null}
                    {source.snippet ? (
                      <p className="text-xs text-zinc-700 dark:text-zinc-300">
                        {source.snippet}
                      </p>
                    ) : null}
                  </div>
                </details>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
