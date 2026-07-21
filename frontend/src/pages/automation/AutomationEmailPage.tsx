import { useCallback, useEffect, useState } from "react";
import {
  CheckCircle2,
  Eye,
  EyeOff,
  Loader2,
  Save,
  Send,
  ToggleLeft,
  ToggleRight,
  Wifi,
  XCircle,
} from "lucide-react";
import { ApiError } from "@/lib/api";
import { emailApi, type EmailSettings, type EmailTemplate } from "@/lib/email";

export function AutomationEmailPage() {
  const [settings, setSettings] = useState<EmailSettings>({
    from_name: "",
    from_email: "",
    reply_to_email: "",
    smtp_host: "",
    smtp_port: 587,
    smtp_username: "",
    smtp_has_password: false,
  });
  const [smtpPassword, setSmtpPassword] = useState("");
  const [templates, setTemplates] = useState<EmailTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [testingConn, setTestingConn] = useState(false);
  const [connResult, setConnResult] = useState<"idle" | "ok" | "fail">("idle");
  const [testingId, setTestingId] = useState<number | null>(null);
  const [showPw, setShowPw] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, t] = await Promise.all([
        emailApi.getSettings(),
        emailApi.listTemplates(),
      ]);
      setSettings(s);
      setTemplates(t);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function saveSettings() {
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const payload: Record<string, unknown> = { ...settings };
      if (smtpPassword) payload.smtp_password = smtpPassword;
      const updated = await emailApi.updateSettings(payload);
      setSettings(updated);
      setSmtpPassword("");
      setSuccess("Settings saved");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function testConnection() {
    setTestingConn(true);
    setConnResult("idle");
    setError(null);
    try {
      const r = await emailApi.testConnection();
      setConnResult(r.ok ? "ok" : "fail");
      if (!r.ok) setError(r.error || "Connection failed");
    } catch (err) {
      setConnResult("fail");
      setError(err instanceof ApiError ? err.message : "Connection test failed");
    } finally {
      setTestingConn(false);
    }
  }

  async function sendTest(t: EmailTemplate) {
    setTestingId(t.id);
    setError(null);
    setSuccess(null);
    try {
      const r = await emailApi.sendTest(t.id);
      if (r.ok) {
        setSuccess(`Test email sent for "${t.name}"`);
      } else {
        setError(r.error || "Send failed");
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Send failed");
    } finally {
      setTestingId(null);
    }
  }

  async function toggleTemplate(t: EmailTemplate) {
    setError(null);
    try {
      const updated = await emailApi.toggleTemplate(t.id);
      setTemplates((curr) =>
        curr.map((x) => (x.id === t.id ? updated : x)),
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Toggle failed");
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
            Email Automation
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Configure sender details, SMTP connection, and manage email
            notification templates.
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
        <h2 className="mb-1 text-base font-semibold">Sender Identity</h2>
        <p className="mb-5 text-xs text-muted-foreground">
          Configure the sender name and addresses for automated emails.
        </p>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <Field label="From Name">
            <input
              type="text"
              value={settings.from_name}
              onChange={(e) =>
                setSettings({ ...settings, from_name: e.target.value })
              }
              placeholder="Your name or brand"
              className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </Field>
          <Field label="From Email Address">
            <input
              type="email"
              value={settings.from_email}
              onChange={(e) =>
                setSettings({ ...settings, from_email: e.target.value })
              }
              placeholder="sender@yourdomain.com"
              className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </Field>
          <Field label="Reply-to Email Address" className="md:col-span-2">
            <input
              type="email"
              value={settings.reply_to_email}
              onChange={(e) =>
                setSettings({ ...settings, reply_to_email: e.target.value })
              }
              placeholder="reply@yourdomain.com"
              className="h-9 w-full max-w-md rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </Field>
        </div>
      </section>

      <section className="rounded-lg border border-border bg-background p-5">
        <h2 className="mb-1 text-base font-semibold">SMTP Server</h2>
        <p className="mb-5 text-xs text-muted-foreground">
          Configure the outgoing mail server. Used for all automated email
          delivery.
        </p>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <Field label="SMTP Host">
            <input
              type="text"
              value={settings.smtp_host}
              onChange={(e) =>
                setSettings({ ...settings, smtp_host: e.target.value })
              }
              placeholder="smtp.gmail.com"
              className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </Field>
          <Field label="SMTP Port">
            <input
              type="number"
              value={settings.smtp_port}
              onChange={(e) =>
                setSettings({
                  ...settings,
                  smtp_port: parseInt(e.target.value) || 587,
                })
              }
              className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </Field>
          <Field label="SMTP Username">
            <input
              type="text"
              value={settings.smtp_username}
              onChange={(e) =>
                setSettings({ ...settings, smtp_username: e.target.value })
              }
              placeholder="user@gmail.com"
              className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </Field>
          <Field label="SMTP Password">
            <div className="relative">
              <input
                type={showPw ? "text" : "password"}
                value={smtpPassword}
                onChange={(e) => setSmtpPassword(e.target.value)}
                placeholder={
                  settings.smtp_has_password
                    ? "Leave blank to keep current"
                    : "Enter password"
                }
                className="h-9 w-full rounded-md border border-input bg-background pr-9 pl-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
              <button
                type="button"
                onClick={() => setShowPw(!showPw)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                {showPw ? (
                  <EyeOff className="h-4 w-4" />
                ) : (
                  <Eye className="h-4 w-4" />
                )}
              </button>
            </div>
          </Field>
        </div>

        <div className="mt-4 flex items-center gap-3">
          <button
            type="button"
            onClick={() => void testConnection()}
            disabled={testingConn || !settings.smtp_host}
            className="flex h-9 items-center gap-2 rounded-md border border-input px-3 text-sm font-medium hover:bg-accent disabled:opacity-50"
          >
            {testingConn ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Wifi className="h-4 w-4" />
            )}
            Test Connection
          </button>
          {connResult === "ok" && (
            <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-600">
              <CheckCircle2 className="h-3.5 w-3.5" />
              Connected
            </span>
          )}
          {connResult === "fail" && (
            <span className="inline-flex items-center gap-1 text-xs font-medium text-red-600">
              <XCircle className="h-3.5 w-3.5" />
              Connection failed
            </span>
          )}
        </div>
      </section>

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => void saveSettings()}
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

      <section className="rounded-lg border border-border bg-background p-5">
        <h2 className="mb-1 text-base font-semibold">Templates</h2>
        <p className="mb-5 text-xs text-muted-foreground">
          Enable or disable automated email notifications. Use <em>Send Test</em>{" "}
          to verify delivery.
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs font-medium text-muted-foreground">
                <th className="pb-2 pr-4">Template Type</th>
                <th className="pb-2 pr-4">Enabled</th>
                <th className="pb-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {templates.map((t) => (
                <tr key={t.id} className="border-b border-border last:border-0">
                  <td className="py-2.5 pr-4 text-sm">{t.name}</td>
                  <td className="py-2.5 pr-4">
                    <span
                      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ${
                        t.enabled
                          ? "bg-emerald-100 text-emerald-700"
                          : "bg-muted text-muted-foreground"
                      }`}
                    >
                      {t.enabled ? "Yes" : "No"}
                    </span>
                  </td>
                  <td className="py-2.5">
                    <div className="flex items-center gap-1">
                      <button
                        type="button"
                        onClick={() => void toggleTemplate(t)}
                        className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium text-muted-foreground hover:bg-accent"
                      >
                        {t.enabled ? (
                          <ToggleRight className="h-4 w-4 text-primary" />
                        ) : (
                          <ToggleLeft className="h-4 w-4" />
                        )}
                        {t.enabled ? "Disable" : "Enable"}
                      </button>
                      <button
                        type="button"
                        onClick={() => void sendTest(t)}
                        disabled={testingId === t.id}
                        className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium text-muted-foreground hover:bg-accent disabled:opacity-50"
                      >
                        {testingId === t.id ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <Send className="h-3.5 w-3.5" />
                        )}
                        Send Test
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
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
