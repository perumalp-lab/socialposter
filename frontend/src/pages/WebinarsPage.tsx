import { useCallback, useEffect, useState } from "react";
import {
  ArrowUpRight,
  Globe,
  Loader2,
  Mail,
  Pencil,
  Plus,
  Send,
  Trash2,
  UserPlus,
  Video,
  X,
} from "lucide-react";
import { ApiError } from "@/lib/api";
import { webinarsApi, type Webinar, type WebinarInput } from "@/lib/webinars";

const PLATFORM_TYPES = ["zoom", "google_meet", "teams", "webex", "custom"];
const STATUS_OPTIONS = ["draft", "scheduled", "completed", "cancelled"];

const TIMEZONES = [
  "UTC",
  "America/New_York",
  "America/Chicago",
  "America/Denver",
  "America/Los_Angeles",
  "America/Anchorage",
  "Pacific/Honolulu",
  "Europe/London",
  "Europe/Paris",
  "Europe/Berlin",
  "Europe/Moscow",
  "Asia/Dubai",
  "Asia/Kolkata",
  "Asia/Shanghai",
  "Asia/Tokyo",
  "Asia/Seoul",
  "Australia/Sydney",
  "Pacific/Auckland",
];

const emptyForm: WebinarInput = {
  title: "",
  description: "",
  scheduled_at: "",
  duration_minutes: 60,
  platform_type: "zoom",
  meeting_url: "",
  registration_url: "",
  recording_url: "",
  host_name: "",
  target_audience: "",
  timezone: "UTC",
  tags: [],
  max_attendees: null,
  status: "draft",
};

