import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Check, Loader2, Sparkles } from "lucide-react";
import { useAuth } from "@/auth/AuthContext";
import { ApiError } from "@/lib/api";
import { billingApi, type PublicPricing } from "@/lib/billing";
import { cn } from "@/lib/utils";

export function PricingPage() {
  const { status } = useAuth();
  const isAuthed = status === "authenticated";
  const [pricing, setPricing] = useState<PublicPricing | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    billingApi
      .publicPricing()
      .then((p) => {
        if (alive) {
          setPricing(p);
          setError(null);
        }
      })
      .catch((err) => {
        if (alive)
          setError(err instanceof ApiError ? err.message : "Failed to load");
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  return (
    <div className="min-h-screen bg-muted/20">
      <Header isAuthed={isAuthed} />

      <main className="mx-auto max-w-5xl px-4 py-12">
        <div className="mb-12 text-center">
          <h1 className="text-4xl font-semibold tracking-tight">Simple pricing</h1>
          <p className="mt-2 text-muted-foreground">
            Start free. Upgrade when you outgrow it.
          </p>
        </div>

        {error && (
          <div className="mx-auto mb-8 max-w-md rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        )}

        {loading && (
          <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading plans…
          </div>
        )}

        {pricing && (
          <div className="grid gap-6 md:grid-cols-2">
            <PlanCard
              kind="free"
              title="Free"
              priceLabel="$0"
              priceHint="forever"
              features={freeFeatures(pricing)}
              cta={
                isAuthed ? (
                  <Link
                    to="/dashboard"
                    className="inline-flex h-10 w-full items-center justify-center gap-1.5 rounded-md border border-border bg-background px-4 text-sm font-medium hover:bg-accent"
                  >
                    Go to dashboard
                  </Link>
                ) : (
                  <Link
                    to="/login"
                    className="inline-flex h-10 w-full items-center justify-center gap-1.5 rounded-md border border-border bg-background px-4 text-sm font-medium hover:bg-accent"
                  >
                    Sign up free
                  </Link>
                )
              }
            />
            <PlanCard
              kind="pro"
              title="Pro"
              priceLabel={proPriceLabel(pricing)}
              priceHint={proPriceHint(pricing)}
              features={proFeatures(pricing)}
              cta={
                isAuthed ? (
                  <Link
                    to="/settings/billing"
                    className="inline-flex h-10 w-full items-center justify-center gap-1.5 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground hover:opacity-90"
                  >
                    <Sparkles className="h-3.5 w-3.5" />
                    Upgrade now
                  </Link>
                ) : (
                  <Link
                    to="/login"
                    className="inline-flex h-10 w-full items-center justify-center gap-1.5 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground hover:opacity-90"
                  >
                    Get started
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                )
              }
            />
          </div>
        )}

        <p className="mt-10 text-center text-xs text-muted-foreground">
          Facebook, Instagram and WhatsApp share one Meta connection slot.
        </p>
      </main>
    </div>
  );
}

function Header({ isAuthed }: { isAuthed: boolean }) {
  return (
    <header className="border-b border-border bg-background">
      <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-4">
        <Link to="/" className="flex items-center gap-2">
          <div className="grid h-8 w-8 place-items-center rounded-md bg-primary text-primary-foreground">
            <Sparkles className="h-4 w-4" />
          </div>
          <span className="text-sm font-semibold tracking-tight">Kryptams</span>
        </Link>
        <nav className="flex items-center gap-2">
          {isAuthed ? (
            <Link
              to="/dashboard"
              className="inline-flex h-9 items-center rounded-md border border-border px-3 text-sm font-medium hover:bg-accent"
            >
              Dashboard
            </Link>
          ) : (
            <>
              <Link
                to="/login"
                className="inline-flex h-9 items-center rounded-md px-3 text-sm font-medium hover:bg-accent"
              >
                Sign in
              </Link>
              <Link
                to="/login"
                className="inline-flex h-9 items-center rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground hover:opacity-90"
              >
                Sign up
              </Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}

function PlanCard({
  kind,
  title,
  priceLabel,
  priceHint,
  features,
  cta,
}: {
  kind: "free" | "pro";
  title: string;
  priceLabel: string;
  priceHint: string;
  features: string[];
  cta: React.ReactNode;
}) {
  return (
    <section
      className={cn(
        "rounded-2xl border p-8",
        kind === "pro"
          ? "border-primary/40 bg-background shadow-md ring-1 ring-primary/10"
          : "border-border bg-background",
      )}
    >
      <div className="flex items-center gap-2">
        <h2 className="text-xl font-semibold">{title}</h2>
        {kind === "pro" && (
          <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-medium text-primary">
            Most popular
          </span>
        )}
      </div>
      <div className="mt-3 flex items-baseline gap-1.5">
        <span className="text-4xl font-semibold tracking-tight">{priceLabel}</span>
        <span className="text-sm text-muted-foreground">{priceHint}</span>
      </div>
      <ul className="mt-6 space-y-2.5 text-sm">
        {features.map((f) => (
          <li key={f} className="flex items-start gap-2">
            <Check className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
            <span>{f}</span>
          </li>
        ))}
      </ul>
      <div className="mt-8">{cta}</div>
    </section>
  );
}

function formatLimit(value: number, kind: "connections" | "schedules"): string {
  if (value < 0) return kind === "connections" ? "All platforms" : "Unlimited scheduled posts";
  return kind === "connections"
    ? `${value} platform connection${value === 1 ? "" : "s"}`
    : `${value} scheduled post${value === 1 ? "" : "s"}`;
}

function freeFeatures(p: PublicPricing): string[] {
  return [
    formatLimit(p.limits.free.platform_connections, "connections"),
    formatLimit(p.limits.free.scheduled_posts, "schedules"),
    "Unlimited manual posts",
    "Comment inbox & engagement analytics",
  ];
}

function proFeatures(p: PublicPricing): string[] {
  return [
    formatLimit(p.limits.pro.platform_connections, "connections"),
    formatLimit(p.limits.pro.scheduled_posts, "schedules"),
    "Unlimited manual posts",
    "Comment inbox & engagement analytics",
    "Priority support",
  ];
}

function proPriceLabel(p: PublicPricing): string {
  const price = p.pro_price;
  if (price && price.amount != null && price.currency) {
    const symbol = currencySymbol(price.currency);
    const amount = (price.amount / 100).toFixed(2).replace(/\.00$/, "");
    return `${symbol}${amount}`;
  }
  return "Coming soon";
}

function proPriceHint(p: PublicPricing): string {
  const interval = p.pro_price?.interval;
  if (!interval) return "";
  return `per ${interval}`;
}

function currencySymbol(code: string): string {
  switch (code.toLowerCase()) {
    case "usd": return "$";
    case "eur": return "€";
    case "gbp": return "£";
    case "jpy": return "¥";
    default: return `${code.toUpperCase()} `;
  }
}
