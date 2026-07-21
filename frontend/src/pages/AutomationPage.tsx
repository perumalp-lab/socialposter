import { useCallback, useEffect, useState } from "react";
import {
  AlertCircle,
  Bot,
  CheckCircle2,
  Clock,
  Loader2,
  Plus,
  Power,
  Trash2,
  X,
} from "lucide-react";
import { ApiError } from "@/lib/api";
import {
  ACTION_OPTIONS,
  TRIGGER_OPTIONS,
  automationApi,
  describeAction,
  describeTrigger,
  type ActionType,
  type Rule,
  type RuleAction,
  type RuleConditions,
  type RuleInput,
  type RuleLog,
  type TriggerType,
} from "@/lib/automation";
import { cn } from "@/lib/utils";

type EditorState =
  | { mode: "closed" }
  | { mode: "create" }
  | { mode: "edit"; rule: Rule };

export function AutomationPage() {
  const [rules, setRules] = useState<Rule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editor, setEditor] = useState<EditorState>({ mode: "closed" });
  const [logsForRule, setLogsForRule] = useState<Rule | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await automationApi.list();
      setRules(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load rules");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function toggle(rule: Rule) {
    setRules((curr) =>
      curr.map((r) => (r.id === rule.id ? { ...r, enabled: !r.enabled } : r)),
    );
    try {
      await automationApi.toggle(rule.id);
    } catch (err) {
      // Roll back optimistic update.
      setRules((curr) =>
        curr.map((r) => (r.id === rule.id ? { ...r, enabled: rule.enabled } : r)),
      );
      setError(err instanceof ApiError ? err.message : "Toggle failed");
    }
  }

  async function remove(rule: Rule) {
    if (!confirm(`Delete rule "${rule.name}"?`)) return;
    try {
      await automationApi.remove(rule.id);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Delete failed");
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Automation</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Watch for events and respond automatically — alerts, AI follow-ups,
            cross-platform reposts.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setEditor({ mode: "create" })}
          className="flex h-9 items-center gap-2 rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground hover:opacity-90"
        >
          <Plus className="h-4 w-4" />
          New rule
        </button>
      </div>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      {loading ? (
        <div className="text-sm text-muted-foreground">Loading…</div>
      ) : rules.length === 0 ? (
        <EmptyState onCreate={() => setEditor({ mode: "create" })} />
      ) : (
        <ul className="space-y-3">
          {rules.map((r) => (
            <RuleCard
              key={r.id}
              rule={r}
              onToggle={() => void toggle(r)}
              onEdit={() => setEditor({ mode: "edit", rule: r })}
              onDelete={() => void remove(r)}
              onShowLogs={() => setLogsForRule(r)}
            />
          ))}
        </ul>
      )}

      {editor.mode !== "closed" && (
        <RuleEditor
          state={editor}
          onClose={() => setEditor({ mode: "closed" })}
          onSaved={async () => {
            setEditor({ mode: "closed" });
            await refresh();
          }}
        />
      )}

      {logsForRule && (
        <LogsDrawer
          rule={logsForRule}
          onClose={() => setLogsForRule(null)}
        />
      )}
    </div>
  );
}

function EmptyState({ onCreate }: { onCreate: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border bg-background py-16 text-center">
      <Bot className="h-8 w-8 text-muted-foreground" />
      <p className="mt-3 text-sm font-medium">No automation rules yet</p>
      <p className="mt-1 max-w-md text-xs text-muted-foreground">
        Get notified when posts go viral, auto-repost top performers, or have AI
        draft follow-ups for you.
      </p>
      <button
        type="button"
        onClick={onCreate}
        className="mt-4 flex h-9 items-center gap-2 rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground hover:opacity-90"
      >
        <Plus className="h-4 w-4" />
        Create your first rule
      </button>
    </div>
  );
}

