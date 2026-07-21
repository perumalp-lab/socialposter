import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  ChevronLeft,
  ChevronRight,
  Clock,
  ExternalLink,
  PenSquare,
  XCircle,
} from "lucide-react";
import { ApiError } from "@/lib/api";
import { calendarApi, type CalendarEvent } from "@/lib/calendar";
import { PlatformBadge } from "@/components/PlatformBadge";
import { platformBrand } from "@/lib/platformColors";
import { cn } from "@/lib/utils";

const MONTH_NAMES = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

const WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export function CalendarPage() {
  const today = useMemo(() => new Date(), []);
  const [year, setYear] = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth() + 1);
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [tz, setTz] = useState<string | null>(null);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await calendarApi.events(year, month);
      setEvents(res.events);
      setTz(res.timezone);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Failed to load calendar",
      );
    } finally {
      setLoading(false);
    }
  }, [year, month]);

  useEffect(() => {
    void load();
  }, [load]);

  // Group events by date for fast lookup
  const eventsByDate = useMemo(() => {
    const map = new Map<string, CalendarEvent[]>();
    for (const e of events) {
      const list = map.get(e.date) ?? [];
      list.push(e);
      map.set(e.date, list);
    }
    // sort each day's events by time
    for (const [, list] of map) {
      list.sort((a, b) => a.time.localeCompare(b.time));
    }
    return map;
  }, [events]);

  const grid = useMemo(() => buildMonthGrid(year, month), [year, month]);

  const todayKey = formatDate(today);
  const monthKey = `${year}-${String(month).padStart(2, "0")}`;

  const goToPrev = () => {
    const m = month - 1;
    if (m < 1) {
      setYear(year - 1);
      setMonth(12);
    } else {
      setMonth(m);
    }
    setSelectedDate(null);
  };

  const goToNext = () => {
    const m = month + 1;
    if (m > 12) {
      setYear(year + 1);
      setMonth(1);
    } else {
      setMonth(m);
    }
    setSelectedDate(null);
  };

  const goToToday = () => {
    setYear(today.getFullYear());
    setMonth(today.getMonth() + 1);
    setSelectedDate(todayKey);
  };

  const selectedEvents = selectedDate
    ? (eventsByDate.get(selectedDate) ?? [])
    : [];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Calendar</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Monthly overview of scheduled and published posts.
            {tz && (
              <span className="ml-1 text-xs text-muted-foreground/80">
                ({tz})
              </span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={goToPrev}
            className="grid h-8 w-8 place-items-center rounded-md border border-border bg-background text-sm hover:bg-accent"
            aria-label="Previous month"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <span className="min-w-[140px] text-center text-sm font-medium">
            {MONTH_NAMES[month - 1]} {year}
          </span>
          <button
            type="button"
            onClick={goToNext}
            className="grid h-8 w-8 place-items-center rounded-md border border-border bg-background text-sm hover:bg-accent"
            aria-label="Next month"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={goToToday}
            className="h-8 rounded-md border border-border bg-background px-3 text-xs font-medium hover:bg-accent"
          >
            Today
          </button>
          <Link
            to="/compose"
            className="inline-flex h-8 items-center gap-1 rounded-md bg-primary px-3 text-xs font-medium text-primary-foreground hover:bg-primary/90"
          >
            <PenSquare className="h-3.5 w-3.5" />
            Compose
          </Link>
        </div>
      </div>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <section className="overflow-hidden rounded-lg border border-border bg-background lg:col-span-2">
          <div className="grid grid-cols-7 border-b border-border bg-muted/30 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            {WEEKDAY_LABELS.map((d) => (
              <div key={d} className="px-2 py-2">
                {d}
              </div>
            ))}
          </div>
          <div className="grid grid-cols-7">
            {grid.map((cell, idx) => {
              const isCurrentMonth = cell.month === month;
              const cellKey = formatDateParts(cell.year, cell.month, cell.day);
              const dayEvents = eventsByDate.get(cellKey) ?? [];
              const isToday = cellKey === todayKey;
              const isSelected = cellKey === selectedDate;
              return (
                <button
                  key={idx}
                  type="button"
                  onClick={() => setSelectedDate(cellKey)}
                  className={cn(
                    "min-h-[88px] border-b border-r border-border p-1.5 text-left transition-colors",
                    "hover:bg-accent/40",
                    !isCurrentMonth && "bg-muted/20 text-muted-foreground/60",
                    isSelected && "bg-primary/5 ring-1 ring-inset ring-primary/40",
                  )}
                >
                  <div className="flex items-center justify-between">
                    <span
                      className={cn(
                        "grid h-6 w-6 place-items-center rounded-full text-xs",
                        isToday && "bg-primary font-semibold text-primary-foreground",
                      )}
                    >
                      {cell.day}
                    </span>
                    {dayEvents.length > 0 && (
                      <span className="text-[10px] font-medium text-muted-foreground">
                        {dayEvents.length}
                      </span>
                    )}
                  </div>
                  <div className="mt-1 space-y-0.5">
                    {dayEvents.slice(0, 3).map((e, i) => (
                      <EventChip key={i} event={e} />
                    ))}
                    {dayEvents.length > 3 && (
                      <div className="text-[10px] text-muted-foreground">
                        +{dayEvents.length - 3} more
                      </div>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
          {loading && (
            <div className="border-t border-border px-5 py-3 text-xs text-muted-foreground">
              Loading {monthKey}…
            </div>
          )}
        </section>

        <aside className="rounded-lg border border-border bg-background">
          <header className="border-b border-border px-5 py-3">
            <h2 className="text-sm font-semibold">
              {selectedDate
                ? formatHumanDate(selectedDate)
                : "Select a day"}
            </h2>
            <p className="text-xs text-muted-foreground">
              {selectedDate
                ? `${selectedEvents.length} event${selectedEvents.length === 1 ? "" : "s"}`
                : "Click any day in the calendar to view its posts."}
            </p>
          </header>
          <div className="p-5">
            {!selectedDate && (
              <div className="py-6 text-center text-sm text-muted-foreground">
                Pick a day to see scheduled and published posts.
              </div>
            )}
            {selectedDate && selectedEvents.length === 0 && (
              <div className="flex flex-col items-center gap-3 py-6 text-center text-sm text-muted-foreground">
                <span>Nothing on this day.</span>
                <Link
                  to="/compose"
                  className="inline-flex items-center gap-1 rounded-md border border-border bg-background px-3 py-1.5 text-xs font-medium text-foreground hover:bg-accent"
                >
                  <PenSquare className="h-3 w-3" />
                  Compose a post
                </Link>
              </div>
            )}
            {selectedEvents.length > 0 && (
              <ul className="space-y-3">
                {selectedEvents.map((e, i) => (
                  <EventDetail key={i} event={e} />
                ))}
              </ul>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}

function EventChip({ event }: { event: CalendarEvent }) {
  const platforms = event.platform.split(",").filter(Boolean);
  const primary = platforms[0] ?? "unknown";
  const brand = platformBrand(primary);
  const isFailed = event.type === "published" && event.success === false;

  return (
    <div
      className={cn(
        "flex items-center gap-1 truncate rounded px-1.5 py-0.5 text-[10px]",
        event.type === "scheduled"
          ? "border border-dashed"
          : isFailed
            ? "bg-red-100 text-red-800"
            : "",
      )}
      style={
        event.type === "scheduled"
          ? { borderColor: brand.bg, color: brand.softFg, background: brand.softBg }
          : !isFailed
            ? { background: brand.softBg, color: brand.softFg }
            : undefined
      }
      title={`${event.time} – ${event.text}`}
    >
      <span className="font-mono">{event.time}</span>
      <span className="truncate">{event.text || event.name || "(no text)"}</span>
    </div>
  );
}

function EventDetail({ event }: { event: CalendarEvent }) {
  const platforms = event.platform.split(",").filter(Boolean);
  const isFailed = event.type === "published" && event.success === false;

  return (
    <li className="rounded-md border border-border bg-muted/10 p-3">
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <span
          className={cn(
            "rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide",
            event.type === "scheduled"
              ? "border border-dashed border-border text-muted-foreground"
              : isFailed
                ? "bg-red-100 text-red-800"
                : "bg-emerald-100 text-emerald-800",
          )}
        >
          {event.type}
        </span>
        <span className="inline-flex items-center gap-1">
          <Clock className="h-3 w-3" />
          {event.time}
        </span>
        {platforms.map((p) => (
          <PlatformBadge key={p} platform={p} variant="dot" />
        ))}
        {isFailed && (
          <span className="inline-flex items-center gap-1 text-red-700">
            <XCircle className="h-3 w-3" />
            failed
          </span>
        )}
      </div>
      <p className="mt-2 line-clamp-3 text-sm">
        {event.text || event.name || "(no text)"}
      </p>
      {event.post_url && (
        <a
          href={event.post_url}
          target="_blank"
          rel="noreferrer"
          className="mt-2 inline-flex items-center gap-1 text-xs text-primary hover:underline"
        >
          Open post
          <ExternalLink className="h-3 w-3" />
        </a>
      )}
    </li>
  );
}

type Cell = { year: number; month: number; day: number };

function buildMonthGrid(year: number, month: number): Cell[] {
  // Mon-first 6-week grid covering the month.
  const first = new Date(year, month - 1, 1);
  const firstDow = (first.getDay() + 6) % 7; // 0 = Mon
  const start = new Date(year, month - 1, 1 - firstDow);

  const cells: Cell[] = [];
  for (let i = 0; i < 42; i++) {
    const d = new Date(start);
    d.setDate(start.getDate() + i);
    cells.push({
      year: d.getFullYear(),
      month: d.getMonth() + 1,
      day: d.getDate(),
    });
  }
  return cells;
}

function formatDateParts(y: number, m: number, d: number): string {
  return `${y}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
}

function formatDate(d: Date): string {
  return formatDateParts(d.getFullYear(), d.getMonth() + 1, d.getDate());
}

function formatHumanDate(key: string): string {
  const [y, m, d] = key.split("-").map(Number);
  const date = new Date(y, m - 1, d);
  return date.toLocaleDateString(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}
