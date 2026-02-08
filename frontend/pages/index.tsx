import Link from "next/link";
import React, { useEffect, useRef, useState } from "react";
import { useRouter } from "next/router";
import { ChapterList } from "../components/ChapterList";
import { GraphView } from "../components/GraphView";
import { ReaderPanel } from "../components/ReaderPanel";
import {
  API_BASE,
  ApiAsset,
  Chapter,
  fetchChapterGraph,
  fetchChapterMarkdown,
  fetchChapters,
  fetchAssets,
  fetchBookTypes,
  heartbeatBook,
  processBook,
  uploadBook,
  fetchBookPdfUrl,
  KnowledgeGraph,
  BookType
} from "../lib/api";
import { getSupabaseClient, hasSupabaseConfig } from "../lib/supabase";

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
const HEARTBEAT_INTERVAL_MS = 60_000;
const HEARTBEAT_IDLE_TIMEOUT_MS = 5 * 60_000;
const POLL_INTERVAL_PROCESSING_MS = 10_000;
const POLL_INTERVAL_PENDING_MS = 20_000;

const FALLBACK_BOOK_TYPES: BookType[] = [
  { key: "textbook", code: "B", label: "专业教材/大学教科书" },
  { key: "handbook", code: "C", label: "专业工具书/行业手册" },
  { key: "humanities", code: "D", label: "人文社科研究著作" },
  { key: "exam", code: "E", label: "职业考试备考" },
  { key: "popular_science", code: "F", label: "科普类书籍" },
  { key: "business", code: "G", label: "商业/管理/职场" },
  { key: "history_geo", code: "H", label: "历史/地理叙述类" },
  { key: "literature", code: "I", label: "纯文学" },
  { key: "lifestyle", code: "J", label: "生活/休闲" },
  { key: "general", code: "K", label: "通用规则" }
];

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
  const router = useRouter();
  const [bookId, setBookId] = useState<string | null>(null);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [activeChapterId, setActiveChapterId] = useState<string | null>(null);
  const [graph, setGraph] = useState<KnowledgeGraph | null>(null);
  const [markdown, setMarkdown] = useState<string>("");
  const [highlightTerm, setHighlightTerm] = useState<string | null>(null);
  const [evidence, setEvidence] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [usageSummary, setUsageSummary] = useState<{
    calls: number;
    tokensIn: number;
    tokensOut: number;
  } | null>(null);
  const [llmInfo, setLlmInfo] = useState<{ provider: string; model: string } | null>(null);
  const [manualBookId, setManualBookId] = useState("");
  const [progressPercent, setProgressPercent] = useState(0);
  const [progressSpeedMs, setProgressSpeedMs] = useState(300);
  const progressMetaRef = useRef<{ chapterId: string; startedAt: number } | null>(null);
  const progressTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const fastForwardTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const hasConfig = hasSupabaseConfig();
  const [assets, setAssets] = useState<ApiAsset[]>([]);
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null);
  const [selectedAssetModel, setSelectedAssetModel] = useState<string>("");
  const [bookType, setBookType] = useState<string>("textbook");
  const [bookTypes, setBookTypes] = useState<BookType[]>(FALLBACK_BOOK_TYPES);
  const lastActivityRef = useRef<number>(Date.now());
  const heartbeatTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  useEffect(() => {
    let mounted = true;
    const supabase = getSupabaseClient();
    if (!supabase) {
      setAuthReady(true);
      return;
    }
    supabase.auth
      .getSession()
      .then(({ data }) => {
        if (!mounted) return;
        setAuthReady(true);
        if (!data.session) {
          router.replace("/login");
        }
      })
      .catch(() => {
        if (mounted) {
          setAuthReady(true);
        }
      });
    const { data } = supabase.auth.onAuthStateChange((_event, session) => {
      if (!session) {
        router.replace("/login");
      }
    });
    return () => {
      mounted = false;
      data.subscription.unsubscribe();
    };
  }, [router]);

  useEffect(() => {
    const markActive = () => {
      lastActivityRef.current = Date.now();
    };
    const onVisibility = () => {
      if (document.visibilityState === "visible") {
        lastActivityRef.current = Date.now();
      }
    };
    window.addEventListener("mousemove", markActive, { passive: true });
    window.addEventListener("keydown", markActive);
    window.addEventListener("scroll", markActive, { passive: true });
    window.addEventListener("click", markActive);
    window.addEventListener("touchstart", markActive, { passive: true });
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      window.removeEventListener("mousemove", markActive);
      window.removeEventListener("keydown", markActive);
      window.removeEventListener("scroll", markActive);
      window.removeEventListener("click", markActive);
      window.removeEventListener("touchstart", markActive);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const hydrateSidebar = () => {
      setSidebarOpen(window.innerWidth >= 1024);
    };
    hydrateSidebar();
    const onResize = () => {
      if (window.innerWidth >= 1024) {
        setSidebarOpen(true);
      }
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  useEffect(() => {
    const loadBookTypes = async () => {
      try {
        const types = await fetchBookTypes();
        if (types.length > 0) {
          setBookTypes(types);
          if (!types.find((item) => item.key === bookType)) {
            setBookType(types[0].key);
          }
        }
      } catch {
        // ignore; use fallback
      }
    };
    loadBookTypes();
  }, [bookType]);

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
  const shouldSpin = Boolean(bookId) && (totalChapters === 0 || !!processingChapter);
  const selectedAsset = assets.find((item) => item.id === selectedAssetId) || null;
  const assetModels = selectedAsset?.models || [];

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
      if (pdfUrl) {
        URL.revokeObjectURL(pdfUrl);
      }
      setPdfUrl(null);
      setRunError(null);
      setUsageSummary(null);
      return;
    }
    let cancelled = false;
    const loadPdf = async () => {
      try {
        const url = await fetchBookPdfUrl(bookId);
        if (cancelled) {
          URL.revokeObjectURL(url);
          return;
        }
        setPdfUrl((prev) => {
          if (prev) URL.revokeObjectURL(prev);
          return url;
        });
      } catch {
        // ignore PDF errors to avoid blocking UI
      }
    };
    loadPdf();
    return () => {
      cancelled = true;
    };
  }, [bookId]);

  useEffect(() => {
    if (!bookId) {
      return;
    }
    const currentBookId = bookId;
    let timer: NodeJS.Timeout | null = null;
    const poll = async () => {
      try {
        const data = await fetchChapters(currentBookId);
        setChapters(data.chapters);
        setLlmInfo({ provider: data.llm_provider, model: data.llm_model });
        setUsageSummary({
          calls: data.calls ?? 0,
          tokensIn: data.tokens_in ?? 0,
          tokensOut: data.tokens_out ?? 0
        });
        setRunError(data.last_error || null);
        if (!activeChapterId && data.chapters.length > 0) {
          setActiveChapterId(data.chapters[0].chapter_id);
        }
        const hasProcessing = data.chapters.some((chapter) => chapter.status === "PROCESSING");
        const hasPending = data.chapters.some((chapter) => chapter.status === "PENDING");
        const hasActive = data.chapters.length === 0 || hasProcessing || hasPending;
        if (hasActive) {
          const interval = hasProcessing
            ? POLL_INTERVAL_PROCESSING_MS
            : POLL_INTERVAL_PENDING_MS;
          timer = setTimeout(poll, interval);
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
    const loadAssets = async () => {
      try {
        const data = await fetchAssets();
        setAssets(data);
        if (!selectedAssetId && data.length > 0) {
          setSelectedAssetId(data[0].id);
          const firstModel = data[0].models?.[0] || "";
          setSelectedAssetModel(firstModel);
        }
      } catch {
        // ignore asset errors on homepage
      }
    };
    loadAssets();
  }, []);

  useEffect(() => {
    if (!selectedAssetId) {
      if (selectedAssetModel) {
        setSelectedAssetModel("");
      }
      return;
    }
    if (assetModels.length === 0) {
      if (selectedAssetModel) {
        setSelectedAssetModel("");
      }
      return;
    }
    if (!assetModels.includes(selectedAssetModel)) {
      setSelectedAssetModel(assetModels[0]);
    }
  }, [selectedAssetId, assetModels.join("|"), selectedAssetModel]);

  useEffect(() => {
    if (!bookId) {
      if (heartbeatTimerRef.current) {
        clearTimeout(heartbeatTimerRef.current);
        heartbeatTimerRef.current = null;
      }
      return;
    }
    const hasProcessing =
      chapters.length === 0 ||
      chapters.some(
        (chapter) => chapter.status === "PROCESSING" || chapter.status === "PENDING"
      );
    if (!hasProcessing) {
      if (heartbeatTimerRef.current) {
        clearTimeout(heartbeatTimerRef.current);
        heartbeatTimerRef.current = null;
      }
      return;
    }
    const beat = async () => {
      const now = Date.now();
      const idleTooLong =
        document.visibilityState === "hidden" &&
        now - lastActivityRef.current >= HEARTBEAT_IDLE_TIMEOUT_MS;
      if (!idleTooLong) {
        try {
          await heartbeatBook(bookId);
        } catch {
          // ignore heartbeat errors to avoid noisy UI
        }
      }
      heartbeatTimerRef.current = setTimeout(beat, HEARTBEAT_INTERVAL_MS);
    };
    beat();
    return () => {
      if (heartbeatTimerRef.current) {
        clearTimeout(heartbeatTimerRef.current);
        heartbeatTimerRef.current = null;
      }
    };
  }, [bookId, chapters]);
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

    if (totalChapters === 0) {
      if (
        !progressMetaRef.current ||
        progressMetaRef.current.chapterId !== "__book__"
      ) {
        progressMetaRef.current = {
          chapterId: "__book__",
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

    if (allTerminal) {
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
    if (!selectedAssetId) {
      setError("请先在个人中心添加 API 资产，并选择模型");
      event.target.value = "";
      return;
    }
    if (!selectedAssetModel) {
      setError("当前资产未配置可用模型，请先完善模型列表");
      event.target.value = "";
      return;
    }
    setUploading(true);
    setError(null);
    try {
      const uploadResult = await uploadBook(file, bookType);
      setBookId(uploadResult.book_id);
      setChapters([]);
      setActiveChapterId(null);
      setGraph(null);
      setMarkdown("");
      await processBook(
        uploadResult.book_id,
        "custom",
        selectedAssetId,
        selectedAssetModel
      );
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

  if (!authReady) {
    return null;
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-logo">GP</div>
          <div className="brand-meta">
            <div className="brand-name">Graph Pivot</div>
            <div className="brand-desc">知识图谱阅读器</div>
          </div>
        </div>
        <nav className="top-nav">
          <Link href="/" className={`nav-link ${router.pathname === "/" ? "active" : ""}`}>
            知识图谱
          </Link>
          <Link href="/public" className="nav-link">
            公共书库
          </Link>
          <Link href="/account" className="nav-link">
            个人中心
          </Link>
        </nav>
        <div className="topbar-actions">
          <button
            className="icon-button"
            type="button"
            onClick={() => setSidebarOpen((open) => !open)}
            aria-label="toggle chapter sidebar"
          >
            <span className="hamburger" />
          </button>
          <div className="avatar-chip">U</div>
        </div>
      </header>

      <div className={`page-grid ${sidebarOpen ? "" : "sidebar-collapsed"}`}>
        <aside className={`sidebar ${sidebarOpen ? "open" : "collapsed"}`}>
          <div className="sidebar-header">
            <div>
              <div className="sidebar-title">章节列表</div>
              <div className="sidebar-subtitle">状态实时轮询</div>
            </div>
            <button
              className="icon-button ghost"
              type="button"
              aria-label="collapse sidebar"
              onClick={() => setSidebarOpen(false)}
            >
              ×
            </button>
          </div>
          <ChapterList
            chapters={chapters}
            activeId={activeChapterId}
            onSelect={(id) => {
              setActiveChapterId(id);
              setHighlightTerm(null);
              setEvidence(null);
            }}
          />
        </aside>

        <div className="content-column">
          <section className="page-heading">
            <div>
              <p className="eyebrow">Knowledge Graph</p>
              <h1 className="page-title">Graph Pivot</h1>
              <p className="page-desc">
                上传 PDF，生成章节级知识图谱，并在右侧阅读面板中联动高亮证据。
              </p>
            </div>
            <div className="pill">Backend: {API_BASE}</div>
          </section>

          {!hasConfig ? (
            <div className="banner banner-error">缺少 Supabase 配置，请检查环境变量。</div>
          ) : null}
          {error ? <div className="banner banner-error">{error}</div> : null}
          {runError ? (
            <div className="banner banner-error">模型调用失败：{runError}</div>
          ) : null}

          <section className="control-grid">
            <div className="panel control-card span-8">
              <div className="panel-title spaced">
                <div>
                  <div className="label-strong">模型配置</div>
                  {llmInfo ? (
                    <div className="muted">
                      当前：{llmInfo.provider}（{llmInfo.model}）
                    </div>
                  ) : (
                    <div className="muted">从个人中心添加并选择 API 资产</div>
                  )}
                </div>
              </div>
              <div className="control-row">
                <span className="field-label">API 资产</span>
                <select
                  value={selectedAssetId || ""}
                  onChange={(event) => {
                    const id = event.target.value;
                    setSelectedAssetId(id);
                    const asset = assets.find((item) => item.id === id);
                    setSelectedAssetModel(asset?.models?.[0] || "");
                  }}
                  disabled={assets.length === 0}
                >
                  {assets.length === 0 ? (
                    <option value="">请先在个人中心添加资产</option>
                  ) : (
                    assets.map((asset) => (
                      <option key={asset.id} value={asset.id}>
                        {asset.name} ({asset.provider})
                      </option>
                    ))
                  )}
                </select>
              </div>
              <div className="control-row">
                <span className="field-label">模型</span>
                <select
                  value={selectedAssetModel}
                  onChange={(event) => setSelectedAssetModel(event.target.value)}
                  disabled={!selectedAssetId || assetModels.length === 0}
                >
                  {assetModels.length === 0 ? (
                    <option value="">该资产暂无模型</option>
                  ) : (
                    assetModels.map((model) => (
                      <option key={model} value={model}>
                        {model}
                      </option>
                    ))
                  )}
                </select>
              </div>
            </div>

            <div className="panel control-card span-4">
              <div className="panel-title spaced">
                <div className="label-strong">书籍上传与加载</div>
                <div className="muted">PDF 上传或直接加载已有 book_id</div>
              </div>
              <div className="form-grid">
                <label className="field">
                  <span>书籍类型</span>
                  <select
                    value={bookType}
                    onChange={(event) => setBookType(event.target.value)}
                  >
                    {bookTypes.map((item) => (
                      <option key={item.key} value={item.key}>
                        {item.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  <span>上传 PDF</span>
                  <input
                    type="file"
                    accept="application/pdf"
                    onChange={handleUpload}
                    disabled={uploading}
                  />
                </label>
                <label className="field">
                  <span>已有 book_id</span>
                  <div className="input-row">
                    <input
                      type="text"
                      placeholder="输入已有 book_id"
                      value={manualBookId}
                      onChange={(event) => setManualBookId(event.target.value)}
                    />
                    <button className="primary" type="button" onClick={handleLoadBook}>
                      加载
                    </button>
                  </div>
                </label>
                <div className="input-row ghost-actions">
                  <button
                    className="ghost"
                    onClick={() => router.push("/public")}
                    type="button"
                  >
                    公共书库
                  </button>
                  <button
                    className="ghost"
                    onClick={() => router.push("/account")}
                    type="button"
                  >
                    个人中心
                  </button>
                </div>
              </div>
            </div>
          </section>

          {bookId ? (
            <div className="panel status-card">
              <div className="panel-title spaced">
                <div className="status-title">
                  <span
                    className={`progress-spinner ${shouldSpin ? "spinning" : "paused"}`}
                    aria-hidden="true"
                  />
                  <span className="label-strong">{Math.round(progressPercent)}%</span>
                </div>
                <div className="muted">{bookId}</div>
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
                <span>{doneCount}/{totalChapters || 0}</span>
                <span className="progress-label">{progressLabel}</span>
              </div>
              {usageSummary ? (
                <div className="progress-meta secondary">
                  Tokens: {usageSummary.tokensIn + usageSummary.tokensOut}（in{" "}
                  {usageSummary.tokensIn} / out {usageSummary.tokensOut}） · Calls{" "}
                  {usageSummary.calls}
                </div>
              ) : null}
            </div>
          ) : null}

          <section className="workspace">
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
          </section>
        </div>
      </div>
    </div>
  );
}
