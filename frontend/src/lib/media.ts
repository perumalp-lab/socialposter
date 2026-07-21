import { api, uploadFile } from "./api";

export type MediaType = "image" | "video" | "document";

export type MediaAsset = {
  id: number;
  filename: string;
  file_path: string;
  url: string | null;
  media_type: MediaType;
  mime_type: string;
  file_size: number;
  tags: string[];
  alt_text: string;
  usage_count: number;
  created_at: string | null;
};

export type MediaListResponse = {
  items: MediaAsset[];
  page: number;
  per_page: number;
  total: number;
  pages: number;
};

export type UploadResponse = {
  ok: true;
  id: number;
  path: string;
  url: string;
  filename: string;
  media_type: MediaType;
  file_size: number;
};

export const mediaApi = {
  list: (params: {
    page?: number;
    type?: MediaType | "";
    search?: string;
    tag?: string;
  } = {}) =>
    api.get<MediaListResponse>("/api/media", {
      query: {
        page: params.page,
        type: params.type || undefined,
        search: params.search || undefined,
        tag: params.tag || undefined,
      },
    }),
  upload: (file: File, onProgress?: (pct: number) => void) =>
    uploadFile<UploadResponse>("/api/media/upload", file, onProgress),
  remove: (id: number) => api.delete<{ ok: true }>(`/api/media/${id}`),
  updateTags: (id: number, body: { tags?: string[]; alt_text?: string }) =>
    api.put<{ ok: true; tags: string[]; alt_text: string }>(
      `/api/media/${id}/tags`,
      body,
    ),
};

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${(bytes / 1024 / 1024 / 1024).toFixed(1)} GB`;
}
