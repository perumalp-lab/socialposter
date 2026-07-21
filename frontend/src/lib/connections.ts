import { api } from "./api";
import type { PlatformInfo } from "./compose";

export type OAuthStatus = Record<string, boolean>;

export const connectionsApi = {
  platforms: () => api.get<PlatformInfo[]>("/api/platforms"),
  oauthStatus: () => api.get<OAuthStatus>("/api/oauth/status"),
  disconnect: (platform: string) =>
    api.post<{ ok: true; removed: string[] }>(
      `/api/connection/${platform}/disconnect`,
    ),
  saveExtraConfig: (platform: string, body: Record<string, string>) =>
    api.post<{ ok: true; extra_data: Record<string, unknown> }>(
      `/api/connection/${platform}/config`,
      body,
    ),
};

export const PLATFORM_GROUPS: Array<{
  oauth_key: string;
  members: Array<{
    name: string;
    display_name: string;
    extra_keys?: Array<{ key: string; label: string; hint?: string }>;
  }>;
}> = [
  {
    oauth_key: "linkedin",
    members: [{ name: "linkedin", display_name: "LinkedIn" }],
  },
  {
    oauth_key: "twitter",
    members: [{ name: "twitter", display_name: "X (Twitter)" }],
  },
  {
    oauth_key: "youtube",
    members: [{ name: "youtube", display_name: "YouTube" }],
  },
  {
    oauth_key: "meta",
    members: [
      {
        name: "facebook",
        display_name: "Facebook",
        extra_keys: [
          { key: "page_id", label: "Page ID", hint: "Auto-filled on connect" },
        ],
      },
      {
        name: "instagram",
        display_name: "Instagram",
        extra_keys: [
          {
            key: "business_account_id",
            label: "Business account ID",
            hint: "Auto-discovered if your FB Page is linked to IG",
          },
        ],
      },
      {
        name: "whatsapp",
        display_name: "WhatsApp",
        extra_keys: [
          { key: "phone_number_id", label: "Phone number ID" },
        ],
      },
    ],
  },
];
