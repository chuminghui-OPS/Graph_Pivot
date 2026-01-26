import React, { useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeRaw from "rehype-raw";

interface ReaderPanelProps {
  pdfUrl: string | null;
  markdown: string;
  highlightTerm: string | null;
  evidence: string | null;
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export function ReaderPanel({
  pdfUrl,
  markdown,
  highlightTerm,
  evidence
}: ReaderPanelProps) {
  const [mode, setMode] = useState<"pdf" | "md">("pdf");

  const highlightedMarkdown = useMemo(() => {
    if (!highlightTerm) {
      return markdown;
    }
    const pattern = new RegExp(escapeRegExp(highlightTerm), "gi");
    return markdown.replace(pattern, (match) => `<mark>${match}</mark>`);
  }, [markdown, highlightTerm]);

  return (
    <div className="panel">
      <div className="panel-title">
        Reader
        <div className="mode-toggle">
          <button
            className={mode === "pdf" ? "active" : ""}
            onClick={() => setMode("pdf")}
          >
            PDF
          </button>
          <button
            className={mode === "md" ? "active" : ""}
            onClick={() => setMode("md")}
          >
            Markdown
          </button>
        </div>
      </div>
      {evidence ? (
        <div className="evidence-box">
          Evidence: <mark>{evidence}</mark>
        </div>
      ) : (
        <div className="evidence-box muted">Click a node or edge to highlight.</div>
      )}
      <div className="reader-body">
        {mode === "pdf" ? (
          pdfUrl ? (
            <iframe className="pdf-frame" src={pdfUrl} title="PDF viewer" />
          ) : (
            <div className="empty-state">Upload a PDF to start.</div>
          )
        ) : (
          <div className="markdown-body">
            <ReactMarkdown rehypePlugins={[rehypeRaw]}>
              {highlightedMarkdown}
            </ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}
