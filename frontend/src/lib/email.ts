import { api } from "./api";

export type EmailSettings = {
  from_name: string;
  from_email: string;
  reply_to_email: string;
  smtp_host: string;
  smtp_port: number;
  smtp_username: string;
  smtp_has_password: boolean;
};

export type EmailTemplate = {
  id: number;
  type_key: string;
  name: string;
  enabled: boolean;
};

export const emailApi = {
  getSettings: () => api.get<EmailSettings>("/api/email/settings"),
  updateSettings: (data: Partial<EmailSettings> & { smtp_password?: string }) =>
    api.put<EmailSettings>("/api/email/settings", data),
  testConnection: () =>
    api.post<{ ok: boolean; error?: string }>("/api/email/test-connection"),
  listTemplates: () => api.get<EmailTemplate[]>("/api/email/templates"),
  toggleTemplate: (id: number) =>
    api.post<EmailTemplate>(`/api/email/templates/${id}/toggle`),
  sendTest: (id: number) =>
    api.post<{ ok: boolean; error?: string }>(
      `/api/email/templates/${id}/send-test`,
    ),
};
