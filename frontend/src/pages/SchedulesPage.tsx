import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowUpRight,
  CalendarClock,
  ClipboardList,
  Loader2,
  Pencil,
  Trash2,
} from "lucide-react";
import { ApiError } from "@/lib/api";
import {
  describeInterval,
  fromDatetimeLocal,
  schedulesApi,
  toDatetimeLocal,
  type ScheduledPost,
  type ScheduleLog,
} from "@/lib/schedules";
import { cn } from "@/lib/utils";

export function SchedulesPage() {
  const [items, setItems] = useState<ScheduledPost[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<ScheduledPost | null>(null);
  const [logsFor, setLogsFor] = useState<ScheduledPost | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await schedulesApi.list();
      setItems(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function toggle(s: ScheduledPost) {
    setItems((curr) =>
      curr.map((x) => (x.id === s.id ? { ...x, enabled: !x.enabled } : x)),
    );
    try {
      await schedulesApi.update(s.id, { enabled: !s.enabled });
    } catch (err) {
      setItems((curr) =>
        curr.map((x) => (x.id === s.id ? { ...x, enabled: s.enabled } : x)),
      );
      setError(err instanceof ApiError ? err.message : "Toggle failed");
    }
  }

  async function remove(s: ScheduledPost) {
    if (!confirm(`Delete schedule "${s.name}"?`)) return;
    try {
      await schedulesApi.remove(s.id);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Delete failed");
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Schedules</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Recurring posts. Disable any time to pause future runs without
          losing the content.
        </p>
      </div>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      {loading ? (
        <div className="text-sm text-muted-foreground">Loading…</div>
      ) : items.length === 0 ? (
        <EmptyState />
      ) : (
        <ul className="space-y-3">
          {items.map((s) => (
            <ScheduleCard
              key={s.id}
              schedule={s}
              onToggle={() => void toggle(s)}
              onEdit={() => setEditing(s)}
              onLogs={() => setLogsFor(s)}
              onDelete={() => void remove(s)}
            />
          ))}
        </ul>
      )}

      {editing && (
        <EditorDrawer
          schedule={editing}
          onClose={() => setEditing(null)}
          onSaved={async () => {
            setEditing(null);
            await refresh();
          }}
        />
      )}

      {logsFor && (
        <LogsDrawer schedule={logsFor} onClose={() => setLogsFor(null)} />
      )}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border bg-background py-16 text-center">
      <CalendarClock className="h-8 w-8 text-muted-foreground" />
      <p className="mt-3 text-sm font-medium">No schedules yet</p>
      <p className="mt-1 max-w-md text-xs text-muted-foreground">
        Schedules let you publish a post on a recurring interval. Compose a post
        and click <strong>Schedule</strong> to set a first-run time.
      </p>
      <Link
        to="/compose"
        className="mt-4 inline-flex items-center gap-1 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:opacity-90"
      >
        Compose your first post
        <ArrowUpRight className="h-3 w-3" />
      </Link>
    </div>
  );
}

function ScheduleCard({
  schedule,
  onToggle,
  onEdit,
  onLogs,
  onDelete,
}: {
  schedule: ScheduledPost;
  onToggle: () => void;
  onEdit: () => void;
  onLogs: () => void;
  onDelete: () => void;
}) {
  const next = schedule.next_run_at
    ? new Date(schedule.next_run_at).toLocaleString()
    : "—";

  return (
    <li className="flex items-start gap-4 rounded-lg border border-border bg-background p-4">
      <button
        type="button"
        onClick={onToggle}
        aria-label={schedule.enabled ? "Disable" : "Enable"}
        className={cn(
          "mt-0.5 flex h-6 w-10 shrink-0 items-center rounded-full p-0.5 transition-colors",
          schedule.enabled ? "bg-primary" : "bg-muted",
        )}
      >
        <span
          className={cn(
            "h-5 w-5 rounded-full bg-white shadow transition-transform",
            schedule.enabled && "translate-x-4",
          )}
        />
      </button>

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "truncate text-sm font-semibold",
              !schedule.enabled && "text-muted-foreground",
            )}
          >
            {schedule.name}
          </span>
          {!schedule.enabled && (
            <span className="rounded-full bg-muted px-1.5 text-[10px] font-medium text-muted-foreground">
              paused
            </span>
          )}
        </div>
        <div className="mt-0.5 line-clamp-1 text-xs text-muted-foreground">
          {schedule.text}
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
          <span>{describeInterval(schedule.interval_minutes)}</span>
          <span>·</span>
          <span>Next: {next}</span>
          {schedule.platforms.length > 0 && (
            <>
              <span>·</span>
              <span>{schedule.platforms.join(", ")}</span>
            </>
          )}
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-1">
        <button
          type="button"
          onClick={onLogs}
          className="flex h-8 items-center gap-1 rounded-md px-2 text-xs text-muted-foreground hover:bg-accent"
        >
          <ClipboardList className="h-3.5 w-3.5" />
          Logs
        </button>
        <button
          type="button"
          onClick={onEdit}
          aria-label="Edit"
          className="grid h-8 w-8 place-items-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground"
        >
          <Pencil className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={onDelete}
          aria-label="Delete"
          className="grid h-8 w-8 place-items-center rounded-md text-muted-foreground hover:bg-red-50 hover:text-red-600"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      </div>
    </li>
  );
}

function EditorDrawer({
  schedule,
  onClose,
  onSaved,
}: {
  schedule: ScheduledPost;
  onClose: () => void;
  onSaved: () => Promise<void>;
}) {
  const initialNextRun = useMemo(
    () =>
      schedule.next_run_at
        ? toDatetimeLocal(new Date(schedule.next_run_at))
        : "",
    [schedule.next_run_at],
  );

  const [name, setName] = useState(schedule.name);
  const [text, setText] = useState(schedule.text);
  const [intervalMin, setIntervalMin] = useState<number>(
    schedule.interval_minutes,
  );
  const [nextRun, setNextRun] = useState(initialNextRun);
  const [platformsCsv, setPlatformsCsv] = useState(schedule.platforms.join(", "));
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    setSubmitting(true);
    setError(null);
    try {
      await schedulesApi.update(schedule.id, {
        name: name.trim() || schedule.name,
        text,
        interval_minutes: Math.max(1, Math.floor(intervalMin)),
        next_run_at: nextRun ? fromDatetimeLocal(nextRun) : undefined,
        platforms: platformsCsv
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
      });
      await onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Save failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <div
        onClick={onClose}
        aria-hidden
        className="fixed inset-0 z-40 bg-black/40 animate-fade-in"
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-label="Edit schedule"
        className="fixed inset-y-0 right-0 z-50 flex w-full max-w-xl flex-col border-l border-border bg-background shadow-2xl"
      >
        <div className="flex h-14 shrink-0 items-center justify-between border-b border-border px-5">
          <h2 className="text-base font-semibold">Edit schedule</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md px-2 py-1 text-sm text-muted-foreground hover:bg-accent hover:text-foreground"
          >
            Close
          </button>
        </div>
        <div className="flex-1 space-y-4 overflow-y-auto p-5">
          <Field label="Name">
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </Field>
          <Field label="Content">
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={6}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </Field>
          <Field label="Platforms (comma-separated)">
            <input
              type="text"
              value={platformsCsv}
              onChange={(e) => setPlatformsCsv(e.target.value)}
              placeholder="linkedin, twitter"
              className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Next run (your local time)">
              <input
                type="datetime-local"
                value={nextRun}
                onChange={(e) => setNextRun(e.target.value)}
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </Field>
            <Field label="Interval (minutes)">
              <input
                type="number"
                min={1}
                value={intervalMin}
                onChange={(e) =>
                  setIntervalMin(Math.max(1, Number(e.target.value) || 1))
                }
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
              <span className="mt-1 block text-[11px] text-muted-foreground">
                {describeInterval(intervalMin)}
              </span>
            </Field>
          </div>
          {error && (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          )}
        </div>
        <div className="flex shrink-0 items-center justify-end gap-2 border-t border-border px-5 py-3">
          <button
            type="button"
            onClick={onClose}
            className="h-9 rounded-md px-3 text-sm hover:bg-accent"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => void save()}
            disabled={submitting}
            className="flex h-9 items-center gap-1.5 rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-60"
          >
            {submitting && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            Save changes
          </button>
        </div>
      </aside>
    </>
  );
}

function LogsDrawer({
  schedule,
  onClose,
}: {
  schedule: ScheduledPost;
  onClose: () => void;
}) {
  const [logs, setLogs] = useState<ScheduleLog[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    schedulesApi
      .logs(schedule.id, { page: 1, per_page: 50 })
      .then((data) => {
        if (!cancelled) setLogs(data.logs);
      })
      .catch((err) => {
        if (!cancelled)
          setError(err instanceof ApiError ? err.message : "Failed");
      });
    return () => {
      cancelled = true;
    };
  }, [schedule.id]);

  return (
    <>
      <div
        onClick={onClose}
        aria-hidden
        className="fixed inset-0 z-40 bg-black/40 animate-fade-in"
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-label="Schedule logs"
        className="fixed inset-y-0 right-0 z-50 flex w-full max-w-xl flex-col border-l border-border bg-background shadow-2xl"
      >
        <div className="flex h-14 shrink-0 items-center justify-between border-b border-border px-5">
          <div>
            <h2 className="truncate text-base font-semibold">
              Logs · {schedule.name}
            </h2>
            <p className="text-xs text-muted-foreground">Last 50 runs</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md px-2 py-1 text-sm text-muted-foreground hover:bg-accent hover:text-foreground"
          >
            Close
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-5">
          {error ? (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          ) : !logs ? (
            <div className="text-sm text-muted-foreground">Loading…</div>
          ) : logs.length === 0 ? (
            <div className="rounded-md border border-dashed border-border bg-muted/30 px-4 py-8 text-center text-sm text-muted-foreground">
              No runs yet.
            </div>
          ) : (
            <ul className="space-y-3">
              {logs.map((l) => (
                <li
                  key={l.id}
                  className="rounded-md border border-border bg-background p-3 text-xs"
                >
                  <div className="font-medium">
                    {l.executed_at
                      ? new Date(l.executed_at).toLocaleString()
                      : "—"}
                  </div>
                  {l.results !== null && l.results !== undefined && (
                    <pre className="mt-1 overflow-x-auto rounded bg-muted/40 p-2 text-[10px]">
                      {JSON.stringify(l.results, null, 2)}
                    </pre>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </aside>
    </>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium">{label}</span>
      {children}
    </label>
  );
}
