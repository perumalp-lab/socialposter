import { useCallback, useEffect, useState } from "react";
import {
  Eye,
  EyeOff,
  Loader2,
  MessageCircle,
  Pencil,
  Plus,
  Save,
  Send,
  Trash2,
} from "lucide-react";
import { ApiError } from "@/lib/api";
import {
  whatsappApi,
  type WhatsAppMessage,
  type WhatsAppMessageInput,
  type WhatsAppSettings,
} from "@/lib/whatsapp";

export function AutomationWhatsAppPage() {
  const [settings, setSettings] = useState<WhatsAppSettings>({
    phone_number_id: "",
    business_account_id: "",
    has_access_token: false,
    webhook_verify_token: "",
  });
  const [accessToken, setAccessToken] = useState("");
  const [messages, setMessages] = useState<WhatsAppMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [showToken, setShowToken] = useState(false);

  const [showForm, setShowForm] = useState(false);
  const [editingMsg, setEditingMsg] = useState<WhatsAppMessage | null>(null);
  const [form, setForm] = useState<WhatsAppMessageInput>({
    name: "",
    template_name: "",
    body: "",
    language: "en",
    header_type: "none",
    header_value: "",
    footer: "",
  });

  const [sendTo, setSendTo] = useState("");
  const [testBody, setTestBody] = useState("");
  const [sendingTest, setSendingTest] = useState(false);
  const [sendingId, setSendingId] = useState<number | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, m] = await Promise.all([
        whatsappApi.getSettings(),
        whatsappApi.listMessages(),
      ]);
      setSettings(s);
      setMessages(m);
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
      if (accessToken) payload.access_token = accessToken;
      const updated = await whatsappApi.updateSettings(payload);
      setSettings(updated);
      setAccessToken("");
      setSuccess("Settings saved");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  function openCreate() {
    setForm({ name: "", body: "", language: "en" });
    setEditingMsg(null);
    setShowForm(true);
  }

  function openEdit(m: WhatsAppMessage) {
    setForm({
      name: m.name,
      template_name: m.template_name,
      body: m.body,
      language: m.language,
      header_type: m.header_type,
      header_value: m.header_value,
      footer: m.footer,
    });
    setEditingMsg(m);
    setShowForm(true);
  }

  async function saveMessage() {
    if (!form.name.trim()) return;
    setError(null);
    try {
      if (editingMsg) {
        await whatsappApi.updateMessage(editingMsg.id, form);
      } else {
        await whatsappApi.createMessage(form);
      }
      setShowForm(false);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Save failed");
    }
  }

  async function deleteMessage(m: WhatsAppMessage) {
    if (!confirm(`Delete message "${m.name}"?`)) return;
    setError(null);
    try {
      await whatsappApi.deleteMessage(m.id);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Delete failed");
    }
  }

  async function sendTestMessage() {
    if (!sendTo.trim()) return;
    setSendingTest(true);
    setError(null);
    setSuccess(null);
    try {
      const r = await whatsappApi.sendTest(
        sendTo.trim(),
        testBody.trim() || "Test message from Kryptams",
      );
      if (r.ok) {
        setSuccess("Test message sent");
        setSendTo("");
        setTestBody("");
      } else {
        setError(r.error || "Send failed");
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Send failed");
    } finally {
      setSendingTest(false);
    }
  }

  async function sendTemplate(m: WhatsAppMessage) {
    const to = prompt("Recipient phone number (include country code):");
    if (!to) return;
    setSendingId(m.id);
    setError(null);
    setSuccess(null);
    try {
      const r = await whatsappApi.sendMessage(m.id, to.trim());
      if (r.ok) {
        setSuccess(`Message sent to ${to}`);
      } else {
        setError(r.error || "Send failed");
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Send failed");
    } finally {
      setSendingId(null);
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
            WhatsApp Automation
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Automate WhatsApp messages, broadcasts, and chatbots.
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
        <h2 className="mb-1 text-base font-semibold">
          WhatsApp Business API Connection
        </h2>
        <p className="mb-5 text-xs text-muted-foreground">
          Connect your WhatsApp Business Account to send messages via the Cloud
          API.
        </p>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <Field label="Phone Number ID">
            <input
              type="text"
              value={settings.phone_number_id}
              onChange={(e) =>
                setSettings({ ...settings, phone_number_id: e.target.value })
              }
              placeholder="From Meta Business Dashboard"
              className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </Field>
          <Field label="Business Account ID">
            <input
              type="text"
              value={settings.business_account_id}
              onChange={(e) =>
                setSettings({
                  ...settings,
                  business_account_id: e.target.value,
                })
              }
              placeholder="Optional"
              className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </Field>
          <Field label="Access Token">
            <div className="relative">
              <input
                type={showToken ? "text" : "password"}
                value={accessToken}
                onChange={(e) => setAccessToken(e.target.value)}
                placeholder={
                  settings.has_access_token
                    ? "Leave blank to keep current"
                    : "Permanent or temporary token"
                }
                className="h-9 w-full rounded-md border border-input bg-background pr-9 pl-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
              <button
                type="button"
                onClick={() => setShowToken(!showToken)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                {showToken ? (
                  <EyeOff className="h-4 w-4" />
                ) : (
                  <Eye className="h-4 w-4" />
                )}
              </button>
            </div>
          </Field>
          <Field label="Webhook Verify Token">
            <input
              type="text"
              value={settings.webhook_verify_token}
              onChange={(e) =>
                setSettings({
                  ...settings,
                  webhook_verify_token: e.target.value,
                })
              }
              placeholder="For inbound message webhooks"
              className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </Field>
        </div>
        <button
          type="button"
          onClick={() => void saveSettings()}
          disabled={saving}
          className="mt-4 flex h-9 items-center gap-2 rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-60"
        >
          {saving ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Save className="h-4 w-4" />
          )}
          Save API Settings
        </button>
      </section>

      <section className="rounded-lg border border-border bg-background p-5">
        <h2 className="mb-1 text-base font-semibold">Send Test Message</h2>
        <p className="mb-5 text-xs text-muted-foreground">
          Send a quick test to verify your WhatsApp API connection.
        </p>
        <div className="flex flex-wrap items-end gap-3">
          <Field label="Recipient phone">
            <input
              type="text"
              value={sendTo}
              onChange={(e) => setSendTo(e.target.value)}
              placeholder="+1234567890"
              className="h-9 w-56 rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </Field>
          <Field label="Message (optional)">
            <input
              type="text"
              value={testBody}
              onChange={(e) => setTestBody(e.target.value)}
              placeholder="Test message from Kryptams"
              className="h-9 w-72 rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </Field>
          <button
            type="button"
            onClick={() => void sendTestMessage()}
            disabled={sendingTest || !sendTo.trim()}
            className="flex h-9 items-center gap-2 rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-60"
          >
            {sendingTest ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
            Send Test
          </button>
        </div>
      </section>

      <section className="rounded-lg border border-border bg-background p-5">
        <div className="mb-5 flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold">Message Templates</h2>
            <p className="mt-0.5 text-xs text-muted-foreground">
              Pre-built messages you can send or use in broadcasts.
            </p>
          </div>
          <button
            type="button"
            onClick={openCreate}
            className="flex h-8 items-center gap-1.5 rounded-md bg-primary px-3 text-xs font-medium text-primary-foreground hover:opacity-90"
          >
            <Plus className="h-3.5 w-3.5" />
            New Message
          </button>
        </div>

        {showForm && (
          <div className="mb-5 rounded-md border border-border bg-muted/30 p-4">
            <h3 className="mb-3 text-sm font-semibold">
              {editingMsg ? "Edit" : "New"} Message Template
            </h3>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <Field label="Name">
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="e.g. Welcome Message"
                  className="h-8 w-full rounded-md border border-input bg-background px-2 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </Field>
              <Field label="Template Name (Meta)">
                <input
                  type="text"
                  value={form.template_name}
                  onChange={(e) =>
                    setForm({ ...form, template_name: e.target.value })
                  }
                  placeholder="Approved template name"
                  className="h-8 w-full rounded-md border border-input bg-background px-2 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </Field>
              <Field label="Language" className="md:col-span-2">
                <select
                  value={form.language}
                  onChange={(e) => setForm({ ...form, language: e.target.value })}
                  className="h-8 w-full max-w-xs rounded-md border border-input bg-background px-2 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  <option value="en">English</option>
                  <option value="en_US">English (US)</option>
                  <option value="en_GB">English (UK)</option>
                  <option value="hi">Hindi</option>
                  <option value="ta">Tamil</option>
                  <option value="te">Telugu</option>
                  <option value="mr">Marathi</option>
                  <option value="gu">Gujarati</option>
                  <option value="bn">Bengali</option>
                </select>
              </Field>
              <Field label="Header Type" className="md:col-span-2">
                <select
                  value={form.header_type}
                  onChange={(e) =>
                    setForm({ ...form, header_type: e.target.value })
                  }
                  className="h-8 w-full max-w-xs rounded-md border border-input bg-background px-2 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  <option value="none">None</option>
                  <option value="text">Text</option>
                  <option value="image">Image URL</option>
                </select>
              </Field>
              {form.header_type !== "none" && (
                <Field label="Header Value" className="md:col-span-2">
                  <input
                    type="text"
                    value={form.header_value}
                    onChange={(e) =>
                      setForm({ ...form, header_value: e.target.value })
                    }
                    placeholder={
                      form.header_type === "image"
                        ? "https://example.com/image.jpg"
                        : "Header text"
                    }
                    className="h-8 w-full rounded-md border border-input bg-background px-2 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                </Field>
              )}
              <Field label="Body" className="md:col-span-2">
                <textarea
                  value={form.body}
                  onChange={(e) => setForm({ ...form, body: e.target.value })}
                  rows={3}
                  placeholder="Message body text"
                  className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </Field>
              <Field label="Footer" className="md:col-span-2">
                <input
                  type="text"
                  value={form.footer}
                  onChange={(e) => setForm({ ...form, footer: e.target.value })}
                  placeholder="Optional footer text"
                  className="h-8 w-full rounded-md border border-input bg-background px-2 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </Field>
            </div>
            <div className="mt-3 flex items-center gap-2">
              <button
                type="button"
                onClick={() => void saveMessage()}
                disabled={!form.name.trim()}
                className="flex h-8 items-center gap-1 rounded-md bg-primary px-3 text-xs font-medium text-primary-foreground hover:opacity-90 disabled:opacity-60"
              >
                {editingMsg ? "Update" : "Create"}
              </button>
              <button
                type="button"
                onClick={() => setShowForm(false)}
                className="h-8 rounded-md px-3 text-xs hover:bg-accent"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border py-12 text-center">
            <MessageCircle className="h-7 w-7 text-muted-foreground" />
            <p className="mt-2 text-sm font-medium">No message templates</p>
            <p className="mt-1 text-xs text-muted-foreground">
              Create your first template to start sending WhatsApp messages.
            </p>
          </div>
        ) : (
          <ul className="space-y-2">
            {messages.map((m) => (
              <li
                key={m.id}
                className="flex items-start gap-3 rounded-md border border-border bg-background p-3"
              >
                <div className="grid h-8 w-8 shrink-0 place-items-center rounded-md bg-emerald-100 text-emerald-600">
                  <MessageCircle className="h-4 w-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="truncate text-sm font-semibold">
                      {m.name}
                    </span>
                    {m.template_name && (
                      <span className="rounded-full bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
                        {m.template_name}
                      </span>
                    )}
                  </div>
                  {m.body && (
                    <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">
                      {m.body}
                    </p>
                  )}
                  <div className="mt-1 flex flex-wrap gap-2 text-[10px] text-muted-foreground">
                    <span>{m.language}</span>
                    {m.header_type !== "none" && (
                      <span>Header: {m.header_type}</span>
                    )}
                    {m.footer && <span>Footer: {m.footer}</span>}
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-1">
                  <button
                    type="button"
                    onClick={() => sendTemplate(m)}
                    disabled={sendingId === m.id}
                    className="grid h-7 w-7 place-items-center rounded-md text-muted-foreground hover:bg-accent"
                    aria-label="Send"
                  >
                    {sendingId === m.id ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Send className="h-3.5 w-3.5" />
                    )}
                  </button>
                  <button
                    type="button"
                    onClick={() => openEdit(m)}
                    className="grid h-7 w-7 place-items-center rounded-md text-muted-foreground hover:bg-accent"
                    aria-label="Edit"
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => deleteMessage(m)}
                    className="grid h-7 w-7 place-items-center rounded-md text-muted-foreground hover:bg-red-50 hover:text-red-600"
                    aria-label="Delete"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
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
