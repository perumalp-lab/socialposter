import { api } from "./api";

export type Attendee = {
  email: string;
  name?: string;
};

export type Webinar = {
  id: number;
  title: string;
  description: string;
  scheduled_at: string | null;
  duration_minutes: number;
  platform_type: string;
  meeting_url: string;
  registration_url: string;
  recording_url: string;
  host_name: string;
  target_audience: string;
  timezone: string;
  tags: string[];
  max_attendees: number | null;
  status: string;
  attendees: Attendee[];
  invitations_sent_at: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type WebinarInput = {
  title: string;
  description?: string;
  scheduled_at?: string;
  duration_minutes?: number;
  platform_type?: string;
  meeting_url?: string;
  registration_url?: string;
  recording_url?: string;
  host_name?: string;
  target_audience?: string;
  timezone?: string;
  tags?: string[];
  max_attendees?: number | null;
  status?: string;
  attendees?: Attendee[];
};

export const webinarsApi = {
  list: () => api.get<Webinar[]>("/api/webinars"),
  get: (id: number) => api.get<Webinar>(`/api/webinars/${id}`),
  create: (input: WebinarInput) =>
    api.post<Webinar>("/api/webinars", input),
  update: (id: number, input: Partial<WebinarInput>) =>
    api.put<Webinar>(`/api/webinars/${id}`, input),
  remove: (id: number) =>
    api.delete<{ ok: true }>(`/api/webinars/${id}`),
  sendInvitations: (id: number) =>
    api.post<{
      ok: true;
      invitations_sent_at: string;
      results: Array<{ email: string; ok: boolean; error?: string }>;
      success_count: number;
      error_count: number;
    }>(`/api/webinars/${id}/send-invitations`),
};
