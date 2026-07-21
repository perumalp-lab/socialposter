import { api } from "./api";

export type CalendarEvent = {
  type: "published" | "scheduled";
  date: string;
  time: string;
  platform: string;
  text: string;
  success?: boolean;
  post_url?: string | null;
  name?: string;
  schedule_id?: number;
};

export type CalendarPayload = {
  year: number;
  month: number;
  timezone: string | null;
  events: CalendarEvent[];
};

export const calendarApi = {
  events: (year: number, month: number) =>
    api.get<CalendarPayload>("/api/calendar/events", {
      query: { year, month },
    }),
};
