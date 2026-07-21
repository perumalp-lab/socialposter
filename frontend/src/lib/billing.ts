import { api, ApiError } from "@/lib/api";

export type PlanLimits = {
  platform_connections: number; // -1 = unlimited
  scheduled_posts: number;
};

export type PlanInfo = {
  plan: "free" | "pro";
  is_pro: boolean;
  status: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  limits: { free: PlanLimits; pro: PlanLimits };
};

export type PlanLimitBody = {
  error: "plan_limit";
  kind: "platform_connections" | "scheduled_posts";
  plan: string;
  current: number;
  limit: number;
  message: string;
};

export type PublicPricing = {
  limits: { free: PlanLimits; pro: PlanLimits };
  pro_price: {
    amount: number | null;
    currency: string | null;
    interval: string | null;
  } | null;
};

export const billingApi = {
  plan: () => api.get<PlanInfo>("/api/billing/plan"),
  checkout: () => api.post<{ url: string }>("/api/billing/checkout"),
  portal: () => api.post<{ url: string }>("/api/billing/portal"),
  publicPricing: () => api.get<PublicPricing>("/api/billing/pricing"),
};

/** Detect a 402 plan-limit error and pull out its structured body. */
export function asPlanLimit(err: unknown): PlanLimitBody | null {
  if (!(err instanceof ApiError)) return null;
  if (err.status !== 402) return null;
  const body = err.body as PlanLimitBody | null;
  if (!body || body.error !== "plan_limit") return null;
  return body;
}
