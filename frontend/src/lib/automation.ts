import { api } from "./api";

export type TriggerType = "engagement_threshold" | "no_post_interval";

export type EngagementThresholdConditions = {
  threshold: number;
  platform?: string;
  days: number;
};

export type NoPostIntervalConditions = {
  hours: number;
  platform?: string;
};

export type RuleConditions =
  | EngagementThresholdConditions
  | NoPostIntervalConditions
  | Record<string, unknown>;

export type ActionType = "notify" | "ai_generate" | "repost";

export type RuleAction = {
  type: ActionType;
  params: {
    message?: string;
    topic?: string;
    platforms?: string[];
  };
};

export type Rule = {
  id: number;
  name: string;
  trigger_type: TriggerType;
  conditions: RuleConditions;
  actions: RuleAction[];
  enabled: boolean;
  last_triggered_at: string | null;
  trigger_count: number;
  created_at: string | null;
};

export type RuleInput = {
  name: string;
  trigger_type: TriggerType;
  conditions: RuleConditions;
  actions: RuleAction[];
};

export type RuleLog = {
  id: number;
  triggered_at: string | null;
  conditions_met: Record<string, unknown> | null;
  actions_taken: Array<Record<string, unknown>> | null;
  success: boolean;
  error_message: string | null;
};

export const automationApi = {
  list: () => api.get<Rule[]>("/api/automation/rules"),
  create: (input: RuleInput) =>
    api.post<{ ok: true; id: number }>("/api/automation/rules", input),
  update: (id: number, input: Partial<RuleInput>) =>
    api.put<{ ok: true }>(`/api/automation/rules/${id}`, input),
  remove: (id: number) =>
    api.delete<{ ok: true }>(`/api/automation/rules/${id}`),
  toggle: (id: number) =>
    api.post<{ ok: true; enabled: boolean }>(
      `/api/automation/rules/${id}/toggle`,
    ),
  logs: (id: number) => api.get<RuleLog[]>(`/api/automation/rules/${id}/logs`),
};

export const TRIGGER_OPTIONS: Array<{ value: TriggerType; label: string }> = [
  { value: "engagement_threshold", label: "Engagement threshold reached" },
  { value: "no_post_interval", label: "No posts for N hours" },
];

export const ACTION_OPTIONS: Array<{ value: ActionType; label: string }> = [
  { value: "notify", label: "Notify (alert)" },
  { value: "ai_generate", label: "AI-generate content" },
  { value: "repost", label: "Repost to other platforms" },
];

export function describeTrigger(rule: Rule): string {
  const c = rule.conditions as Record<string, unknown>;
  if (rule.trigger_type === "engagement_threshold") {
    const platform = (c.platform as string) || "any platform";
    return `≥ ${c.threshold ?? "?"} engagements on ${platform} (last ${c.days ?? "?"}d)`;
  }
  if (rule.trigger_type === "no_post_interval") {
    const platform = (c.platform as string) || "any platform";
    return `No post for ${c.hours ?? "?"}h on ${platform}`;
  }
  return rule.trigger_type;
}

export function describeAction(action: RuleAction): string {
  if (action.type === "notify") {
    return action.params.message
      ? `Notify: "${action.params.message}"`
      : "Notify";
  }
  if (action.type === "ai_generate") {
    return action.params.topic
      ? `AI-generate about "${action.params.topic}"`
      : "AI-generate";
  }
  if (action.type === "repost") {
    return `Repost to ${(action.params.platforms || []).join(", ") || "—"}`;
  }
  return action.type;
}
