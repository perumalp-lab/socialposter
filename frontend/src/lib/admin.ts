import { api } from "./api";

export type SettingField = {
  label: string;
  hint: string;
  set: boolean;
  masked: string;
};

export type AdminSettings = {
  oauth: Record<string, SettingField>;
  ai: Record<string, SettingField>;
  billing: Record<string, SettingField>;
};

export type ActivityLogEntry = {
  id: number;
  user_id: number | null;
  user_email: string | null;
  action: string;
  target_type: string | null;
  target_id: string | null;
  details: Record<string, unknown>;
  created_at: string | null;
};

export type ActivityLogPage = {
  items: ActivityLogEntry[];
  page: number;
  per_page: number;
  total: number;
  pages: number;
};

export type WebhookEventEntry = {
  id: number;
  platform: string;
  event_type: string | null;
  verified: boolean;
  processed: boolean;
  error: string | null;
  headers: Record<string, string>;
  payload_summary: string;
  created_at: string | null;
  processed_at: string | null;
};

export type WebhookEventPage = {
  items: WebhookEventEntry[];
  page: number;
  per_page: number;
  total: number;
  pages: number;
};

export const adminApi = {
  get: () => api.get<AdminSettings>("/api/admin/settings"),
  update: (body: Record<string, string>) =>
    api.put<{ ok: true; updated: string[] }>("/api/admin/settings", body),
  activity: (params: { page?: number; action?: string; userId?: number } = {}) =>
    api.get<ActivityLogPage>("/api/admin/activity", {
      query: {
        page: params.page,
        action: params.action || undefined,
        user_id: params.userId,
      },
    }),
  webhooks: (
    params: { page?: number; platform?: string; verified?: boolean | "" } = {},
  ) =>
    api.get<WebhookEventPage>("/api/admin/webhooks", {
      query: {
        page: params.page,
        platform: params.platform || undefined,
        verified:
          params.verified === true
            ? "true"
            : params.verified === false
              ? "false"
              : undefined,
      },
    }),
};
