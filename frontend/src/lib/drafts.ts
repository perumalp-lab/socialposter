import { api, uploadFile } from "./api";

export type DraftStatus =
  | "draft"
  | "pending_approval"
  | "approved"
  | "rejected"
  | "published";

export type DraftListItem = {
  id: number;
  name: string;
  status: DraftStatus;
  platforms: string[];
  text: string;
  author: string;
  updated_at: string;
};

export type DraftDetail = DraftListItem & {
  media: Array<Record<string, unknown>>;
  overrides: Record<string, unknown>;
  author_id: number;
  reviewed_by: string | null;
  review_comment: string | null;
  reviewed_at: string | null;
  created_at: string;
  comments: Array<{ id: number; user: string; text: string; created_at: string }>;
};

export type DraftInput = {
  name: string;
  text: string;
  platforms: string[];
  media?: Array<Record<string, unknown>>;
  overrides?: Record<string, unknown>;
};

export const PLATFORMS = [
  "linkedin",
  "twitter",
  "facebook",
  "instagram",
  "youtube",
  "whatsapp",
] as const;

export type BulkImportResult = {
  ok: true;
  created_count: number;
  error_count: number;
  created: Array<{ row: number; id: number; name: string }>;
  errors: Array<{ row: number; error: string }>;
};

export type PublishResult = {
  platform: string;
  success: boolean;
  post_id: string | null;
  post_url: string | null;
  error: string | null;
};

export const draftsApi = {
  list: (status?: string) =>
    api.get<{ items: DraftListItem[] }>("/api/drafts", {
      query: status ? { status } : undefined,
    }),
  get: (id: number) => api.get<DraftDetail>(`/api/drafts/${id}`),
  create: (input: DraftInput) =>
    api.post<{ ok: true; id: number }>("/api/drafts", input),
  update: (id: number, input: Partial<DraftInput>) =>
    api.put<{ ok: true }>(`/api/drafts/${id}`, input),
  remove: (id: number) => api.delete<{ ok: true }>(`/api/drafts/${id}`),
  submit: (id: number) =>
    api.post<{ ok: true; status: DraftStatus }>(`/api/drafts/${id}/submit`),
  approve: (id: number, comment?: string) =>
    api.post<{ ok: true; status: DraftStatus }>(`/api/drafts/${id}/approve`, {
      comment: comment ?? "",
    }),
  reject: (id: number, comment: string) =>
    api.post<{ ok: true; status: DraftStatus }>(`/api/drafts/${id}/reject`, {
      comment,
    }),
  publish: (id: number) =>
    api.post<{ ok: true; results: PublishResult[] }>(
      `/api/drafts/${id}/publish`,
    ),
  bulkImport: (file: File, onProgress?: (pct: number) => void) =>
    uploadFile<BulkImportResult>("/api/drafts/bulk-import", file, onProgress),
};

export const SAMPLE_BULK_CSV = `name,platforms,text,status
"Q1 launch","linkedin,twitter","We're excited to announce our new pricing plan! Upgrade today for 20% off.","draft"
"Holiday promo","facebook,instagram","Holiday season is here. Free shipping all weekend.","draft"
"Webinar invite","linkedin","Join our webinar on AI in marketing — Tuesday at 2pm ET.","pending_approval"
`;
