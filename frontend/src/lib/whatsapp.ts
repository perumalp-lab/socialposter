import { api } from "./api";

export type WhatsAppSettings = {
  phone_number_id: string;
  business_account_id: string;
  has_access_token: boolean;
  webhook_verify_token: string;
};

export type WhatsAppMessage = {
  id: number;
  name: string;
  template_name: string;
  body: string;
  language: string;
  header_type: string;
  header_value: string;
  footer: string;
  created_at: string | null;
  updated_at: string | null;
};

export type WhatsAppMessageInput = {
  name: string;
  template_name?: string;
  body?: string;
  language?: string;
  header_type?: string;
  header_value?: string;
  footer?: string;
};

export const whatsappApi = {
  getSettings: () => api.get<WhatsAppSettings>("/api/whatsapp/settings"),
  updateSettings: (
    data: Partial<WhatsAppSettings> & { access_token?: string },
  ) => api.put<WhatsAppSettings>("/api/whatsapp/settings", data),
  sendTest: (to: string, body: string) =>
    api.post<{ ok: boolean; error?: string; message_id?: string }>(
      "/api/whatsapp/test",
      { to, body },
    ),
  listMessages: () => api.get<WhatsAppMessage[]>("/api/whatsapp/messages"),
  createMessage: (input: WhatsAppMessageInput) =>
    api.post<{ id: number; name: string }>("/api/whatsapp/messages", input),
  updateMessage: (id: number, input: Partial<WhatsAppMessageInput>) =>
    api.put<{ ok: boolean }>(`/api/whatsapp/messages/${id}`, input),
  deleteMessage: (id: number) =>
    api.delete<{ ok: boolean }>(`/api/whatsapp/messages/${id}`),
  sendMessage: (id: number, to: string) =>
    api.post<{ ok: boolean; error?: string; message_id?: string }>(
      `/api/whatsapp/messages/${id}/send`,
      { to },
    ),
};
