export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export type ChapterStatus =
  | "PENDING"
  | "PROCESSING"
  | "DONE"
  | "FAILED"
  | "SKIPPED_TOO_LARGE"
  | "TIMEOUT"
  | "PAUSED";

export interface Chapter {
  chapter_id: string;
  title: string;
  status: ChapterStatus;
}

export interface ChapterListResponse {
  book_id: string;
  llm_provider: string;
  llm_model: string;
  chapters: Chapter[];
}

export interface KnowledgeGraph {
  chapter_id: string;
  nodes: { id: string; name: string; type: string }[];
  edges: {
    source: string;
    target: string;
    relation: string;
    evidence: string;
    confidence: number;
  }[];
}

export async function uploadBook(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE}/api/books/upload`, {
    method: "POST",
    body: formData
  });
  if (!res.ok) {
    throw new Error(await res.text());
  }
  return res.json();
}

export async function processBook(bookId: string, llmProvider: string) {
  const url = new URL(`${API_BASE}/api/books/${bookId}/process`);
  url.searchParams.set("llm", llmProvider);
  const res = await fetch(url.toString(), {
    method: "POST"
  });
  if (!res.ok) {
    throw new Error(await res.text());
  }
  return res.json();
}

export async function fetchChapters(bookId: string) {
  const res = await fetch(`${API_BASE}/api/books/${bookId}/chapters`);
  if (!res.ok) {
    throw new Error(await res.text());
  }
  return (await res.json()) as ChapterListResponse;
}

export async function heartbeatBook(bookId: string) {
  const res = await fetch(`${API_BASE}/api/books/${bookId}/heartbeat`, {
    method: "POST"
  });
  if (!res.ok) {
    throw new Error(await res.text());
  }
  return res.json();
}

export async function fetchChapterMarkdown(bookId: string, chapterId: string) {
  const res = await fetch(
    `${API_BASE}/api/books/${bookId}/chapters/${chapterId}/md`
  );
  if (!res.ok) {
    throw new Error(await res.text());
  }
  return res.json();
}

export async function fetchChapterGraph(bookId: string, chapterId: string) {
  const res = await fetch(
    `${API_BASE}/api/books/${bookId}/chapters/${chapterId}/graph`
  );
  if (!res.ok) {
    throw new Error(await res.text());
  }
  return (await res.json()) as KnowledgeGraph;
}

export function bookPdfUrl(bookId: string) {
  return `${API_BASE}/api/books/${bookId}/pdf`;
}
