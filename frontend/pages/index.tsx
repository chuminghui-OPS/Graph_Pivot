import React, { useEffect, useMemo, useRef, useState } from "react";
import { ChapterList } from "../components/ChapterList";
import { GraphView } from "../components/GraphView";
import { ReaderPanel } from "../components/ReaderPanel";
import {
  API_BASE,
  Chapter,
  fetchChapterGraph,
  fetchChapterMarkdown,
  fetchChapters,
  heartbeatBook,
  processBook,
  uploadBook,
  bookPdfUrl,
  KnowledgeGraph
} from "../lib/api";

const PROGRESS_STEPS = [
  { start: 0, end: 20, duration: 5_000 },
  { start: 20, end: 40, duration: 10_000 },
  { start: 40, end: 60, duration: 20_000 },
  { start: 60, end: 80, duration: 45_000 },
  { start: 80, end: 100, duration: 200_000 }
];
const TOTAL_PROGRESS_MS = PROGRESS_STEPS.reduce(
  (total, step) => total + step.duration,
  0
);
const TERMINAL_STATUSES = new Set([
  "DONE",
  "FAILED",
  "SKIPPED_TOO_LARGE",
  "TIMEOUT",
  "PAUSED"
]);

const progressFromElapsed = (elapsedMs: number) => {
  let remaining = Math.max(0, elapsedMs);
  let progress = 0;
  for (const step of PROGRESS_STEPS) {
    if (remaining <= 0) {
      break;
    }
    const span = step.duration;
    const slice = Math.min(remaining, span);
    const ratio = slice / span;
    progress = step.start + (step.end - step.start) * ratio;
    remaining -= span;
  }
  return Math.min(100, Math.max(progress, 0));
};

