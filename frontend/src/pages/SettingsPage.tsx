import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import {
  Check,
  CheckCircle2,
  DollarSign,
  Key,
  Loader2,
  Lock,
  Sparkles,
  Star,
  Trash2,
  User,
} from "lucide-react";
import { useAuth } from "@/auth/AuthContext";
import { ApiError } from "@/lib/api";
import {
  SUGGESTED_MODELS,
  SUPPORTED_PROVIDERS,
  aiApi,
  type UserAIKey,
} from "@/lib/ai";
import { cn } from "@/lib/utils";

export function SettingsPage() {
  const { user } = useAuth();
  const [keys, setKeys] = useState<UserAIKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await aiApi.userKeys.list();
      setKeys(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Personal preferences for {user?.email}.
        </p>
      </div>

      <ProfileSection />

      <PasswordSection />

      <CostOptimizationSection />

      <section className="rounded-lg border border-border bg-background">
        <header className="flex items-center justify-between border-b border-border px-5 py-3">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-primary" />
            <h2 className="text-sm font-semibold">AI providers</h2>
          </div>
          <span className="text-[11px] text-muted-foreground">
            Bring your own keys — they override workspace defaults.
          </span>
        </header>

        <div className="divide-y divide-border">
          {error && (
            <div className="px-5 py-3 text-sm text-red-700">{error}</div>
          )}
          {loading ? (
            <div className="px-5 py-6 text-sm text-muted-foreground">
              Loading…
            </div>
          ) : (
            SUPPORTED_PROVIDERS.map((p) => (
              <ProviderRow
                key={p.value}
                provider={p.value}
                providerLabel={p.label}
                row={keys.find((k) => k.provider === p.value)}
                onChanged={refresh}
              />
            ))
          )}
        </div>
      </section>
    </div>
  );
}

function ProfileSection() {
  const { user, updateProfile } = useAuth();
  const [name, setName] = useState(user?.display_name || "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setName(user?.display_name || "");
  }, [user?.display_name]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      await updateProfile({ display_name: name.trim() });
      setSaved(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  const dirty = name.trim() !== (user?.display_name || "");

  return (
    <section className="rounded-lg border border-border bg-background">
      <header className="flex items-center justify-between border-b border-border px-5 py-3">
        <div className="flex items-center gap-2">
          <User className="h-4 w-4 text-primary" />
          <h2 className="text-sm font-semibold">Profile</h2>
        </div>
        <span className="text-[11px] text-muted-foreground">
          {user?.email}
        </span>
      </header>
      <form onSubmit={onSubmit} className="space-y-3 p-5">
        <label className="block">
          <span className="mb-1 block text-xs font-medium">Display name</span>
          <input
            type="text"
            value={name}
            onChange={(e) => {
              setName(e.target.value);
              setSaved(false);
            }}
            className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </label>
        {error && (
          <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
            {error}
          </div>
        )}
        <div className="flex items-center gap-2">
          {saved && !error && (
            <span className="inline-flex items-center gap-1 text-xs text-emerald-700">
              <CheckCircle2 className="h-3 w-3" />
              Saved
            </span>
          )}
          <button
            type="submit"
            disabled={!dirty || busy}
            className="ml-auto flex h-9 items-center gap-1.5 rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-60"
          >
            {busy ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Check className="h-3.5 w-3.5" />
            )}
            Save
          </button>
        </div>
      </form>
    </section>
  );
}

function PasswordSection() {
  const { changePassword } = useAuth();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  function reset() {
    setCurrent("");
    setNext("");
    setConfirmPw("");
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSaved(false);
    if (next.length < 8) {
      setError("New password must be at least 8 characters");
      return;
    }
    if (next !== confirmPw) {
      setError("New passwords do not match");
      return;
    }
    setBusy(true);
    try {
      await changePassword({ current_password: current, new_password: next });
      setSaved(true);
      reset();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Update failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rounded-lg border border-border bg-background">
      <header className="flex items-center gap-2 border-b border-border px-5 py-3">
        <Lock className="h-4 w-4 text-primary" />
        <h2 className="text-sm font-semibold">Password</h2>
      </header>
      <form onSubmit={onSubmit} className="space-y-3 p-5">
        <PwField label="Current password" value={current} onChange={setCurrent} autoComplete="current-password" />
        <PwField label="New password" value={next} onChange={setNext} autoComplete="new-password" hint="At least 8 characters" />
        <PwField label="Confirm new password" value={confirmPw} onChange={setConfirmPw} autoComplete="new-password" />
        {error && (
          <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
            {error}
          </div>
        )}
        <div className="flex items-center gap-2">
          {saved && !error && (
            <span className="inline-flex items-center gap-1 text-xs text-emerald-700">
              <CheckCircle2 className="h-3 w-3" />
              Password updated
            </span>
          )}
          <button
            type="submit"
            disabled={busy || !current || !next || !confirmPw}
            className="ml-auto flex h-9 items-center gap-1.5 rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-60"
          >
            {busy ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Lock className="h-3.5 w-3.5" />
            )}
            Update password
          </button>
        </div>
      </form>
    </section>
  );
}

