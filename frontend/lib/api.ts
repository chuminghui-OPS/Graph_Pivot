import { getSupabaseClient } from "./supabase";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

async function getAccessToken() {
  const supabase = getSupabaseClient();
  if (!supabase) throw new Error("Supabase not configured");
  const { data, error } = await supabase.auth.getSession();
  if (error) throw new Error(error.message);
  const token = data.session?.access_token;
  if (!token) throw new Error("Not authenticated");
  return token;
}

async function authFetch(input: RequestInfo, init?: RequestInit) {
  const token = await getAccessToken();
  const headers = new Headers(init?.headers || {});
  headers.set("Authorization", `Bearer ${token}`);
  return fetch(input, { ...init, headers });
}

async function apiRequest<T>(input: RequestInfo, init?: RequestInit): Promise<T> {
  const res = await authFetch(input, init);
  if (!res.ok) throw new Error(await res.text());
  return res.json() as Promise<T>;
}

async function publicRequest<T>(input: RequestInfo, init?: RequestInit): Promise<T> {
  const res = await fetch(input, init);
  if (!res.ok) throw new Error(await res.text());
  return res.json() as Promise<T>;
}

const jsonInit = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body)
});

const graphUrl = (bookId: string, chapterId: string) =>
  `${API_BASE}/api/books/${bookId}/chapters/${chapterId}/graph`;

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
  calls?: number;
  tokens_in?: number;
  tokens_out?: number;
  last_error?: string | null;
  chapters: Chapter[];
}

export interface KnowledgeGraph {
  chapter_id: string;
  nodes: { id: string; name: string; type: string }[];
  edges: {
    id?: string;
    source: string;
    target: string;
    relation: string;
    evidence: string;
    confidence: number;
    source_text_location?: string | null;
  }[];
}

export interface GraphNodeCreateInput {
  id?: string;
  name: string;
  type: string;
}

export interface GraphNodeUpdateInput {
  name?: string;
  type?: string;
}

export interface GraphEdgeCreateInput {
  id?: string;
  source: string;
  target: string;
  relation: string;
  evidence?: string;
  confidence?: number;
  source_text_location?: string | null;
}

export interface GraphEdgeUpdateInput {
  id?: string;
  source?: string;
  target?: string;
  relation?: string;
  evidence?: string;
  confidence?: number;
  source_text_location?: string | null;
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

export async function uploadBook(file: File, bookType: string) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("book_type", bookType);
  return apiRequest(`${API_BASE}/api/books/upload`, { method: "POST", body: formData });
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
    if (assetModel) url.searchParams.set("asset_model", assetModel);
  }
  return apiRequest(url.toString(), { method: "POST" });
}

export async function fetchChapters(bookId: string) {
  return apiRequest<ChapterListResponse>(`${API_BASE}/api/books/${bookId}/chapters`);
}

export async function heartbeatBook(bookId: string) {
  return apiRequest(`${API_BASE}/api/books/${bookId}/heartbeat`, { method: "POST" });
}

export async function fetchChapterMarkdown(bookId: string, chapterId: string) {
  return apiRequest<{ chapter_id: string; markdown: string }>(
    `${API_BASE}/api/books/${bookId}/chapters/${chapterId}/md`
  );
}

export async function fetchChapterGraph(bookId: string, chapterId: string) {
  return apiRequest<KnowledgeGraph>(`${API_BASE}/api/books/${bookId}/chapters/${chapterId}/graph`);
}

export async function createGraphNode(bookId: string, chapterId: string, payload: GraphNodeCreateInput) {
  return apiRequest(graphUrl(bookId, chapterId) + "/nodes", jsonInit("POST", payload));
}

export async function updateGraphNode(bookId: string, chapterId: string, nodeId: string, payload: GraphNodeUpdateInput) {
  return apiRequest(graphUrl(bookId, chapterId) + `/nodes/${nodeId}`, jsonInit("PATCH", payload));
}

export async function deleteGraphNode(bookId: string, chapterId: string, nodeId: string) {
  return apiRequest(graphUrl(bookId, chapterId) + `/nodes/${nodeId}`, { method: "DELETE" });
}

export async function createGraphEdge(bookId: string, chapterId: string, payload: GraphEdgeCreateInput) {
  return apiRequest(graphUrl(bookId, chapterId) + "/edges", jsonInit("POST", payload));
}

export async function updateGraphEdge(bookId: string, chapterId: string, edgeId: string, payload: GraphEdgeUpdateInput) {
  return apiRequest(graphUrl(bookId, chapterId) + `/edges/${edgeId}`, jsonInit("PATCH", payload));
}

export async function deleteGraphEdge(bookId: string, chapterId: string, edgeId: string) {
  return apiRequest(graphUrl(bookId, chapterId) + `/edges/${edgeId}`, { method: "DELETE" });
}

export async function fetchBookPdfUrl(bookId: string) {
  const res = await authFetch(`${API_BASE}/api/books/${bookId}/pdf`);
  if (!res.ok) throw new Error(await res.text());
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

export async function fetchBookTypes() {
  return publicRequest<BookType[]>(`${API_BASE}/api/book-types`);
}

export async function fetchPublicBooks(limit = 20, offset = 0) {
  const url = new URL(`${API_BASE}/api/public/books`);
  url.searchParams.set("limit", String(limit));
  url.searchParams.set("offset", String(offset));
  return publicRequest<PublicBook[]>(url.toString());
}

export async function publishBook(bookId: string, payload?: { title?: string; cover_url?: string }) {
  return apiRequest(`${API_BASE}/api/books/${bookId}/publish`, jsonInit("POST", payload || {}));
}

export async function unpublishBook(bookId: string) {
  return apiRequest(`${API_BASE}/api/books/${bookId}/publish`, { method: "DELETE" });
}

export async function deleteBook(bookId: string) {
  return apiRequest(`${API_BASE}/api/books/${bookId}`, { method: "DELETE" });
}

export async function fetchUserProfile() {
  return apiRequest<UserProfile>(`${API_BASE}/api/user/me`);
}

export async function fetchUserBooks() {
  return apiRequest<UserBook[]>(`${API_BASE}/api/user/books`);
}

export async function fetchUserUsage() {
  return apiRequest<UserUsageBookRow[]>(`${API_BASE}/api/user/usage`);
}

export async function fetchAssets() {
  return apiRequest<ApiAsset[]>(`${API_BASE}/api/assets`);
}

export async function createAsset(payload: ApiAssetCreateInput) {
  return apiRequest<ApiAsset>(`${API_BASE}/api/assets`, jsonInit("POST", payload));
}

export async function fetchAssetModels(assetId: string) {
  return apiRequest<ApiAsset>(`${API_BASE}/api/assets/${assetId}/models/fetch`, { method: "POST" });
}

export async function discoverAssetModels(assetId: string) {
  const data = await apiRequest<{ models?: string[] }>(
    `${API_BASE}/api/assets/${assetId}/models/discover`,
    { method: "POST" }
  );
  return data.models || [];
}

export async function updateAsset(assetId: string, payload: ApiAssetUpdateInput) {
  return apiRequest<ApiAsset>(`${API_BASE}/api/assets/${assetId}`, jsonInit("PUT", payload));
}

export async function deleteAsset(assetId: string) {
  return apiRequest(`${API_BASE}/api/assets/${assetId}`, { method: "DELETE" });
}