export default function Home() {
  const [bookId, setBookId] = useState<string | null>(null);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [activeChapterId, setActiveChapterId] = useState<string | null>(null);
  const [graph, setGraph] = useState<KnowledgeGraph | null>(null);
  const [markdown, setMarkdown] = useState<string>("");
  const [highlightTerm, setHighlightTerm] = useState<string | null>(null);
  const [evidence, setEvidence] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [llmInfo, setLlmInfo] = useState<{ provider: string; model: string } | null>(null);
  const [selectedLlm, setSelectedLlm] = useState<"qwen" | "gemini">("qwen");
  const [manualBookId, setManualBookId] = useState("");
  const [progressPercent, setProgressPercent] = useState(0);
  const [progressSpeedMs, setProgressSpeedMs] = useState(300);
  const progressMetaRef = useRef<{ chapterId: string; startedAt: number } | null>(null);
  const progressTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const fastForwardTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const pdfUrl = useMemo(
    () => (bookId ? bookPdfUrl(bookId) : null),
    [bookId]
  );

  const totalChapters = chapters.length;
  const doneCount = chapters.filter((chapter) => chapter.status === "DONE").length;
  const processingIndex = chapters.findIndex(
    (chapter) => chapter.status === "PROCESSING"
  );
  const processingChapter =
    processingIndex >= 0 ? chapters[processingIndex] : null;
  const allTerminal =
    totalChapters > 0 &&
    chapters.every((chapter) => TERMINAL_STATUSES.has(chapter.status));
  const hasFailures = chapters.some((chapter) =>
    ["FAILED", "SKIPPED_TOO_LARGE", "TIMEOUT"].includes(chapter.status)
  );

  let progressLabel = "";
  if (bookId && totalChapters === 0) {
    progressLabel = "正在生成 MD...";
  } else if (processingChapter) {
    progressLabel = `正在处理第${processingIndex + 1}章：${processingChapter.title}`;
  } else if (allTerminal) {
    progressLabel = hasFailures ? "处理完成（部分章节异常）" : "全部完成";
  } else if (totalChapters > 0) {
    progressLabel = "等待处理中...";
  }

  useEffect(() => {
    if (!bookId) {
      return;
    }
    let timer: NodeJS.Timeout | null = null;
    const poll = async () => {
      try {
        const data = await fetchChapters(bookId);
        setChapters(data.chapters);
        setLlmInfo({ provider: data.llm_provider, model: data.llm_model });
        if (!activeChapterId && data.chapters.length > 0) {
          setActiveChapterId(data.chapters[0].chapter_id);
        }
        const hasPending =
          data.chapters.length === 0 ||
          data.chapters.some(
            (chapter) =>
              chapter.status === "PENDING" || chapter.status === "PROCESSING"
          );
        if (hasPending) {
          timer = setTimeout(poll, 2000);
        }
      } catch (err: any) {
        setError(err.message || "Failed to load chapters");
      }
    };
    poll();
    return () => {
      if (timer) clearTimeout(timer);
    };
  }, [bookId, activeChapterId]);

  useEffect(() => {
    if (!bookId) {
      return;
    }
    let heartbeatTimer: NodeJS.Timeout | null = null;
    const beat = async () => {
      try {
        await heartbeatBook(bookId);
      } catch {
        // ignore heartbeat errors to avoid noisy UI
      }
      heartbeatTimer = setTimeout(beat, 10000);
    };
    beat();
    return () => {
      if (heartbeatTimer) {
        clearTimeout(heartbeatTimer);
      }
    };
  }, [bookId]);
  useEffect(() => {
    if (!bookId) {
      if (progressTimerRef.current) {
        clearTimeout(progressTimerRef.current);
        progressTimerRef.current = null;
      }
      if (fastForwardTimerRef.current) {
        clearTimeout(fastForwardTimerRef.current);
        fastForwardTimerRef.current = null;
      }
      progressMetaRef.current = null;
      setProgressPercent(0);
      return;
    }

    if (processingChapter) {
      if (fastForwardTimerRef.current) {
        clearTimeout(fastForwardTimerRef.current);
        fastForwardTimerRef.current = null;
      }
      if (
        !progressMetaRef.current ||
        progressMetaRef.current.chapterId !== processingChapter.chapter_id
      ) {
        progressMetaRef.current = {
          chapterId: processingChapter.chapter_id,
          startedAt: Date.now()
        };
        setProgressPercent(0);
      }
      setProgressSpeedMs(300);
      if (progressTimerRef.current) {
        clearTimeout(progressTimerRef.current);
      }
      const tick = () => {
        if (!progressMetaRef.current) {
          return;
        }
        const elapsed = Date.now() - progressMetaRef.current.startedAt;
        setProgressPercent(progressFromElapsed(elapsed));
        if (elapsed < TOTAL_PROGRESS_MS) {
          progressTimerRef.current = setTimeout(tick, 300);
        }
      };
      tick();
      return () => {
        if (progressTimerRef.current) {
          clearTimeout(progressTimerRef.current);
          progressTimerRef.current = null;
        }
      };
    }

    if (progressTimerRef.current) {
      clearTimeout(progressTimerRef.current);
      progressTimerRef.current = null;
    }

    if (progressMetaRef.current) {
      const finished = chapters.find(
        (chapter) => chapter.chapter_id === progressMetaRef.current?.chapterId
      );
      if (finished && finished.status !== "PENDING" && finished.status !== "PROCESSING") {
        const finishedId = progressMetaRef.current?.chapterId;
        setProgressSpeedMs(1000);
        setProgressPercent(100);
        if (fastForwardTimerRef.current) {
          clearTimeout(fastForwardTimerRef.current);
        }
        fastForwardTimerRef.current = setTimeout(() => {
          setProgressSpeedMs(300);
          if (progressMetaRef.current?.chapterId === finishedId) {
            progressMetaRef.current = null;
          }
        }, 1000);
        return;
      }
      progressMetaRef.current = null;
    }

    if (totalChapters === 0) {
      setProgressPercent(5);
    } else if (allTerminal) {
      setProgressPercent(100);
    } else {
      setProgressPercent(0);
    }
  }, [bookId, processingChapter?.chapter_id, chapters, totalChapters, allTerminal]);

  useEffect(() => {
    if (!bookId || !activeChapterId) {
      return;
    }
    const loadChapterData = async () => {
      try {
        const [md, kg] = await Promise.all([
          fetchChapterMarkdown(bookId, activeChapterId),
          fetchChapterGraph(bookId, activeChapterId)
        ]);
        setMarkdown(md.markdown);
        setGraph(kg);
      } catch (err: any) {
        setError(err.message || "Failed to load chapter");
      }
    };
    loadChapterData();
  }, [bookId, activeChapterId]);

  const handleUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const uploadResult = await uploadBook(file);
      setBookId(uploadResult.book_id);
      setChapters([]);
      setActiveChapterId(null);
      setGraph(null);
      setMarkdown("");
      await processBook(uploadResult.book_id, selectedLlm);
    } catch (err: any) {
      setError(err.message || "Upload failed");
    } finally {
      setUploading(false);
      event.target.value = "";
    }
  };

  const handleLoadBook = async () => {
    const trimmed = manualBookId.trim();
    if (!trimmed) {
      setError("请输入 book_id");
      return;
    }
    setError(null);
    setBookId(trimmed);
    setChapters([]);
    setActiveChapterId(null);
    setGraph(null);
    setMarkdown("");
  };

  return (
    <div className="page">
      <header className="hero">
        <div>
          <div className="title">Graph Pivot</div>
          <div className="subtitle">
            Upload a PDF, extract chapter knowledge graphs, and explore evidence.
          </div>
          <div className="llm-row">
            <span className="llm-label">LLM:</span>
            <div className="llm-toggle">
              <button
                className={selectedLlm === "qwen" ? "active" : ""}
                onClick={() => setSelectedLlm("qwen")}
              >
                通义千问
              </button>
              <button
                className={selectedLlm === "gemini" ? "active" : ""}
                onClick={() => setSelectedLlm("gemini")}
              >
                Gemini
              </button>
            </div>
            {llmInfo ? (
              <span className="llm-meta">
                当前：{llmInfo.provider} ({llmInfo.model})
              </span>
            ) : null}
          </div>
        </div>
        <div className="upload-card">
          <div className="upload-title">Upload PDF</div>
          <input
            type="file"
            accept="application/pdf"
            onChange={handleUpload}
            disabled={uploading}
          />
          <div className="upload-title" style={{ marginTop: 12 }}>
            Load Existing Book
          </div>
          <input
            type="text"
            placeholder="输入已有 book_id"
            value={manualBookId}
            onChange={(event) => setManualBookId(event.target.value)}
          />
          <button className="load-btn" onClick={handleLoadBook}>
            加载
          </button>
          <div className="hint">
            Backend: {API_BASE}
          </div>
        </div>
      </header>
      {error ? <div className="error-banner">{error}</div> : null}
      {bookId ? (
        <div className="progress-card">
          <div className="progress-label">
            {progressLabel} {bookId ? `（${bookId}）` : ""}
          </div>
          <div className="progress-track">
            <div
              className="progress-fill"
              style={{
                width: `${progressPercent}%`,
                transitionDuration: `${progressSpeedMs}ms`
              }}
            />
          </div>
          <div className="progress-meta">
            {doneCount}/{totalChapters || 0}
          </div>
        </div>
      ) : null}
      <main className="layout">
        <ChapterList
          chapters={chapters}
          activeId={activeChapterId}
          onSelect={(id) => {
            setActiveChapterId(id);
            setHighlightTerm(null);
            setEvidence(null);
          }}
        />
        <GraphView
          graph={graph}
          onSelectNode={(name) => {
            setHighlightTerm(name);
            setEvidence(null);
          }}
          onSelectEdge={(evidenceText) => {
            setEvidence(evidenceText);
            setHighlightTerm(evidenceText);
          }}
        />
        <ReaderPanel
          pdfUrl={pdfUrl}
          markdown={markdown}
          highlightTerm={highlightTerm}
          evidence={evidence}
        />
      </main>
    </div>
  );
}
