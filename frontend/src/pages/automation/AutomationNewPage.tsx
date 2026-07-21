import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  Clock,
  Cpu,
  FlaskConical,
  Loader2,
  RefreshCw,
  Sparkles,
  Zap,
} from "lucide-react";
import { ApiError } from "@/lib/api";
import {
  ACTION_OPTIONS,
  TRIGGER_OPTIONS,
  automationApi,
  type ActionType,
  type RuleAction,
  type RuleConditions,
  type RuleInput,
  type TriggerType,
} from "@/lib/automation";

type Template = {
  id: string;
  name: string;
  description: string;
  icon: typeof Zap;
  trigger_type: TriggerType;
  conditions: RuleConditions;
  actions: RuleAction[];
};

const TEMPLATES: Template[] = [
  {
    id: "engagement_alert",
    name: "Engagement Alert",
    description: "Notify you when a post crosses an engagement threshold.",
    icon: AlertTriangle,
    trigger_type: "engagement_threshold",
    conditions: { threshold: 100, platform: "", days: 7 },
    actions: [{ type: "notify", params: { message: "Viral post detected!" } }],
  },
  {
    id: "auto_repost",
    name: "Auto Repost",
    description:
      "Automatically repost top-performing content to other platforms.",
    icon: RefreshCw,
    trigger_type: "engagement_threshold",
    conditions: { threshold: 50, platform: "", days: 3 },
    actions: [
      {
        type: "repost",
        params: { platforms: ["twitter", "linkedin"] },
      },
    ],
  },
  {
    id: "ai_followup",
    name: "AI Follow-Up",
    description:
      "Have AI draft a follow-up post after a post reaches a milestone.",
    icon: Sparkles,
    trigger_type: "engagement_threshold",
    conditions: { threshold: 200, platform: "", days: 7 },
    actions: [
      {
        type: "ai_generate",
        params: { topic: "Follow-up on popular post" },
      },
    ],
  },
  {
    id: "inactivity_reminder",
    name: "Inactivity Reminder",
    description:
      "Get alerted if no posts have been published in a set time window.",
    icon: Clock,
    trigger_type: "no_post_interval",
    conditions: { hours: 48, platform: "" },
    actions: [
      {
        type: "notify",
        params: { message: "No recent posts — time to publish!" },
      },
    ],
  },
  {
    id: "ai_daily_draft",
    name: "AI Daily Draft",
    description:
      "Have AI auto-generate a draft daily when no post is scheduled.",
    icon: Cpu,
    trigger_type: "no_post_interval",
    conditions: { hours: 24, platform: "" },
    actions: [{ type: "ai_generate", params: { topic: "Daily post idea" } }],
  },
  {
    id: "cross_platform_repost",
    name: "Cross-Platform Repost",
    description:
      "Auto-share high-engagement content across all connected platforms.",
    icon: Zap,
    trigger_type: "engagement_threshold",
    conditions: { threshold: 80, platform: "", days: 5 },
    actions: [
      {
        type: "repost",
        params: { platforms: [] },
      },
    ],
  },
];

function useRuleBuilder() {
  const [name, setName] = useState("");
  const [trigger, setTrigger] = useState<TriggerType>("engagement_threshold");
  const [conditions, setConditions] = useState<RuleConditions>({
    threshold: 100,
    platform: "",
    days: 7,
  });
  const [actions, setActions] = useState<RuleAction[]>([
    { type: "notify", params: { message: "" } },
  ]);

  function applyTemplate(t: Template) {
    setName(t.name);
    setTrigger(t.trigger_type);
    setConditions(t.conditions);
    setActions(t.actions);
  }

  function changeTrigger(t: TriggerType) {
    setTrigger(t);
    if (t === "engagement_threshold") {
      setConditions({ threshold: 100, platform: "", days: 7 });
    } else {
      setConditions({ hours: 24, platform: "" });
    }
  }

  return {
    name,
    setName,
    trigger,
    setTrigger: changeTrigger,
    conditions,
    setConditions,
    actions,
    setActions,
    applyTemplate,
  };
}

function emptyAction(): RuleAction {
  return { type: "notify", params: { message: "" } };
}

export function AutomationNewPage() {
  const navigate = useNavigate();
  const {
    name,
    setName,
    trigger,
    setTrigger,
    conditions,
    setConditions,
    actions,
    setActions,
    applyTemplate,
  } = useRuleBuilder();

  const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    if (!name.trim()) {
      setError("Rule name is required");
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
      await automationApi.create(payload);
      navigate("/automation");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Save failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          New Automation
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Choose a template or configure a custom rule from scratch.
        </p>
      </div>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      <section>
        <h2 className="mb-3 text-sm font-semibold">Choose a Template</h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {TEMPLATES.map((t) => {
            const Icon = t.icon;
            const active = selectedTemplate === t.id;
            return (
              <button
                key={t.id}
                type="button"
                onClick={() => {
                  setSelectedTemplate(t.id);
                  applyTemplate(t);
                }}
                className={`rounded-lg border p-4 text-left transition-colors hover:bg-accent ${
                  active
                    ? "border-primary bg-primary/5 ring-1 ring-primary"
                    : "border-border bg-background"
                }`}
              >
                <div className="grid h-8 w-8 place-items-center rounded-md bg-primary/10 text-primary">
                  <Icon className="h-4 w-4" />
                </div>
                <h3 className="mt-2 text-sm font-semibold">{t.name}</h3>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {t.description}
                </p>
              </button>
            );
          })}
        </div>
      </section>

      <section className="rounded-lg border border-border bg-background p-5">
        <h2 className="mb-1 text-base font-semibold">Configure Rule</h2>
        <p className="mb-5 text-xs text-muted-foreground">
          Customise the rule name, trigger conditions, and actions below.
        </p>
        <div className="space-y-5">
          <Field label="Rule name">
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Alert on viral posts"
              className="h-9 w-full max-w-md rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </Field>

          <Field label="Trigger">
            <select
              value={trigger}
              onChange={(e) => setTrigger(e.target.value as TriggerType)}
              className="h-9 w-full max-w-xs rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
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
                + Add action
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

          <div className="flex items-center gap-2 pt-2">
            <button
              type="button"
              onClick={() => void save()}
              disabled={submitting}
              className="flex h-9 items-center gap-1.5 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-60"
            >
              {submitting ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <FlaskConical className="h-4 w-4" />
              )}
              {submitting ? "Creating..." : "Create Rule"}
            </button>
            <button
              type="button"
              onClick={() => navigate("/automation")}
              className="h-9 rounded-md px-4 text-sm hover:bg-accent"
            >
              Cancel
            </button>
          </div>
        </div>
      </section>
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
            className="grid h-7 w-7 place-items-center rounded-md text-muted-foreground hover:bg-accent hover:text-red-600"
          >
            &times;
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