function RuleCard({
  rule,
  onToggle,
  onEdit,
  onDelete,
  onShowLogs,
}: {
  rule: Rule;
  onToggle: () => void;
  onEdit: () => void;
  onDelete: () => void;
  onShowLogs: () => void;
}) {
  return (
    <li className="flex items-start gap-4 rounded-lg border border-border bg-background p-4">
      <button
        type="button"
        onClick={onToggle}
        aria-label={rule.enabled ? "Disable rule" : "Enable rule"}
        className={cn(
          "mt-0.5 flex h-6 w-10 shrink-0 items-center rounded-full p-0.5 transition-colors",
          rule.enabled ? "bg-primary" : "bg-muted",
        )}
      >
        <span
          className={cn(
            "h-5 w-5 rounded-full bg-white shadow transition-transform",
            rule.enabled && "translate-x-4",
          )}
        />
      </button>

      <button
        type="button"
        onClick={onEdit}
        className="min-w-0 flex-1 text-left"
      >
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "truncate text-sm font-semibold",
              !rule.enabled && "text-muted-foreground",
            )}
          >
            {rule.name}
          </span>
          {!rule.enabled && (
            <span className="rounded-full bg-muted px-1.5 text-[10px] font-medium text-muted-foreground">
              paused
            </span>
          )}
        </div>
        <div className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground">
          <Clock className="h-3 w-3" />
          {describeTrigger(rule)}
        </div>
        <div className="mt-1 flex flex-wrap gap-1.5">
          {rule.actions.map((a, i) => (
            <span
              key={i}
              className="rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-medium text-primary"
            >
              {describeAction(a)}
            </span>
          ))}
        </div>
        <div className="mt-1.5 text-[11px] text-muted-foreground">
          Triggered {rule.trigger_count}× ·{" "}
          {rule.last_triggered_at
            ? `last ${new Date(rule.last_triggered_at).toLocaleString()}`
            : "never"}
        </div>
      </button>

      <div className="flex shrink-0 items-center gap-1">
        <button
          type="button"
          onClick={onShowLogs}
          className="h-8 rounded-md px-2 text-xs text-muted-foreground hover:bg-accent"
        >
          Logs
        </button>
        <button
          type="button"
          onClick={onDelete}
          aria-label="Delete rule"
          className="grid h-8 w-8 place-items-center rounded-md text-muted-foreground hover:bg-red-50 hover:text-red-600"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      </div>
    </li>
  );
}

function defaultConditions(t: TriggerType): RuleConditions {
  if (t === "engagement_threshold") {
    return { threshold: 100, platform: "", days: 7 };
  }
  return { hours: 24, platform: "" };
}

function emptyAction(): RuleAction {
  return { type: "notify", params: { message: "" } };
}

