import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  CheckCircle2,
  CreditCard,
  ExternalLink,
  Loader2,
  Sparkles,
  XCircle,
} from "lucide-react";
import { ApiError } from "@/lib/api";
import { billingApi, type PlanInfo } from "@/lib/billing";
import { cn } from "@/lib/utils";

export function BillingPage() {
  const [params] = useSearchParams();
  const checkoutStatus = params.get("status");
  const [plan, setPlan] = useState<PlanInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"checkout" | "portal" | null>(null);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    billingApi
      .plan()
      .then((p) => {
        if (alive) {
          setPlan(p);
          setError(null);
        }
      })
      .catch((err) => {
        if (alive)
          setError(err instanceof ApiError ? err.message : "Failed to load plan");
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  async function startCheckout() {
    setBusy("checkout");
    setError(null);
    try {
      const { url } = await billingApi.checkout();
      window.location.assign(url);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Checkout failed");
      setBusy(null);
    }
  }

  async function openPortal() {
    setBusy("portal");
    setError(null);
    try {
      const { url } = await billingApi.portal();
      window.location.assign(url);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Portal failed");
      setBusy(null);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Billing</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Manage your subscription and see what each plan includes.
        </p>
      </div>

      {checkoutStatus === "success" && (
        <Banner kind="success">
          Payment received. Your subscription will activate within a few seconds —
          this page will reflect Pro shortly.
        </Banner>
      )}
      {checkoutStatus === "cancelled" && (
        <Banner kind="info">
          Checkout was cancelled. You can upgrade any time.
        </Banner>
      )}

      {error && <Banner kind="error">{error}</Banner>}

      {loading && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading plan…
        </div>
      )}

      {plan && (
        <>
          <CurrentPlanCard
            plan={plan}
            busy={busy}
            onUpgrade={startCheckout}
            onManage={openPortal}
          />
          <PlanComparison plan={plan} />
        </>
      )}
    </div>
  );
}

function CurrentPlanCard({
  plan,
  busy,
  onUpgrade,
  onManage,
}: {
  plan: PlanInfo;
  busy: "checkout" | "portal" | null;
  onUpgrade: () => void;
  onManage: () => void;
}) {
  const periodEnd = plan.current_period_end
    ? new Date(plan.current_period_end).toLocaleDateString()
    : null;

  return (
    <section className="rounded-lg border border-border bg-background">
      <header className="flex items-center justify-between border-b border-border px-5 py-3">
        <div className="flex items-center gap-2">
          <CreditCard className="h-4 w-4 text-primary" />
          <h2 className="text-sm font-semibold">Current plan</h2>
        </div>
        <span
          className={cn(
            "rounded-full px-2 py-0.5 text-[11px] font-medium",
            plan.is_pro
              ? "bg-emerald-100 text-emerald-700"
              : "bg-muted text-muted-foreground",
          )}
        >
          {plan.is_pro ? "PRO" : "FREE"}
        </span>
      </header>
      <div className="flex flex-col gap-3 p-5 sm:flex-row sm:items-start sm:justify-between">
        <div className="max-w-xl text-sm">
          {plan.is_pro ? (
            <>
              <p>
                You're on Pro — unlimited platform connections and scheduled
                posts.
              </p>
              {plan.cancel_at_period_end && periodEnd && (
                <p className="mt-2 text-xs text-amber-700">
                  Subscription set to cancel at {periodEnd}.
                </p>
              )}
              {!plan.cancel_at_period_end && periodEnd && (
                <p className="mt-2 text-xs text-muted-foreground">
                  Renews on {periodEnd}.
                </p>
              )}
            </>
          ) : (
            <p>
              You're on the Free plan. Upgrade to Pro for unlimited platform
              connections and scheduled posts.
            </p>
          )}
        </div>
        <div className="flex shrink-0 gap-2">
          {plan.is_pro ? (
            <button
              type="button"
              onClick={onManage}
              disabled={busy !== null}
              className="flex h-9 items-center gap-1.5 rounded-md border border-border px-3 text-sm font-medium hover:bg-accent disabled:opacity-60"
            >
              {busy === "portal" ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <ExternalLink className="h-3.5 w-3.5" />
              )}
              Manage subscription
            </button>
          ) : (
            <button
              type="button"
              onClick={onUpgrade}
              disabled={busy !== null}
              className="flex h-9 items-center gap-1.5 rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-60"
            >
              {busy === "checkout" ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Sparkles className="h-3.5 w-3.5" />
              )}
              Upgrade to Pro
            </button>
          )}
        </div>
      </div>
    </section>
  );
}

function PlanComparison({ plan }: { plan: PlanInfo }) {
  const rows: { label: string; key: keyof PlanInfo["limits"]["free"] }[] = [
    { label: "Platform connections", key: "platform_connections" },
    { label: "Scheduled posts", key: "scheduled_posts" },
  ];

  return (
    <section className="rounded-lg border border-border bg-background">
      <header className="border-b border-border px-5 py-3">
        <h2 className="text-sm font-semibold">What's included</h2>
      </header>
      <div className="overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted/40 text-xs uppercase tracking-wide text-muted-foreground">
            <tr>
              <th className="px-5 py-2.5 text-left font-medium">Feature</th>
              <th className="px-5 py-2.5 text-left font-medium">Free</th>
              <th className="px-5 py-2.5 text-left font-medium">Pro</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows.map((r) => (
              <tr key={r.key}>
                <td className="px-5 py-3 font-medium">{r.label}</td>
                <td className="px-5 py-3">
                  {formatLimit(plan.limits.free[r.key])}
                </td>
                <td className="px-5 py-3">
                  {formatLimit(plan.limits.pro[r.key])}
                </td>
              </tr>
            ))}
            <tr>
              <td className="px-5 py-3 font-medium">Posting (manual)</td>
              <td className="px-5 py-3">Unlimited</td>
              <td className="px-5 py-3">Unlimited</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p className="border-t border-border px-5 py-3 text-[11px] text-muted-foreground">
        Facebook, Instagram and WhatsApp share one Meta connection slot.
      </p>
    </section>
  );
}

function formatLimit(value: number): string {
  if (value < 0) return "Unlimited";
  return value.toString();
}

function Banner({
  kind,
  children,
}: {
  kind: "success" | "info" | "error";
  children: React.ReactNode;
}) {
  const styles = {
    success: "border-emerald-200 bg-emerald-50 text-emerald-800",
    info: "border-sky-200 bg-sky-50 text-sky-800",
    error: "border-red-200 bg-red-50 text-red-700",
  } as const;
  const Icon = kind === "error" ? XCircle : CheckCircle2;
  return (
    <div
      className={cn(
        "flex items-start gap-2 rounded-md border px-3 py-2 text-sm",
        styles[kind],
      )}
    >
      <Icon className="mt-0.5 h-4 w-4 shrink-0" />
      <div>{children}</div>
    </div>
  );
}
