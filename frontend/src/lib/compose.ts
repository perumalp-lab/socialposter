import { api } from "./api";

export type PlatformInfo = {
  name: string;
  display_name: string;
  post_types: string[];
  max_text_length: number | null;
  connected: boolean;
};

export type PostInput = {
  text: string;
  platforms: string[];
  media?: Array<Record<string, unknown>>;
  overrides?: Record<string, unknown>;
  dry_run?: boolean;
};

export type PostResult = {
  platform: string;
  success: boolean;
  post_id: string | null;
  post_url: string | null;
  error: string | null;
};

export const composeApi = {
  platforms: () => api.get<PlatformInfo[]>("/api/platforms"),
  post: (input: PostInput) =>
    api.post<{ ok?: boolean; results: PostResult[] }>("/api/post", input),
};