function RuleEditor({
  state,
  onClose,
  onSaved,
}: {
  state: Exclude<EditorState, { mode: "closed" }>;
  onClose: () => void;
  onSaved: () => void;
}) {
  const initial: RuleInput =
    state.mode === "edit"
      ? {
          name: state.rule.name,
          trigger_type: state.rule.trigger_type,
          conditions: state.rule.conditions,
          actions: state.rule.actions.length ? state.rule.actions : [emptyAction()],
        }
      : {
          name: "",
          trigger_type: "engagement_threshold",
          conditions: defaultConditions("engagement_threshold"),
          actions: [emptyAction()],
        };

  const [name, setName] = useState(initial.name);
  const [trigger, setTrigger] = useState<TriggerType>(initial.trigger_type);
  const [conditions, setConditions] = useState<RuleConditions>(initial.conditions);
  const [actions, setActions] = useState<RuleAction[]>(initial.actions);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function changeTrigger(t: TriggerType) {
    setTrigger(t);
    setConditions(defaultConditions(t));
  }

  async function save() {
    if (!name.trim()) {
      setError("Name is required");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const payload: RuleInput = {
        name: name.trim(),
        trigger_type: trigger,
        conditions,
        actions,
      };
      if (state.mode === "create") {
        await automationApi.create(payload);
      } else {
        await automationApi.update(state.rule.id, payload);
      }
      onSaved();
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
        className="fixed inset-y-0 right-0 z-50 flex w-full max-w-xl flex-col border-l border-border bg-background shadow-2xl"
      >
        <div className="flex h-14 shrink-0 items-center justify-between border-b border-border px-5">
          <h2 className="text-base font-semibold">
            {state.mode === "create" ? "New automation rule" : "Edit rule"}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md px-2 py-1 text-sm text-muted-foreground hover:bg-accent hover:text-foreground"
          >
            Close
          </button>
        </div>

        <div className="flex-1 space-y-5 overflow-y-auto p-5">
          <Field label="Rule name">
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Alert on viral posts"
              className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </Field>

          <Field label="Trigger">
            <select
              value={trigger}
              onChange={(e) => changeTrigger(e.target.value as TriggerType)}
              className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            >
              {TRIGGER_OPTIONS.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </Field>

          <ConditionFields
            trigger={trigger}
            conditions={conditions}
            onChange={setConditions}
          />

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Actions
              </span>
              <button
                type="button"
                onClick={() => setActions((a) => [...a, emptyAction()])}
                className="flex h-7 items-center gap-1 rounded-md px-2 text-xs font-medium text-primary hover:bg-primary/10"
              >
                <Plus className="h-3 w-3" />
                Add action
              </button>
            </div>
            <ul className="space-y-2">
              {actions.map((a, i) => (
                <li key={i}>
                  <ActionEditor
                    action={a}
                    onChange={(next) =>
                      setActions((arr) =>
                        arr.map((x, idx) => (idx === i ? next : x)),
                      )
                    }
                    onRemove={
                      actions.length > 1
                        ? () =>
                            setActions((arr) =>
                              arr.filter((_, idx) => idx !== i),
                            )
                        : undefined
                    }
                  />
                </li>
              ))}
            </ul>
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
            {submitting ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Power className="h-3.5 w-3.5" />
            )}
            {state.mode === "create" ? "Create rule" : "Save changes"}
          </button>
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

function ConditionFields({
  trigger,
  conditions,
  onChange,
}: {
  trigger: TriggerType;
  conditions: RuleConditions;
  onChange: (c: RuleConditions) => void;
}) {
  const c = conditions as Record<string, unknown>;
  if (trigger === "engagement_threshold") {
    return (
      <div className="grid grid-cols-2 gap-3">
        <Field label="Threshold (likes + comments + shares)">
          <input
            type="number"
            min={1}
            value={(c.threshold as number) ?? 100}
            onChange={(e) =>
              onChange({ ...c, threshold: parseInt(e.target.value) || 0 })
            }
            className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </Field>
        <Field label="Lookback (days)">
          <input
            type="number"
            min={1}
            value={(c.days as number) ?? 7}
            onChange={(e) =>
              onChange({ ...c, days: parseInt(e.target.value) || 1 })
            }
            className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </Field>
        <div className="col-span-2">
          <Field label="Platform (optional)">
            <input
              type="text"
              value={(c.platform as string) ?? ""}
              onChange={(e) => onChange({ ...c, platform: e.target.value })}
              placeholder="e.g. twitter — leave empty for any"
              className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </Field>
        </div>
      </div>
    );
  }
  // no_post_interval
  return (
    <div className="grid grid-cols-2 gap-3">
      <Field label="Hours without posting">
        <input
          type="number"
          min={1}
          value={(c.hours as number) ?? 24}
          onChange={(e) =>
            onChange({ ...c, hours: parseInt(e.target.value) || 1 })
          }
          className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        />
      </Field>
      <Field label="Platform (optional)">
        <input
          type="text"
          value={(c.platform as string) ?? ""}
          onChange={(e) => onChange({ ...c, platform: e.target.value })}
          placeholder="e.g. linkedin"
          className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        />
      </Field>
    </div>
  );
}

function ActionEditor({
  action,
  onChange,
  onRemove,
}: {
  action: RuleAction;
  onChange: (a: RuleAction) => void;
  onRemove?: () => void;
}) {
  function setType(type: ActionType) {
    onChange({ type, params: {} });
  }
  function setParam<K extends keyof RuleAction["params"]>(
    key: K,
    value: RuleAction["params"][K],
  ) {
    onChange({ ...action, params: { ...action.params, [key]: value } });
  }

  return (
    <div className="rounded-md border border-border bg-muted/30 p-3 space-y-2">
      <div className="flex items-center gap-2">
        <select
          value={action.type}
          onChange={(e) => setType(e.target.value as ActionType)}
          className="h-8 flex-1 rounded-md border border-input bg-background px-2 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
        >
          {ACTION_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        {onRemove && (
          <button
            type="button"
            onClick={onRemove}
            aria-label="Remove action"
            className="grid h-7 w-7 place-items-center rounded-md text-muted-foreground hover:bg-accent hover:text-red-600"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>
      {action.type === "notify" && (
        <input
          type="text"
          value={action.params.message ?? ""}
          onChange={(e) => setParam("message", e.target.value)}
          placeholder="Optional message — defaults to a generic alert"
          className="h-8 w-full rounded-md border border-input bg-background px-2 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
        />
      )}
      {action.type === "ai_generate" && (
        <input
          type="text"
          value={action.params.topic ?? ""}
          onChange={(e) => setParam("topic", e.target.value)}
          placeholder="Topic / prompt for the AI"
          className="h-8 w-full rounded-md border border-input bg-background px-2 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
        />
      )}
      {action.type === "repost" && (
        <input
          type="text"
          value={(action.params.platforms || []).join(", ")}
          onChange={(e) =>
            setParam(
              "platforms",
              e.target.value
                .split(",")
                .map((s) => s.trim())
                .filter(Boolean),
            )
          }
          placeholder="Platforms (comma-separated): linkedin, twitter, facebook"
          className="h-8 w-full rounded-md border border-input bg-background px-2 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
        />
      )}
    </div>
  );
}

function LogsDrawer({
  rule,
  onClose,
}: {
  rule: Rule;
  onClose: () => void;
}) {
  const [logs, setLogs] = useState<RuleLog[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    automationApi
      .logs(rule.id)
      .then((data) => {
        if (!cancelled) setLogs(data);
      })
      .catch((err) => {
        if (!cancelled)
          setError(err instanceof ApiError ? err.message : "Failed to load logs");
      });
    return () => {
      cancelled = true;
    };
  }, [rule.id]);

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
        className="fixed inset-y-0 right-0 z-50 flex w-full max-w-xl flex-col border-l border-border bg-background shadow-2xl"
      >
        <div className="flex h-14 shrink-0 items-center justify-between border-b border-border px-5">
          <div className="min-w-0">
            <h2 className="truncate text-base font-semibold">
              Logs · {rule.name}
            </h2>
            <p className="text-xs text-muted-foreground">
              Last 50 executions
            </p>
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
              No executions yet.
            </div>
          ) : (
            <ul className="space-y-3">
              {logs.map((l) => (
                <li
                  key={l.id}
                  className="rounded-md border border-border bg-background p-3"
                >
                  <div className="flex items-start gap-2">
                    {l.success ? (
                      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                    ) : (
                      <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-600" />
                    )}
                    <div className="min-w-0 flex-1">
                      <div className="text-xs font-medium">
                        {l.triggered_at
                          ? new Date(l.triggered_at).toLocaleString()
                          : "—"}
                      </div>
                      {l.error_message && (
                        <div className="mt-0.5 text-xs text-red-700">
                          {l.error_message}
                        </div>
                      )}
                      {l.conditions_met && (
                        <pre className="mt-1 overflow-x-auto rounded bg-muted/40 p-2 text-[10px]">
                          {JSON.stringify(l.conditions_met, null, 2)}
                        </pre>
                      )}
                      {l.actions_taken && l.actions_taken.length > 0 && (
                        <pre className="mt-1 overflow-x-auto rounded bg-muted/40 p-2 text-[10px]">
                          {JSON.stringify(l.actions_taken, null, 2)}
                        </pre>
                      )}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </aside>
    </>
  );
}
