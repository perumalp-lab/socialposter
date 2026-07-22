import { useCallback, useEffect, useState } from "react";
import {
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  History,
  Lock,
  Save,
  ShieldAlert,
  Shield,
  Webhook,
  XCircle,
} from "lucide-react";
import { useAuth } from "@/auth/AuthContext";
import { ApiError } from "@/lib/api";
import {
  adminApi,
  type ActivityLogEntry,
  type ActivityLogPage,
  type AdminSettings,
  type SettingField,
  type WebhookEventEntry,
  type WebhookEventPage,
} from "@/lib/admin";
import { cn } from "@/lib/utils";
import { PlatformBadge } from "@/components/PlatformBadge";

export function AdminPage() {
  const { user } = useAuth();
  const [settings, setSettings] = useState<AdminSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedKeys, setSavedKeys] = useState<string[] | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await adminApi.get();
      setSettings(data);
      setDrafts({});
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load settings");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user?.is_admin) void refresh();
    else setLoading(false);
  }, [refresh, user?.is_admin]);

  if (!user?.is_admin) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Admin</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Workspace settings and integrations.
          </p>
        </div>
        <div className="flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
          <div>
            <div className="font-medium">Admin access required</div>
            <div className="mt-0.5 text-amber-800">
              You're signed in as a regular user. Ask your workspace admin to
              configure OAuth credentials.
            </div>
          </div>
        </div>
      </div>
    );
  }

  async function save() {
    if (Object.keys(drafts).length === 0) return;
    setSaving(true);
    setError(null);
    setSavedKeys(null);
    try {
      const res = await adminApi.update(drafts);
      setSavedKeys(res.updated);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  function setDraft(key: string, value: string) {
    setDrafts((d) => ({ ...d, [key]: value }));
    setSavedKeys(null);
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Admin</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          OAuth credentials, AI providers, and workspace integrations.
        </p>
      </div>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      {savedKeys && (
        <div className="flex items-start gap-2 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
          <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
          <span>
            Saved {savedKeys.length}{" "}
            {savedKeys.length === 1 ? "setting" : "settings"}.
          </span>
        </div>
      )}

      {loading || !settings ? (
        <div className="text-sm text-muted-foreground">Loading…</div>
      ) : (
        <>
          <Section
            title="OAuth credentials"
            description="Client IDs and secrets from each platform's developer console."
            fields={settings.oauth}
            drafts={drafts}
            onChange={setDraft}
          />
          <Section
            title="AI providers"
            description="API keys for AI-assisted post generation. ai_provider should be 'claude' or 'openai'."
            fields={settings.ai}
            drafts={drafts}
            onChange={setDraft}
          />
          <Section
            title="Billing (Stripe)"
            description="Stripe API keys and the Pro plan price ID. The webhook secret comes from your Stripe webhook endpoint configuration."
            fields={settings.billing}
            drafts={drafts}
            onChange={setDraft}
          />

          <div className="sticky bottom-4 flex justify-end">
            <button
              type="button"
              onClick={() => void save()}
              disabled={saving || Object.keys(drafts).length === 0}
              className="flex h-10 items-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground shadow hover:opacity-90 disabled:opacity-60"
            >
              <Save className="h-4 w-4" />
              {saving
                ? "Saving…"
                : Object.keys(drafts).length === 0
                  ? "No changes"
                  : `Save ${Object.keys(drafts).length} change${Object.keys(drafts).length === 1 ? "" : "s"}`}
            </button>
          </div>

          <WebhookSection />

          <ActivityLogSection />
        </>
      )}
    </div>
  );
}

function WebhookSection() {
  const [data, setData] = useState<WebhookEventPage | null>(null);
  const [page, setPage] = useState(1);
  const [platform, setPlatform] = useState("");
  const [verified, setVerified] = useState<"" | "true" | "false">("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await adminApi.webhooks({
        page,
        platform: platform || undefined,
        verified:
          verified === "true" ? true : verified === "false" ? false : "",
      });
      setData(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load webhooks");
    } finally {
      setLoading(false);
    }
  }, [page, platform, verified]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    setPage(1);
  }, [platform, verified]);

  const platforms = ["meta", "facebook", "instagram", "whatsapp", "linkedin", "twitter", "youtube"];
  const baseUrl =
    typeof window !== "undefined"
      ? `${window.location.origin}/api/webhooks/<platform>`
      : "/api/webhooks/<platform>";

  return (
    <section className="rounded-lg border border-border bg-background">
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-5 py-3">
        <div className="flex items-center gap-2">
          <Webhook className="h-4 w-4 text-primary" />
          <div>
            <h2 className="text-sm font-semibold">Webhooks</h2>
            <p className="text-xs text-muted-foreground">
              Inbound events from connected platforms.
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={platform}
            onChange={(e) => setPlatform(e.target.value)}
            className="h-8 rounded-md border border-input bg-background px-2 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="">All platforms</option>
            {platforms.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
          <select
            value={verified}
            onChange={(e) =>
              setVerified(e.target.value as "" | "true" | "false")
            }
            className="h-8 rounded-md border border-input bg-background px-2 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="">All</option>
            <option value="true">Verified</option>
            <option value="false">Unverified</option>
          </select>
        </div>
      </header>

      <div className="space-y-3 p-5">
        <div className="rounded-md border border-border bg-muted/20 p-3 text-xs text-muted-foreground">
          <div className="mb-1 font-medium text-foreground">Webhook URL</div>
          <code className="block break-all rounded bg-background px-2 py-1 font-mono text-[11px]">
            {baseUrl}
          </code>
          <p className="mt-2">
            Replace <code>&lt;platform&gt;</code> with one of:{" "}
            {platforms.map((p, i) => (
              <span key={p}>
                <code>{p}</code>
                {i < platforms.length - 1 ? ", " : ""}
              </span>
            ))}
            . Meta verification uses <code>meta_client_secret</code>; Twitter
            CRC uses <code>twitter_client_secret</code>.
          </p>
        </div>

        {error && (
          <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        )}

        {loading && !data ? (
          <div className="py-6 text-center text-sm text-muted-foreground">
            Loading…
          </div>
        ) : !data || data.items.length === 0 ? (
          <div className="py-8 text-center text-sm text-muted-foreground">
            No webhook events received yet. Send a test event to the URL above
            to see it here.
          </div>
        ) : (
          <>
            <ul className="divide-y divide-border">
              {data.items.map((item) => (
                <WebhookRow key={item.id} item={item} />
              ))}
            </ul>
            {data.pages > 1 && (
              <div className="mt-3 flex items-center justify-end gap-2 text-sm">
                <button
                  type="button"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                  className="grid h-8 w-8 place-items-center rounded-md hover:bg-accent disabled:opacity-40"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <span className="text-muted-foreground">
                  Page {data.page} of {data.pages} · {data.total} events
                </span>
                <button
                  type="button"
                  disabled={page >= data.pages}
                  onClick={() => setPage((p) => p + 1)}
                  className="grid h-8 w-8 place-items-center rounded-md hover:bg-accent disabled:opacity-40"
                >
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </section>
  );
}

function WebhookRow({ item }: { item: WebhookEventEntry }) {
  return (
    <li className="space-y-1 py-2.5 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <PlatformBadge platform={item.platform} />
        {item.event_type && (
          <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-[11px]">
            {item.event_type}
          </code>
        )}
        {item.verified ? (
          <span
            className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-700"
            title="HMAC signature validated"
          >
            <Shield className="h-3 w-3" />
            verified
          </span>
        ) : (
          <span
            className="inline-flex items-center gap-1 text-[11px] font-medium text-amber-700"
            title="No valid signature — may be unsigned or app secret missing"
          >
            <XCircle className="h-3 w-3" />
            unverified
          </span>
        )}
        {item.error && (
          <span className="text-[11px] text-red-700">err: {item.error}</span>
        )}
        <span className="ml-auto text-[11px] text-muted-foreground">
          {item.created_at ? new Date(item.created_at).toLocaleString() : "—"}
        </span>
      </div>
      {item.payload_summary && (
        <pre className="overflow-x-auto rounded bg-muted/40 px-2 py-1 font-mono text-[11px] text-muted-foreground">
          {item.payload_summary}
        </pre>
      )}
    </li>
  );
}

function ActivityLogSection() {
  const [data, setData] = useState<ActivityLogPage | null>(null);
  const [page, setPage] = useState(1);
  const [actionFilter, setActionFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await adminApi.activity({
        page,
        action: actionFilter || undefined,
      });
      setData(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load activity");
    } finally {
      setLoading(false);
    }
  }, [page, actionFilter]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // Reset to page 1 on filter change.
  useEffect(() => {
    setPage(1);
  }, [actionFilter]);

  const knownActions = [
    "auth.login",
    "draft.create",
    "draft.submit",
    "draft.approve",
    "draft.reject",
    "draft.publish",
    "draft.delete",
    "draft.bulk_import",
    "schedule.create",
    "schedule.delete",
    "connection.disconnect",
  ];

  return (
    <section className="rounded-lg border border-border bg-background">
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-5 py-3">
        <div className="flex items-center gap-2">
          <History className="h-4 w-4 text-primary" />
          <div>
            <h2 className="text-sm font-semibold">Activity log</h2>
            <p className="text-xs text-muted-foreground">
              Audit trail of significant actions across the workspace.
            </p>
          </div>
        </div>
        <select
          value={actionFilter}
          onChange={(e) => setActionFilter(e.target.value)}
          className="h-8 rounded-md border border-input bg-background px-2 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="">All actions</option>
          {knownActions.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </select>
      </header>

      <div className="p-5">
        {error && (
          <div className="mb-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        )}

        {loading && !data ? (
          <div className="py-6 text-center text-sm text-muted-foreground">
            Loading…
          </div>
        ) : !data || data.items.length === 0 ? (
          <div className="py-8 text-center text-sm text-muted-foreground">
            No activity yet. Logs accumulate as users post, approve, or
            connect platforms.
          </div>
        ) : (
          <>
            <ul className="divide-y divide-border">
              {data.items.map((item) => (
                <ActivityRow key={item.id} item={item} />
              ))}
            </ul>
            {data.pages > 1 && (
              <div className="mt-3 flex items-center justify-end gap-2 text-sm">
                <button
                  type="button"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                  className="grid h-8 w-8 place-items-center rounded-md hover:bg-accent disabled:opacity-40"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <span className="text-muted-foreground">
                  Page {data.page} of {data.pages} · {data.total} entries
                </span>
                <button
                  type="button"
                  disabled={page >= data.pages}
                  onClick={() => setPage((p) => p + 1)}
                  className="grid h-8 w-8 place-items-center rounded-md hover:bg-accent disabled:opacity-40"
                >
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </section>
  );
}

function ActivityRow({ item }: { item: ActivityLogEntry }) {
  const detailsText = formatDetails(item.details);
  const actor = item.user_email || (item.user_id ? `user #${item.user_id}` : "system");
  return (
    <li className="flex items-start gap-3 py-2.5 text-sm">
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-[11px]">
            {item.action}
          </code>
          <span className="text-xs text-muted-foreground">{actor}</span>
          {item.target_type && (
            <span className="text-[11px] text-muted-foreground">
              · {item.target_type}
              {item.target_id ? ` ${item.target_id}` : ""}
            </span>
          )}
        </div>
        {detailsText && (
          <div className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">
            {detailsText}
          </div>
        )}
      </div>
      <div className="shrink-0 text-[11px] text-muted-foreground">
        {item.created_at ? new Date(item.created_at).toLocaleString() : "—"}
      </div>
    </li>
  );
}

function formatDetails(details: Record<string, unknown>): string {
  const entries = Object.entries(details);
  if (entries.length === 0) return "";
  return entries
    .map(([k, v]) => {
      if (Array.isArray(v)) return `${k}=${v.join(",")}`;
      if (typeof v === "object" && v !== null) return `${k}=${JSON.stringify(v)}`;
      return `${k}=${String(v)}`;
    })
    .join(" · ");
}

function Section({
  title,
  description,
  fields,
  drafts,
  onChange,
}: {
  title: string;
  description: string;
  fields: Record<string, SettingField>;
  drafts: Record<string, string>;
  onChange: (key: string, value: string) => void;
}) {
  const entries = Object.entries(fields);
  return (
    <section className="rounded-lg border border-border bg-background p-5">
      <header className="mb-4">
        <h2 className="text-base font-semibold">{title}</h2>
        <p className="mt-0.5 text-sm text-muted-foreground">{description}</p>
      </header>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {entries.map(([key, field]) => (
          <FieldRow
            key={key}
            field={field}
            draft={drafts[key]}
            onChange={(v) => onChange(key, v)}
          />
        ))}
      </div>
    </section>
  );
}

function FieldRow({
  field,
  draft,
  onChange,
}: {
  field: SettingField;
  draft: string | undefined;
  onChange: (value: string) => void;
}) {
  const dirty = draft !== undefined;
  const hasValue = field.set && draft === undefined;

  return (
    <label className="block">
      <div className="mb-1 flex items-center gap-2">
        <span className="text-xs font-medium">{field.label}</span>
        {field.set && !dirty && (
          <span className="inline-flex h-4 items-center gap-1 rounded-full bg-emerald-100 px-1.5 text-[9px] font-semibold text-emerald-700">
            <Lock className="h-2.5 w-2.5" />
            saved
          </span>
        )}
        {dirty && (
          <span className="rounded-full bg-amber-100 px-1.5 text-[9px] font-semibold text-amber-700">
            modified
          </span>
        )}
      </div>
      {field.hint && (
        <p className="mb-1 text-[11px] text-muted-foreground">{field.hint}</p>
      )}
      <input
        type="text"
        value={draft ?? (hasValue ? field.masked || "" : "")}
        placeholder={hasValue ? "Type new value to overwrite" : "Enter value"}
        onChange={(e) => onChange(e.target.value)}
        className={cn(
          "h-9 w-full rounded-md border border-input bg-background px-3 text-sm",
          "focus:outline-none focus:ring-2 focus:ring-ring",
          dirty && "border-amber-300 ring-1 ring-amber-300",
        )}
      />
    </label>
  );
}
