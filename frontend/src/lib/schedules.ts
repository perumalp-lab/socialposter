import { api } from "./api";

export type ScheduledPost = {
  id: number;
  name: string;
  platforms: string[];
  text: string;
  media: Array<Record<string, unknown>>;
  overrides: Record<string, unknown>;
  interval_minutes: number;
  next_run_at: string | null;
  enabled: boolean;
  created_at: string | null;
  updated_at: string | null;
};

export type ScheduleLog = {
  id: number;
  schedule_id: number;
  executed_at: string | null;
  results: unknown;
};

export type ScheduleDetail = ScheduledPost & {
  recent_logs: ScheduleLog[];
};

export type ScheduleInput = {
  name: string;
  platforms: string[];
  text: string;
  media?: Array<Record<string, unknown>>;
  overrides?: Record<string, unknown>;
  interval_minutes: number;
  start_at?: string;
};

export type ScheduleUpdate = Partial<ScheduleInput> & {
  enabled?: boolean;
  next_run_at?: string;
};

export const schedulesApi = {
  list: () => api.get<ScheduledPost[]>("/api/schedules"),
  get: (id: number) => api.get<ScheduleDetail>(`/api/schedules/${id}`),
  create: (input: ScheduleInput) =>
    api.post<ScheduledPost>("/api/schedules", input),
  update: (id: number, input: ScheduleUpdate) =>
    api.put<ScheduledPost>(`/api/schedules/${id}`, input),
  remove: (id: number) =>
    api.delete<{ ok: true }>(`/api/schedules/${id}`),
  logs: (id: number, params: { page?: number; per_page?: number } = {}) =>
    api.get<{
      schedule_id: number;
      page: number;
      per_page: number;
      logs: ScheduleLog[];
    }>(`/api/schedules/${id}/logs`, { query: params }),
};

// Repeat presets — picked to match common use cases without a custom UI.
export type RepeatPreset = "once" | "daily" | "weekly" | "custom";

export const REPEAT_PRESETS: Array<{
  value: RepeatPreset;
  label: string;
  intervalMinutes: number | null;
  hint: string;
}> = [
  {
    value: "once",
    label: "Once",
    intervalMinutes: 525600,
    hint: "Fires at the chosen time. Disable after to stop the next yearly re-run.",
  },
  {
    value: "daily",
    label: "Daily",
    intervalMinutes: 1440,
    hint: "Re-fires every day at the same time.",
  },
  {
    value: "weekly",
    label: "Weekly",
    intervalMinutes: 10080,
    hint: "Re-fires every 7 days at the same time.",
  },
  {
    value: "custom",
    label: "Custom interval",
    intervalMinutes: null,
    hint: "Pick your own re-fire interval.",
  },
];

export function describeInterval(minutes: number): string {
  if (minutes >= 525600) return "Once a year (effectively one-time)";
  if (minutes >= 10080 && minutes % 10080 === 0) {
    const w = minutes / 10080;
    return w === 1 ? "Weekly" : `Every ${w} weeks`;
  }
  if (minutes >= 1440 && minutes % 1440 === 0) {
    const d = minutes / 1440;
    return d === 1 ? "Daily" : `Every ${d} days`;
  }
  if (minutes >= 60 && minutes % 60 === 0) {
    const h = minutes / 60;
    return h === 1 ? "Hourly" : `Every ${h} hours`;
  }
  return minutes === 1 ? "Every minute" : `Every ${minutes} minutes`;
}

/** Formats Date → "YYYY-MM-DDTHH:mm" for use as <input type="datetime-local"> value. */
export function toDatetimeLocal(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** Parses datetime-local string in local time and returns ISO 8601 (UTC). */
export function fromDatetimeLocal(local: string): string {
  // The browser interprets datetime-local as local time. Convert to ISO.
  const d = new Date(local);
  return d.toISOString();
}
