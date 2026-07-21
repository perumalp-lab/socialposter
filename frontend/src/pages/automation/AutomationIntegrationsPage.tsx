import { useCallback, useEffect, useState } from "react";
import { ExternalLink, Eye, EyeOff, Loader2, Save, Zap } from "lucide-react";
import { ApiError } from "@/lib/api";
import {
  integrationsApi,
  type IntegrationSettings,
} from "@/lib/integrations";

export function AutomationIntegrationsPage() {
  const [settings, setSettings] = useState<IntegrationSettings>({
    zapier_api_key: "",
    pabbly_api_key: "",
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [showZapier, setShowZapier] = useState(false);
  const [showPabbly, setShowPabbly] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const s = await integrationsApi.getSettings();
      setSettings(s);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function save() {
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const updated = await integrationsApi.updateSettings(settings);
      setSettings(updated);
      setSuccess("Settings saved");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <div className="text-sm text-muted-foreground">Loading...</div>;
  }

  return (
    <div className="space-y-8">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            Platform Integrations
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Connect external platforms to extend your automation workflows.
          </p>
        </div>
      </div>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}
      {success && (
        <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
          {success}
        </div>
      )}

      <section className="rounded-lg border border-border bg-background p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="flex items-center gap-2 text-base font-semibold">
              <Zap className="h-4 w-4 text-orange-500" />
              Zapier
            </h2>
            <p className="mt-1 text-xs text-muted-foreground">
              Connect your Zapier account to trigger automations from thousands
              of apps.
            </p>
          </div>
          <a
            href="https://zapier.com/apps"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 rounded-md border border-input px-3 py-1.5 text-xs font-medium hover:bg-accent"
          >
            Click Here to use our zapier app.
            <ExternalLink className="h-3 w-3" />
          </a>
        </div>
        <div className="mt-4">
          <Field label="Zapier API Key">
            <div className="relative max-w-md">
              <input
                type={showZapier ? "text" : "password"}
                value={settings.zapier_api_key}
                onChange={(e) =>
                  setSettings({ ...settings, zapier_api_key: e.target.value })
                }
                placeholder="Enter your Zapier API key"
                className="h-9 w-full rounded-md border border-input bg-background pr-9 pl-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
              <button
                type="button"
                onClick={() => setShowZapier(!showZapier)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                aria-label={showZapier ? "Hide key" : "Show key"}
              >
                {showZapier ? (
                  <EyeOff className="h-4 w-4" />
                ) : (
                  <Eye className="h-4 w-4" />
                )}
              </button>
            </div>
          </Field>
        </div>
      </section>

      <section className="rounded-lg border border-border bg-background p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="flex items-center gap-2 text-base font-semibold">
              <Zap className="h-4 w-4 text-purple-500" />
              Pabbly Connect
            </h2>
            <p className="mt-1 text-xs text-muted-foreground">
              Integrate with Pabbly Connect to build advanced automation
              workflows.
            </p>
          </div>
          <a
            href="https://www.pabbly.com/connect/"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 rounded-md border border-input px-3 py-1.5 text-xs font-medium hover:bg-accent"
          >
            Click Here to use our pabbly app.
            <ExternalLink className="h-3 w-3" />
          </a>
        </div>
        <div className="mt-4">
          <Field label="Pabbly API Key">
            <div className="relative max-w-md">
              <input
                type={showPabbly ? "text" : "password"}
                value={settings.pabbly_api_key}
                onChange={(e) =>
                  setSettings({ ...settings, pabbly_api_key: e.target.value })
                }
                placeholder="Enter your Pabbly API key"
                className="h-9 w-full rounded-md border border-input bg-background pr-9 pl-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
              <button
                type="button"
                onClick={() => setShowPabbly(!showPabbly)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                aria-label={showPabbly ? "Hide key" : "Show key"}
              >
                {showPabbly ? (
                  <EyeOff className="h-4 w-4" />
                ) : (
                  <Eye className="h-4 w-4" />
                )}
              </button>
            </div>
          </Field>
        </div>
      </section>

      <button
        type="button"
        onClick={() => void save()}
        disabled={saving}
        className="flex h-9 items-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-60"
      >
        {saving ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Save className="h-4 w-4" />
        )}
        Save Settings
      </button>
    </div>
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
