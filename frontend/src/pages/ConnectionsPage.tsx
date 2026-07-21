import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  CheckCircle2,
  Loader2,
  Plug,
  Settings2,
  XCircle,
} from "lucide-react";
import { useAuth } from "@/auth/AuthContext";
import { ApiError } from "@/lib/api";
import type { PlatformInfo } from "@/lib/compose";
import {
  connectionsApi,
  PLATFORM_GROUPS,
  type OAuthStatus,
} from "@/lib/connections";
import { cn } from "@/lib/utils";

export function ConnectionsPage() {
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();

  const [platforms, setPlatforms] = useState<PlatformInfo[]>([]);
  const [oauth, setOauth] = useState<OAuthStatus>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const justReturned = params.get("oauth") === "ok";

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [p, o] = await Promise.all([
        connectionsApi.platforms(),
        connectionsApi.oauthStatus(),
      ]);
      setPlatforms(p);
      setOauth(o);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // Drop the `?oauth=ok` flag once shown so it doesn't stick around.
  useEffect(() => {
    if (!justReturned) return;
    const t = setTimeout(() => {
      params.delete("oauth");
      setParams(params, { replace: true });
    }, 4000);
    return () => clearTimeout(t);
  }, [justReturned, params, setParams]);

  function platformByName(name: string): PlatformInfo | undefined {
    return platforms.find((p) => p.name === name);
  }

  async function disconnect(name: string) {
    if (!confirm(`Disconnect ${name}?`)) return;
    setBusy(name);
    try {
      await connectionsApi.disconnect(name);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Disconnect failed");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Connections</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Link your social accounts so Kryptams can publish on your behalf.
        </p>
      </div>

      {justReturned && (
        <Notice tone="success">
          Welcome back — connection updated. If a platform still shows
          <em> not connected</em>, the OAuth flow may not have completed.
        </Notice>
      )}

      {error && <Notice tone="error">{error}</Notice>}

      {loading ? (
        <div className="text-sm text-muted-foreground">Loading…</div>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {PLATFORM_GROUPS.map((group) => {
            const credsConfigured = oauth[group.oauth_key] === true;
            return (
              <GroupCard
                key={group.oauth_key}
                group={group}
                credsConfigured={credsConfigured}
                isAdmin={!!user?.is_admin}
                lookup={platformByName}
                busy={busy}
                onDisconnect={disconnect}
                onConfigSaved={refresh}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}

type GroupCardProps = {
  group: (typeof PLATFORM_GROUPS)[number];
  credsConfigured: boolean;
  isAdmin: boolean;
  lookup: (name: string) => PlatformInfo | undefined;
  busy: string | null;
  onDisconnect: (name: string) => void;
  onConfigSaved: () => void;
};

function GroupCard({
  group,
  credsConfigured,
  isAdmin,
  lookup,
  busy,
  onDisconnect,
  onConfigSaved,
}: GroupCardProps) {
  const anyConnected = group.members.some((m) => lookup(m.name)?.connected);
  const primary = group.members[0];
  const isMeta = group.oauth_key === "meta";

  return (
    <div className="rounded-lg border border-border bg-background p-5 shadow-sm">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-base font-semibold capitalize">
              {isMeta ? "Meta" : primary.display_name}
            </h3>
            <ConnectionPill connected={anyConnected} />
          </div>
          {isMeta && (
            <p className="mt-0.5 text-xs text-muted-foreground">
              Connecting Meta links Facebook, Instagram, and WhatsApp together.
            </p>
          )}
        </div>
        <div className="flex shrink-0 gap-2">
          {!credsConfigured ? (
            <CredsMissingButton isAdmin={isAdmin} />
          ) : anyConnected ? (
            <button
              type="button"
              onClick={() => onDisconnect(primary.name)}
              disabled={busy === primary.name}
              className="flex h-8 items-center gap-1.5 rounded-md border border-border px-3 text-xs font-medium text-muted-foreground hover:bg-accent disabled:opacity-60"
            >
              {busy === primary.name ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : null}
              Disconnect
            </button>
          ) : (
            <a
              href={`/oauth/${primary.name}/connect?source=spa`}
              className="flex h-8 items-center gap-1.5 rounded-md bg-primary px-3 text-xs font-medium text-primary-foreground hover:opacity-90"
            >
              <Plug className="h-3 w-3" />
              Connect
            </a>
          )}
        </div>
      </div>

      <ul className="space-y-2">
        {group.members.map((m) => {
          const info = lookup(m.name);
          return (
            <li
              key={m.name}
              className="flex items-start justify-between gap-3 text-sm"
            >
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{m.display_name}</span>
                  {info?.connected ? (
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                  ) : (
                    <XCircle className="h-3.5 w-3.5 text-muted-foreground/60" />
                  )}
                </div>
                {info && (
                  <div className="text-xs text-muted-foreground">
                    {info.post_types.join(" · ")}
                    {info.max_text_length
                      ? ` · ${info.max_text_length} chars`
                      : ""}
                  </div>
                )}
                {info?.connected && m.extra_keys && (
                  <ExtraConfig
                    platform={m.name}
                    keys={m.extra_keys}
                    onSaved={onConfigSaved}
                  />
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function CredsMissingButton({ isAdmin }: { isAdmin: boolean }) {
  if (isAdmin) {
    return (
      <Link
        to="/admin"
        className="flex h-8 items-center gap-1.5 rounded-md border border-amber-300 bg-amber-50 px-3 text-xs font-medium text-amber-900 hover:bg-amber-100"
      >
        <Settings2 className="h-3 w-3" />
        Configure OAuth
      </Link>
    );
  }
  return (
    <span className="flex h-8 items-center rounded-md border border-border px-3 text-xs text-muted-foreground">
      Ask an admin
    </span>
  );
}

function ConnectionPill({ connected }: { connected: boolean }) {
  return (
    <span
      className={cn(
        "rounded-full px-2 py-0.5 text-[10px] font-semibold",
        connected
          ? "bg-emerald-100 text-emerald-700"
          : "bg-muted text-muted-foreground",
      )}
    >
      {connected ? "Connected" : "Not connected"}
    </span>
  );
}

type ExtraKey = { key: string; label: string; hint?: string };

function ExtraConfig({
  platform,
  keys,
  onSaved,
}: {
  platform: string;
  keys: ExtraKey[];
  onSaved: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [values, setValues] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function save() {
    setSaving(true);
    setMsg(null);
    try {
      const body = Object.fromEntries(
        Object.entries(values).filter(([, v]) => v.trim().length > 0),
      );
      if (Object.keys(body).length === 0) {
        setMsg("Enter at least one value");
        return;
      }
      await connectionsApi.saveExtraConfig(platform, body);
      setMsg("Saved");
      onSaved();
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={() => setExpanded((x) => !x)}
        className="text-[11px] font-medium text-primary hover:underline"
      >
        {expanded ? "Hide" : "Configure"}
      </button>
      {expanded && (
        <div className="mt-2 space-y-2 rounded-md border border-border bg-muted/30 p-3">
          {keys.map((k) => (
            <label key={k.key} className="block">
              <span className="block text-[11px] font-medium">{k.label}</span>
              {k.hint && (
                <span className="block text-[10px] text-muted-foreground">
                  {k.hint}
                </span>
              )}
              <input
                type="text"
                value={values[k.key] ?? ""}
                onChange={(e) =>
                  setValues((v) => ({ ...v, [k.key]: e.target.value }))
                }
                className="mt-1 h-7 w-full rounded border border-input bg-background px-2 text-xs focus:outline-none focus:ring-1 focus:ring-ring"
              />
            </label>
          ))}
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => void save()}
              disabled={saving}
              className="h-7 rounded-md bg-primary px-3 text-[11px] font-medium text-primary-foreground hover:opacity-90 disabled:opacity-60"
            >
              {saving ? "Saving…" : "Save"}
            </button>
            {msg && <span className="text-[11px] text-muted-foreground">{msg}</span>}
          </div>
        </div>
      )}
    </div>
  );
}

function Notice({
  tone,
  children,
}: {
  tone: "warn" | "error" | "success";
  children: React.ReactNode;
}) {
  const toneClass = {
    warn: "border-amber-200 bg-amber-50 text-amber-900",
    error: "border-red-200 bg-red-50 text-red-700",
    success: "border-emerald-200 bg-emerald-50 text-emerald-800",
  }[tone];
  return (
    <div className={cn("rounded-md border px-3 py-2 text-sm", toneClass)}>
      {children}
    </div>
  );
}
