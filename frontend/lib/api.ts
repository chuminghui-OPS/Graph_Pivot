import { getSupabaseClient } from "./supabase";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

async function getAccessToken() {
  const supabase = getSupabaseClient();
  if (!supabase) {
    throw new Error("Supabase not configured");
  }
  const { data, error } = await supabase.auth.getSession();
  if (error) {
    throw new Error(error.message);
  }
  const token = data.session?.access_token;
  if (!token) {
    throw new Error("Not authenticated");
  }
  return token;
}

async function authFetch(input: RequestInfo, init?: RequestInit) {
  const token = await getAccessToken();
  const headers = new Headers(init?.headers || {});
  headers.set("Authorization", `Bearer ${token}`);
  return fetch(input, { ...init, headers });
}

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

export async function uploadBook(file: File, bookType: string) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("book_type", bookType);
  const res = await authFetch(`${API_BASE}/api/books/upload`, {
    method: "POST",
    body: formData
  });
  if (!res.ok) {
    throw new Error(await res.text());
  }
  return res.json();
}

export async function processBook(
  bookId: string,
  llmProvider: string,
  assetId?: string | null,
  assetModel?: string | null
) {
  const url = new URL(`${API_BASE}/api/books/${bookId}/process`);
  url.searchParams.set("llm", llmProvider);
  if (assetId) {
    url.searchParams.set("asset_id", assetId);
    if (assetModel) {
      url.searchParams.set("asset_model", assetModel);
    }
  }
  const res = await authFetch(url.toString(), {
    method: "POST"
  });
  if (!res.ok) {
    throw new Error(await res.text());
  }
  return res.json();
}

export async function fetchChapters(bookId: string) {
  const res = await authFetch(`${API_BASE}/api/books/${bookId}/chapters`);
  if (!res.ok) {
    throw new Error(await res.text());
  }
  return (await res.json()) as ChapterListResponse;
}

export async function heartbeatBook(bookId: string) {
  const res = await authFetch(`${API_BASE}/api/books/${bookId}/heartbeat`, {
    method: "POST"
  });
  if (!res.ok) {
    throw new Error(await res.text());
  }
  return res.json();
}

export async function fetchChapterMarkdown(bookId: string, chapterId: string) {
  const res = await authFetch(
    `${API_BASE}/api/books/${bookId}/chapters/${chapterId}/md`
  );
  if (!res.ok) {
    throw new Error(await res.text());
  }
  return res.json();
}

export async function fetchChapterGraph(bookId: string, chapterId: string) {
  const res = await authFetch(
    `${API_BASE}/api/books/${bookId}/chapters/${chapterId}/graph`
  );
  if (!res.ok) {
    throw new Error(await res.text());
  }
  return (await res.json()) as KnowledgeGraph;
}

export async function fetchBookPdfUrl(bookId: string) {
  const res = await authFetch(`${API_BASE}/api/books/${bookId}/pdf`);
  if (!res.ok) {
    throw new Error(await res.text());
  }
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

export interface UserProfile {
  user_id: string;
  email?: string;
  full_name?: string;
  avatar_url?: string;
  plan: string;
  total_books: number;
}

export interface UserBook {
  book_id: string;
  title: string;
  created_at?: string;
}

export interface UserUsageBookRow {
  book_id: string;
  calls: number;
  tokens_in: number;
  tokens_out: number;
}

export interface ApiAsset {
  id: string;
  name: string;
  provider: string;
  api_mode: string;
  api_key_masked?: string | null;
  base_url?: string | null;
  api_path?: string | null;
  models?: string[] | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface ApiAssetCreateInput {
  name: string;
  provider: string;
  api_mode: string;
  api_key?: string;
  base_url?: string | null;
  api_path?: string | null;
  models?: string[] | null;
}

export interface ApiAssetUpdateInput {
  name?: string;
  provider?: string;
  api_mode?: string;
  api_key?: string;
  base_url?: string | null;
  api_path?: string | null;
  models?: string[] | null;
}

export interface BookType {
  key: string;
  code: string;
  label: string;
}

export interface PublicBook {
  id: string;
  title: string;
  cover_url?: string | null;
  owner_user_id: string;
  favorites_count: number;
  reposts_count: number;
  published_at?: string | null;
  updated_at?: string | null;
}

export async function fetchBookTypes() {
  const res = await fetch(`${API_BASE}/api/book-types`);
  if (!res.ok) {
    throw new Error(await res.text());
  }
  return (await res.json()) as BookType[];
}

export async function fetchPublicBooks(limit = 20, offset = 0) {
  const url = new URL(`${API_BASE}/api/public/books`);
  url.searchParams.set("limit", String(limit));
  url.searchParams.set("offset", String(offset));
  const res = await fetch(url.toString());
  if (!res.ok) {
    throw new Error(await res.text());
  }
  return (await res.json()) as PublicBook[];
}

export async function fetchUserProfile() {
  const res = await authFetch(`${API_BASE}/api/user/me`);
  if (!res.ok) {
    throw new Error(await res.text());
  }
  return (await res.json()) as UserProfile;
}

export async function fetchUserBooks() {
  const res = await authFetch(`${API_BASE}/api/user/books`);
  if (!res.ok) {
    throw new Error(await res.text());
  }
  return (await res.json()) as UserBook[];
}

export async function fetchUserUsage() {
  const res = await authFetch(`${API_BASE}/api/user/usage`);
  if (!res.ok) {
    throw new Error(await res.text());
  }
  return (await res.json()) as UserUsageBookRow[];
}

export async function fetchAssets() {
  const res = await authFetch(`${API_BASE}/api/assets`);
  if (!res.ok) {
    throw new Error(await res.text());
  }
  return (await res.json()) as ApiAsset[];
}

export async function createAsset(payload: ApiAssetCreateInput) {
  const res = await authFetch(`${API_BASE}/api/assets`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    throw new Error(await res.text());
  }
  return (await res.json()) as ApiAsset;
}

export async function fetchAssetModels(assetId: string) {
  const res = await authFetch(`${API_BASE}/api/assets/${assetId}/models/fetch`, {
    method: "POST"
  });
  if (!res.ok) {
    throw new Error(await res.text());
  }
  return (await res.json()) as ApiAsset;
}

export async function discoverAssetModels(assetId: string) {
  const res = await authFetch(`${API_BASE}/api/assets/${assetId}/models/discover`, {
    method: "POST"
  });
  if (!res.ok) {
    throw new Error(await res.text());
  }
  const data = (await res.json()) as { models?: string[] };
  return data.models || [];
}

export async function updateAsset(assetId: string, payload: ApiAssetUpdateInput) {
  const res = await authFetch(`${API_BASE}/api/assets/${assetId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    throw new Error(await res.text());
  }
  return (await res.json()) as ApiAsset;
}

export async function deleteAsset(assetId: string) {
  const res = await authFetch(`${API_BASE}/api/assets/${assetId}`, {
    method: "DELETE"
  });
  if (!res.ok) {
    throw new Error(await res.text());
  }
  return res.json();
}