function PwField({
  label,
  value,
  onChange,
  autoComplete,
  hint,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  autoComplete: string;
  hint?: string;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium">{label}</span>
      <input
        type="password"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        autoComplete={autoComplete}
        className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
      />
      {hint && (
        <span className="mt-1 block text-[10px] text-muted-foreground">
          {hint}
        </span>
      )}
    </label>
  );
}

function ProviderRow({
  provider,
  providerLabel,
  row,
  onChanged,
}: {
  provider: string;
  providerLabel: string;
  row: UserAIKey | undefined;
  onChanged: () => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState(row?.default_model || "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const suggestions = useMemo(
    () => SUGGESTED_MODELS[provider] || [],
    [provider],
  );

  async function save() {
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      const body: { api_key?: string; default_model?: string } = {};
      if (apiKey.trim()) body.api_key = apiKey.trim();
      body.default_model = model.trim();
      if (!row && !body.api_key) {
        setError("API key is required for a new entry");
        return;
      }
      await aiApi.userKeys.upsert(provider, body);
      setSaved(true);
      setApiKey("");
      setEditing(false);
      await onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!confirm(`Remove your ${providerLabel} key?`)) return;
    setBusy(true);
    try {
      await aiApi.userKeys.remove(provider);
      setSaved(false);
      await onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Remove failed");
    } finally {
      setBusy(false);
    }
  }

  async function makeDefault() {
    setBusy(true);
    try {
      await aiApi.userKeys.setDefault(provider);
      await onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="px-5 py-4">
      <div className="flex flex-wrap items-start gap-3">
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-md bg-primary/10 text-primary">
          <Key className="h-4 w-4" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">{providerLabel}</span>
            {row?.is_default && (
              <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-1.5 text-[10px] font-medium text-amber-700">
                <Star className="h-2.5 w-2.5" />
                default
              </span>
            )}
            {saved && !editing && (
              <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-700">
                <CheckCircle2 className="h-3 w-3" />
                Saved
              </span>
            )}
          </div>
          <div className="mt-0.5 text-xs text-muted-foreground">
            {row ? (
              <>
                Key: <span className="font-mono">{row.masked}</span>
                {row.default_model && (
                  <>
                    {" "}
                    · model{" "}
                    <span className="font-mono">{row.default_model}</span>
                  </>
                )}
              </>
            ) : (
              "Not configured"
            )}
          </div>
        </div>
        <div className="flex shrink-0 gap-2">
          {row && !row.is_default && (
            <button
              type="button"
              onClick={() => void makeDefault()}
              disabled={busy}
              className="h-8 rounded-md border border-border px-2 text-xs hover:bg-accent disabled:opacity-60"
            >
              Make default
            </button>
          )}
          <button
            type="button"
            onClick={() => {
              setEditing((e) => !e);
              setError(null);
              setSaved(false);
              setApiKey("");
              setModel(row?.default_model || "");
            }}
            className="h-8 rounded-md border border-border px-3 text-xs font-medium hover:bg-accent"
          >
            {editing ? "Cancel" : row ? "Edit" : "Add key"}
          </button>
          {row && (
            <button
              type="button"
              onClick={() => void remove()}
              disabled={busy}
              aria-label="Remove key"
              className="grid h-8 w-8 place-items-center rounded-md border border-border text-muted-foreground hover:bg-red-50 hover:text-red-600 disabled:opacity-60"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>

      {editing && (
        <div className="mt-3 space-y-2 rounded-md border border-border bg-muted/30 p-3">
          <label className="block">
            <span className="mb-1 block text-xs font-medium">
              API key{" "}
              {row && (
                <span className="font-normal text-muted-foreground">
                  (leave blank to keep existing)
                </span>
              )}
            </span>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="Paste new key"
              autoComplete="off"
              spellCheck={false}
              className="h-8 w-full rounded-md border border-input bg-background px-2 font-mono text-xs focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-medium">
              Default model{" "}
              <span className="font-normal text-muted-foreground">
                (optional)
              </span>
            </span>
            <input
              type="text"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="e.g. claude-sonnet-4-5-20250929"
              list={`models-${provider}`}
              className="h-8 w-full rounded-md border border-input bg-background px-2 font-mono text-xs focus:outline-none focus:ring-2 focus:ring-ring"
            />
            <datalist id={`models-${provider}`}>
              {suggestions.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.label}
                </option>
              ))}
            </datalist>
            {suggestions.length > 0 && (
              <div className="mt-1 flex flex-wrap gap-1">
                {suggestions.map((s) => (
                  <button
                    key={s.id}
                    type="button"
                    onClick={() => setModel(s.id)}
                    className={cn(
                      "rounded-full border px-2 py-0.5 text-[10px]",
                      model === s.id
                        ? "border-primary bg-primary/10 text-primary"
                        : "border-border text-muted-foreground hover:bg-accent",
                    )}
                  >
                    {s.label}
                  </button>
                ))}
              </div>
            )}
          </label>
          {error && (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
              {error}
            </div>
          )}
          <div className="flex justify-end">
            <button
              type="button"
              onClick={() => void save()}
              disabled={busy}
              className="flex h-8 items-center gap-1.5 rounded-md bg-primary px-3 text-xs font-medium text-primary-foreground hover:opacity-90 disabled:opacity-60"
            >
              {busy ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <Check className="h-3 w-3" />
              )}
              Save
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function CostOptimizationSection() {
  const { user } = useAuth();
  const isAdmin = !!user?.is_admin;
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    void aiApi.preferences
      .get()
      .then((p) => {
        if (alive) setEnabled(p.cost_optimization);
      })
      .catch((err) => {
        if (alive)
          setError(
            err instanceof ApiError ? err.message : "Failed to load preferences",
          );
      });
    return () => {
      alive = false;
    };
  }, []);

  async function toggle(next: boolean) {
    if (!isAdmin) return;
    setBusy(true);
    setError(null);
    const prev = enabled;
    setEnabled(next);
    try {
      const res = await aiApi.preferences.update({ cost_optimization: next });
      setEnabled(res.cost_optimization);
    } catch (err) {
      setEnabled(prev);
      setError(err instanceof ApiError ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rounded-lg border border-border bg-background">
      <header className="flex items-center justify-between border-b border-border px-5 py-3">
        <div className="flex items-center gap-2">
          <DollarSign className="h-4 w-4 text-primary" />
          <h2 className="text-sm font-semibold">Cost optimization</h2>
        </div>
        <span className="text-[11px] text-muted-foreground">
          Workspace-wide
        </span>
      </header>
      <div className="flex flex-col gap-3 p-5 sm:flex-row sm:items-start sm:justify-between">
        <div className="max-w-xl">
          <p className="text-sm">
            Auto-route AI calls to the cheapest configured model.
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            When enabled, AI requests that don't pin a specific model will use
            the lowest <code className="rounded bg-muted px-1">cost_tier</code>{" "}
            model on the active provider. Calls that explicitly choose a model
            (e.g. from the Compose AI panel) are unaffected.
          </p>
          {!isAdmin && (
            <p className="mt-2 text-[11px] text-muted-foreground">
              Only admins can change this setting.
            </p>
          )}
          {error && (
            <p className="mt-2 text-xs text-red-700">{error}</p>
          )}
        </div>
        <ToggleSwitch
          checked={!!enabled}
          disabled={!isAdmin || busy || enabled === null}
          onChange={toggle}
          label={enabled ? "Enabled" : "Disabled"}
        />
      </div>
    </section>
  );
}

function ToggleSwitch({
  checked,
  disabled,
  onChange,
  label,
}: {
  checked: boolean;
  disabled?: boolean;
  onChange: (next: boolean) => void;
  label: string;
}) {
  return (
    <label
      className={cn(
        "inline-flex shrink-0 items-center gap-2",
        disabled ? "opacity-60" : "cursor-pointer",
      )}
    >
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cn(
          "relative inline-flex h-6 w-11 items-center rounded-full transition-colors",
          checked ? "bg-primary" : "bg-muted",
          disabled && "cursor-not-allowed",
        )}
      >
        <span
          className={cn(
            "inline-block h-4 w-4 transform rounded-full bg-background shadow transition-transform",
            checked ? "translate-x-6" : "translate-x-1",
          )}
        />
      </button>
    </label>
  );
}