export function WebinarsPage() {
  const [items, setItems] = useState<Webinar[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<Webinar | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<WebinarInput>(emptyForm);
  const [saving, setSaving] = useState(false);
  const [attendeeEmail, setAttendeeEmail] = useState<Record<number, string>>({});
  const [sendingInvites, setSendingInvites] = useState<Record<number, boolean>>({});
  const [inviteResults, setInviteResults] = useState<Record<number, { success_count: number; error_count: number } | null>>({});

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await webinarsApi.list();
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

  function openCreate() {
    setForm(emptyForm);
    setEditing(null);
    setShowForm(true);
  }

  function openEdit(w: Webinar) {
    setForm({
      title: w.title,
      description: w.description,
      scheduled_at: w.scheduled_at ? w.scheduled_at.slice(0, 16) : "",
      duration_minutes: w.duration_minutes,
      platform_type: w.platform_type,
      meeting_url: w.meeting_url,
      registration_url: w.registration_url,
      recording_url: w.recording_url,
      host_name: w.host_name,
      target_audience: w.target_audience,
      timezone: w.timezone,
      tags: w.tags,
      max_attendees: w.max_attendees,
      status: w.status,
    });
    setEditing(w);
    setShowForm(true);
  }

  async function save() {
    if (!form.title.trim()) return;
    setSaving(true);
    setError(null);
    try {
      if (editing) {
        const updated = await webinarsApi.update(editing.id, form);
        setItems((curr) =>
          curr.map((w) => (w.id === updated.id ? updated : w)),
        );
      } else {
        const created = await webinarsApi.create(form);
        setItems((curr) => [created, ...curr]);
      }
      setShowForm(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function remove(w: Webinar) {
    if (!confirm(`Delete webinar "${w.title}"?`)) return;
    setError(null);
    try {
      await webinarsApi.remove(w.id);
      setItems((curr) => curr.filter((x) => x.id !== w.id));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Delete failed");
    }
  }

  const statusBadge = (s: string) => {
    const colors: Record<string, string> = {
      draft: "bg-muted text-muted-foreground",
      scheduled: "bg-blue-100 text-blue-700",
      completed: "bg-emerald-100 text-emerald-700",
      cancelled: "bg-red-100 text-red-700",
    };
    return (
      <span
        className={`rounded-full px-2 py-0.5 text-[10px] font-semibold capitalize ${colors[s] || colors.draft}`}
      >
        {s}
      </span>
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Webinars</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Create and manage your live online events.
          </p>
        </div>
        <button
          type="button"
          onClick={openCreate}
          className="flex h-9 items-center gap-2 rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground hover:opacity-90"
        >
          <Plus className="h-4 w-4" />
          New webinar
        </button>
      </div>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      {showForm && (
        <div className="rounded-lg border border-border bg-background p-5">
          <h2 className="mb-4 text-base font-semibold">
            {editing ? "Edit webinar" : "Create webinar"}
          </h2>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <Field label="Title" className="md:col-span-2">
              <input
                type="text"
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                placeholder="Webinar title"
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </Field>
            <Field label="Status">
              <select
                value={form.status}
                onChange={(e) => setForm({ ...form, status: e.target.value })}
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              >
                {STATUS_OPTIONS.map((s) => (
                  <option key={s} value={s}>
                    {s.charAt(0).toUpperCase() + s.slice(1)}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Description" className="md:col-span-3">
              <textarea
                value={form.description}
                onChange={(e) =>
                  setForm({ ...form, description: e.target.value })
                }
                rows={3}
                placeholder="What is this webinar about?"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </Field>
            <Field label="Scheduled at">
              <input
                type="datetime-local"
                value={form.scheduled_at || ""}
                onChange={(e) =>
                  setForm({ ...form, scheduled_at: e.target.value || "" })
                }
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </Field>
            <Field label="Timezone">
              <select
                value={form.timezone}
                onChange={(e) =>
                  setForm({ ...form, timezone: e.target.value })
                }
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              >
                {TIMEZONES.map((tz) => (
                  <option key={tz} value={tz}>
                    {tz.replace(/_/g, " ")}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Duration (minutes)">
              <input
                type="number"
                min={5}
                value={form.duration_minutes}
                onChange={(e) =>
                  setForm({
                    ...form,
                    duration_minutes: parseInt(e.target.value) || 60,
                  })
                }
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </Field>
            <Field label="Host name">
              <input
                type="text"
                value={form.host_name}
                onChange={(e) => setForm({ ...form, host_name: e.target.value })}
                placeholder="Presenter name"
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </Field>
            <Field label="Platform">
              <select
                value={form.platform_type}
                onChange={(e) =>
                  setForm({ ...form, platform_type: e.target.value })
                }
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              >
                {PLATFORM_TYPES.map((p) => (
                  <option key={p} value={p}>
                    {p.replace("_", " ")}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Max attendees">
              <input
                type="number"
                min={1}
                value={form.max_attendees ?? ""}
                onChange={(e) =>
                  setForm({
                    ...form,
                    max_attendees: e.target.value ? parseInt(e.target.value) : null,
                  })
                }
                placeholder="Unlimited"
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </Field>
            <Field label="Target audience" className="md:col-span-2">
              <input
                type="text"
                value={form.target_audience}
                onChange={(e) =>
                  setForm({ ...form, target_audience: e.target.value })
                }
                placeholder="e.g. Marketing team"
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </Field>
            <Field label="Tags" className="md:col-span-3">
              <input
                type="text"
                value={form.tags?.join(", ") ?? ""}
                onChange={(e) =>
                  setForm({
                    ...form,
                    tags: e.target.value
                      ? e.target.value.split(",").map((t) => t.trim()).filter(Boolean)
                      : [],
                  })
                }
                placeholder="e.g. product-launch, q1-2026, sales (comma-separated)"
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </Field>
            <Field label="Meeting URL" className="md:col-span-3">
              <input
                type="url"
                value={form.meeting_url}
                onChange={(e) =>
                  setForm({ ...form, meeting_url: e.target.value })
                }
                placeholder="https://zoom.us/j/..."
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </Field>
            <Field label="Registration URL" className="md:col-span-3">
              <input
                type="url"
                value={form.registration_url}
                onChange={(e) =>
                  setForm({ ...form, registration_url: e.target.value })
                }
                placeholder="https://zoom.us/meeting/register/..."
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </Field>
            <Field label="Recording URL" className="md:col-span-3">
              <input
                type="url"
                value={form.recording_url}
                onChange={(e) =>
                  setForm({ ...form, recording_url: e.target.value })
                }
                placeholder="https://zoom.us/rec/share/..."
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </Field>
          </div>
          <div className="mt-4 flex items-center gap-2">
            <button
              type="button"
              onClick={save}
              disabled={saving || !form.title.trim()}
              className="flex h-9 items-center gap-1.5 rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-60"
            >
              {saving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              {editing ? "Update" : "Create"}
            </button>
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="h-9 rounded-md px-3 text-sm hover:bg-accent"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="text-sm text-muted-foreground">Loading...</div>
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border bg-background py-16 text-center">
          <Video className="h-8 w-8 text-muted-foreground" />
          <p className="mt-3 text-sm font-medium">No webinars yet</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Create your first webinar to start managing events.
          </p>
          <button
            type="button"
            onClick={openCreate}
            className="mt-4 flex h-9 items-center gap-2 rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground hover:opacity-90"
          >
            <Plus className="h-4 w-4" />
            Create your first webinar
          </button>
        </div>
      ) : (
        <ul className="space-y-3">
          {items.map((w) => (
            <li
              key={w.id}
              className="flex items-start gap-4 rounded-lg border border-border bg-background p-4"
            >
              <div className="grid h-9 w-9 shrink-0 place-items-center rounded-md bg-primary/10 text-primary">
                <Video className="h-4 w-4" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="truncate text-sm font-semibold">
                    {w.title}
                  </span>
                  {statusBadge(w.status)}
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                  {w.scheduled_at && (
                    <span>
                      {new Date(w.scheduled_at).toLocaleString()}
                    </span>
                  )}
                  {w.timezone && w.timezone !== "UTC" && (
                    <span>{w.timezone.replace(/_/g, " ")}</span>
                  )}
                  <span>{w.duration_minutes} min</span>
                  {w.platform_type && (
                    <span className="inline-flex items-center gap-1 capitalize">
                      <Globe className="h-3 w-3" />
                      {w.platform_type.replace("_", " ")}
                    </span>
                  )}
                  {w.host_name && <span>Host: {w.host_name}</span>}
                  {w.target_audience && (
                    <span>Audience: {w.target_audience}</span>
                  )}
                  {w.max_attendees && (
                    <span>Max: {w.max_attendees}</span>
                  )}
                </div>
                {w.tags.length > 0 && (
                  <div className="mt-1 flex flex-wrap gap-1">
                    {w.tags.map((tag, i) => (
                      <span
                        key={i}
                        className="rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
                {w.description && (
                  <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">
                    {w.description}
                  </p>
                )}
                <div className="mt-1 flex flex-wrap items-center gap-3 text-xs">
                  {w.meeting_url && (
                    <a
                      href={w.meeting_url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 text-primary hover:underline"
                    >
                      Join <ArrowUpRight className="h-3 w-3" />
                    </a>
                  )}
                  {w.registration_url && (
                    <a
                      href={w.registration_url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 text-primary hover:underline"
                    >
                      Register <ArrowUpRight className="h-3 w-3" />
                    </a>
                  )}
                  {w.recording_url && (
                    <a
                      href={w.recording_url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 text-primary hover:underline"
                    >
                      Recording <ArrowUpRight className="h-3 w-3" />
                    </a>
                  )}
                </div>

                {inviteResults[w.id] && (
                  <div className="mt-2 text-xs text-muted-foreground">
                    Sent to {inviteResults[w.id]!.success_count} attendee
                    {inviteResults[w.id]!.success_count !== 1 ? "s" : ""}
                    {inviteResults[w.id]!.error_count > 0 &&
                      ` (${inviteResults[w.id]!.error_count} failed)`}
                  </div>
                )}

                {w.attendees.length > 0 && (
                  <div className="mt-2 space-y-1">
                    <span className="text-[10px] font-semibold uppercase text-muted-foreground">
                      Attendees ({w.attendees.length})
                    </span>
                    {w.attendees.map((a, i) => (
                      <div
                        key={i}
                        className="flex items-center gap-2 text-xs text-muted-foreground"
                      >
                        <Mail className="h-3 w-3 shrink-0" />
                        <span className="truncate">
                          {a.name ? `${a.name} <${a.email}>` : a.email}
                        </span>
                        <button
                          type="button"
                          onClick={async () => {
                            const updated = await webinarsApi.update(w.id, {
                              attendees: w.attendees.filter((_, j) => j !== i),
                            });
                            setItems((curr) =>
                              curr.map((x) => (x.id === w.id ? updated : x)),
                            );
                          }}
                          className="ml-auto shrink-0 text-muted-foreground hover:text-red-600"
                          aria-label="Remove attendee"
                        >
                          <X className="h-3 w-3" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                <div className="mt-2 flex items-center gap-2">
                  <input
                    type="email"
                    value={attendeeEmail[w.id] || ""}
                    onChange={(e) =>
                      setAttendeeEmail((prev) => ({
                        ...prev,
                        [w.id]: e.target.value,
                      }))
                    }
                    placeholder="attendee@example.com"
                    className="h-7 w-48 rounded-md border border-input bg-background px-2 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                  <button
                    type="button"
                    disabled={!attendeeEmail[w.id]?.trim()}
                    onClick={async () => {
                      const email = attendeeEmail[w.id]?.trim();
                      if (!email) return;
                      const updated = await webinarsApi.update(w.id, {
                        attendees: [...w.attendees, { email }],
                      });
                      setItems((curr) =>
                        curr.map((x) => (x.id === w.id ? updated : x)),
                      );
                      setAttendeeEmail((prev) => ({ ...prev, [w.id]: "" }));
                    }}
                    className="flex h-7 items-center gap-1 rounded-md bg-primary px-2 text-[11px] font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
                  >
                    <UserPlus className="h-3 w-3" />
                    Add
                  </button>
                  <button
                    type="button"
                    disabled={
                      w.attendees.length === 0 ||
                      !!w.invitations_sent_at ||
                      sendingInvites[w.id]
                    }
                    onClick={async () => {
                      setSendingInvites((prev) => ({ ...prev, [w.id]: true }));
                      setInviteResults((prev) => ({ ...prev, [w.id]: null }));
                      try {
                        const result = await webinarsApi.sendInvitations(w.id);
                        setItems((curr) =>
                          curr.map((x) =>
                            x.id === w.id
                              ? { ...x, invitations_sent_at: result.invitations_sent_at }
                              : x,
                          ),
                        );
                        setInviteResults((prev) => ({
                          ...prev,
                          [w.id]: {
                            success_count: result.success_count,
                            error_count: result.error_count,
                          },
                        }));
                        if (result.error_count > 0) {
                          setError(`${result.error_count} invitation(s) failed to send. Check email settings.`);
                        }
                      } catch (err) {
                        setError(
                          err instanceof ApiError
                            ? err.message
                            : "Failed to send invitations",
                        );
                      } finally {
                        setSendingInvites((prev) => ({
                          ...prev,
                          [w.id]: false,
                        }));
                      }
                    }}
                    className="flex h-7 items-center gap-1 rounded-md border border-input px-2 text-[11px] font-medium hover:bg-accent disabled:opacity-50"
                  >
                    {w.invitations_sent_at ? (
                      <>Sent</>
                    ) : sendingInvites[w.id] ? (
                      <Loader2 className="h-3 w-3 animate-spin" />
                    ) : (
                      <Send className="h-3 w-3" />
                    )}
                  </button>
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-1">
                <button
                  type="button"
                  onClick={() => openEdit(w)}
                  aria-label="Edit"
                  className="grid h-8 w-8 place-items-center rounded-md text-muted-foreground hover:bg-accent"
                >
                  <Pencil className="h-3.5 w-3.5" />
                </button>
                <button
                  type="button"
                  onClick={() => remove(w)}
                  aria-label="Delete"
                  className="grid h-8 w-8 place-items-center rounded-md text-muted-foreground hover:bg-red-50 hover:text-red-600"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Field({
  label,
  children,
  className,
}: {
  label: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <label className={`block ${className || ""}`}>
      <span className="mb-1 block text-xs font-medium">{label}</span>
      {children}
    </label>
  );
}
