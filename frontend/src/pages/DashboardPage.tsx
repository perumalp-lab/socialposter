import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  Calendar,
  CheckCircle2,
  Clock,
  ExternalLink,
  FileText,
  Heart,
  MessageSquare,
  Plug,
  Send,
  Sparkles,
  TrendingUp,
  Zap,
} from "lucide-react";
import { ApiError } from "@/lib/api";
import {
  analyticsApi,
  type BestTimes,
  type Engagement,
  type Summary,
  type Timeline,
  type TopPost,
} from "@/lib/analytics";
import { connectionsApi, type OAuthStatus } from "@/lib/connections";
import { PlatformBadge } from "@/components/PlatformBadge";
import { platformBrand, platformLabel } from "@/lib/platformColors";
import { cn } from "@/lib/utils";
import { schedulesApi, type ScheduledPost } from "@/lib/schedules";
import { draftsApi, type DraftListItem } from "@/lib/drafts";
import { inboxApi, type InboxStats } from "@/lib/inbox";
import { automationApi, type Rule } from "@/lib/automation";
import { billingApi, type PlanInfo } from "@/lib/billing";

const RANGE_OPTIONS = [
  { label: "7d", value: 7 },
  { label: "30d", value: 30 },
  { label: "90d", value: 90 },
] as const;

export function DashboardPage() {
  const [days, setDays] = useState<number>(30);

  const [summary, setSummary] = useState<Summary | null>(null);
  const [timeline, setTimeline] = useState<Timeline | null>(null);
  const [engagement, setEngagement] = useState<Engagement | null>(null);
  const [top, setTop] = useState<TopPost[]>([]);
  const [bestTimes, setBestTimes] = useState<BestTimes | null>(null);
  const [oauth, setOauth] = useState<OAuthStatus>({});

  const [schedules, setSchedules] = useState<ScheduledPost[]>([]);
  const [pendingDrafts, setPendingDrafts] = useState<DraftListItem[]>([]);
  const [inboxStats, setInboxStats] = useState<InboxStats | null>(null);
  const [automationRules, setAutomationRules] = useState<Rule[]>([]);
  const [planInfo, setPlanInfo] = useState<PlanInfo | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, t, e, tp, bt, oa, sc, pd, is, ar, pi] = await Promise.all([
        analyticsApi.summary(days),
        analyticsApi.timeline(days),
        analyticsApi.engagement(days),
        analyticsApi.topPosts(days),
        analyticsApi.bestTimes().catch(() => ({ hours: [] }) as BestTimes),
        connectionsApi.oauthStatus().catch(() => ({}) as OAuthStatus),
        schedulesApi.list().catch(() => [] as ScheduledPost[]),
        draftsApi.list("pending_approval").catch(() => ({ items: [] })),
        inboxApi.stats().catch(() => null),
        automationApi.list().catch(() => [] as Rule[]),
        billingApi.plan().catch(() => null),
      ]);
      setSummary(s);
      setTimeline(t);
      setEngagement(e);
      setTop(tp.posts);
      setBestTimes(bt);
      setOauth(oa);
      setSchedules(sc);
      setPendingDrafts(pd.items);
      setInboxStats(is);
      setAutomationRules(ar);
      setPlanInfo(pi);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load dashboard");
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  const connectedCount = useMemo(
    () => Object.values(oauth).filter(Boolean).length,
    [oauth],
  );

  const totalEngagement = engagement
    ? engagement.totals.likes +
      engagement.totals.comments +
      engagement.totals.shares
    : 0;

  const insights = useMemo(
    () => buildInsights({ summary, engagement, bestTimes, connectedCount }),
    [summary, engagement, bestTimes, connectedCount],
  );

  const upcomingSchedules = useMemo(
    () =>
      schedules
        .filter((s) => s.enabled && s.next_run_at)
        .sort(
          (a, b) =>
            new Date(a.next_run_at!).getTime() -
            new Date(b.next_run_at!).getTime(),
        )
        .slice(0, 5),
    [schedules],
  );

  const pendingDraftCount = pendingDrafts.length;

  const totalUnread =
    inboxStats?.total_unread ?? inboxStats?.total_unread_messages ?? 0;

  const enabledRuleCount = useMemo(
    () => automationRules.filter((r) => r.enabled).length,
    [automationRules],
  );

  const recentlyTriggeredCount = useMemo(
    () =>
      automationRules.filter((r) => {
        if (!r.last_triggered_at) return false;
        const hoursAgo =
          (Date.now() - new Date(r.last_triggered_at).getTime()) / 36e5;
        return hoursAgo < 24;
      }).length,
    [automationRules],
  );

  const isFree = planInfo?.plan === "free";

  const noActivity =
    !loading &&
    summary?.total === 0 &&
    Object.keys(oauth).length > 0 &&
    connectedCount === 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Quick overview of your posting activity, engagement, and AI insights.
          </p>
        </div>
        <div className="flex gap-1 rounded-md border border-border bg-background p-1">
          {RANGE_OPTIONS.map((r) => (
            <button
              key={r.value}
              type="button"
              onClick={() => setDays(r.value)}
              className={cn(
                "h-7 rounded px-3 text-xs font-medium",
                days === r.value
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-accent",
              )}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      {isFree && !noActivity && planInfo && <UpgradeBanner planInfo={planInfo} />}

      <QuickActions />

      {noActivity && <EmptyOnboarding />}

      <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
        <Kpi
          label="Connected"
          value={connectedCount}
          icon={<Plug className="h-4 w-4" />}
          tone={connectedCount === 0 ? "warn" : "good"}
          link={connectedCount === 0 ? "/connections" : undefined}
        />
        <Kpi
          label="Posts published"
          value={summary?.total ?? "—"}
          icon={<Activity className="h-4 w-4" />}
        />
        <Kpi
          label="Success rate"
          value={summary ? `${summary.success_rate}%` : "—"}
          icon={<CheckCircle2 className="h-4 w-4" />}
          tone={
            summary && summary.total === 0
              ? "neutral"
              : summary && summary.success_rate >= 95
                ? "good"
                : summary && summary.success_rate < 80
                  ? "warn"
                  : "neutral"
          }
        />
        <Kpi
          label="Top platform"
          value={summary?.top_platform || "—"}
          icon={<TrendingUp className="h-4 w-4" />}
        />
        <Kpi
          label="Engagements"
          value={engagement ? totalEngagement.toLocaleString() : "—"}
          icon={<Heart className="h-4 w-4" />}
        />
      </div>

      <Card
        title="AI insights"
        subtitle="Auto-generated from your activity"
        icon={<Sparkles className="h-4 w-4 text-primary" />}
      >
        {insights.length === 0 ? (
          <Empty hint="Insights will appear once you publish a few posts." />
        ) : (
          <ul className="space-y-2">
            {insights.map((i, idx) => (
              <li
                key={idx}
                className="flex items-start gap-2 rounded-md border border-border bg-muted/20 px-3 py-2 text-sm"
              >
                <Sparkles className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />
                <span>{i}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <InfoCard
          label="Upcoming schedules"
          value={upcomingSchedules.length}
          icon={<Calendar className="h-4 w-4" />}
          to="/schedules"
        />
        <InfoCard
          label="Pending approval"
          value={pendingDraftCount}
          icon={<FileText className="h-4 w-4" />}
          tone={pendingDraftCount > 0 ? "warn" : "neutral"}
          to="/drafts"
        />
        <InfoCard
          label="Unread inbox"
          value={totalUnread}
          icon={<MessageSquare className="h-4 w-4" />}
          tone={totalUnread > 0 ? "warn" : "neutral"}
          to="/inbox"
        />
        <InfoCard
          label="Active rules"
          value={enabledRuleCount}
          icon={<Zap className="h-4 w-4" />}
          subtitle={
            recentlyTriggeredCount > 0
              ? `${recentlyTriggeredCount} triggered recently`
              : undefined
          }
          to="/automation"
        />
      </div>

      <Card title="Posting timeline" subtitle={`Last ${days} days`}>
        {!timeline ? (
          <Loading />
        ) : timeline.timeline.every((p) => p.count === 0) ? (
          <Empty
            hint="No posts in this range yet."
            cta={{ label: "Compose your first post", to: "/compose" }}
          />
        ) : (
          <TimelineChart timeline={timeline} />
        )}
      </Card>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card title="Platform breakdown" subtitle={`Last ${days} days`}>
          {!summary ||
          Object.keys(summary.platform_breakdown ?? {}).length === 0 ? (
            <Empty hint="No platforms posted to yet." />
          ) : (
            <PlatformBreakdown breakdown={summary.platform_breakdown} />
          )}
        </Card>

        <Card title="Top posts" subtitle="Highest engagement">
          {top.length === 0 ? (
            <Empty hint="Top posts appear after engagement metrics are fetched." />
          ) : (
            <TopPostsList posts={top.slice(0, 5)} />
          )}
        </Card>
      </div>
    </div>
  );
}

function buildInsights({
  summary,
  engagement,
  bestTimes,
  connectedCount,
}: {
  summary: Summary | null;
  engagement: Engagement | null;
  bestTimes: BestTimes | null;
  connectedCount: number;
}): string[] {
  const out: string[] = [];

  if (connectedCount === 0) {
    out.push(
      "You have no platforms connected yet. Connect at least one to start posting.",
    );
  }

  if (summary && summary.total > 0) {
    out.push(
      `You published ${summary.total} post${summary.total === 1 ? "" : "s"} with a ${summary.success_rate}% success rate over the last ${summary.days} days.`,
    );
  }

  if (summary?.top_platform) {
    out.push(
      `${platformLabel(summary.top_platform)} is your most active platform — keep the cadence going.`,
    );
  }

  if (engagement) {
    const entries = Object.entries(engagement.platforms);
    if (entries.length > 1) {
      const sorted = entries
        .map(([p, v]) => ({
          p,
          score: v.likes + v.comments + v.shares,
          rate: v.avg_engagement_rate,
        }))
        .sort((a, b) => b.score - a.score);
      const winner = sorted[0];
      if (winner.score > 0) {
        out.push(
          `${platformLabel(winner.p)} drives the most engagement (${winner.score.toLocaleString()} interactions, ${winner.rate.toFixed(2)}% avg rate).`,
        );
      }
    }
  }

  if (bestTimes && bestTimes.hours.length > 0) {
    const best = bestTimes.hours[0];
    if (best.avg_engagement_rate > 0) {
      const hourLabel = formatHour(best.hour);
      out.push(
        `Best time to post: around ${hourLabel} (avg engagement rate ${best.avg_engagement_rate.toFixed(2)}%).`,
      );
    }
  }

  return out;
}

function formatHour(h: number): string {
  if (h === 0) return "12 AM";
  if (h < 12) return `${h} AM`;
  if (h === 12) return "12 PM";
  return `${h - 12} PM`;
}

function Kpi({
  label,
  value,
  icon,
  tone = "neutral",
  link,
}: {
  label: string;
  value: string | number;
  icon: React.ReactNode;
  tone?: "neutral" | "good" | "warn";
  link?: string;
}) {
  const toneClass = {
    neutral: "text-foreground",
    good: "text-emerald-600",
    warn: "text-amber-600",
  }[tone];

  const inner = (
    <div className="rounded-lg border border-border bg-background p-4 transition-colors hover:bg-accent/30">
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>{label}</span>
        <span className="text-muted-foreground/60">{icon}</span>
      </div>
      <div className={cn("mt-2 text-2xl font-semibold tracking-tight capitalize", toneClass)}>
        {value}
      </div>
    </div>
  );

  return link ? (
    <Link to={link} className="block">
      {inner}
    </Link>
  ) : (
    inner
  );
}

function Card({
  title,
  subtitle,
  icon,
  children,
}: {
  title: string;
  subtitle?: string;
  icon?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-lg border border-border bg-background">
      <header className="flex items-center gap-2 border-b border-border px-5 py-3">
        {icon}
        <div>
          <h2 className="text-sm font-semibold">{title}</h2>
          {subtitle && (
            <p className="text-xs text-muted-foreground">{subtitle}</p>
          )}
        </div>
      </header>
      <div className="p-5">{children}</div>
    </section>
  );
}

function Loading() {
  return (
    <div className="py-8 text-center text-sm text-muted-foreground">
      Loading…
    </div>
  );
}

function Empty({
  hint,
  cta,
}: {
  hint: string;
  cta?: { label: string; to: string };
}) {
  return (
    <div className="flex flex-col items-center gap-3 py-8 text-sm text-muted-foreground">
      <span>{hint}</span>
      {cta && (
        <Link
          to={cta.to}
          className="inline-flex items-center gap-1 rounded-md border border-border bg-background px-3 py-1.5 text-xs font-medium text-foreground hover:bg-accent"
        >
          {cta.label}
          <ArrowUpRight className="h-3 w-3" />
        </Link>
      )}
    </div>
  );
}

function EmptyOnboarding() {
  return (
    <div className="rounded-lg border border-dashed border-border bg-muted/20 p-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3">
          <div className="grid h-10 w-10 shrink-0 place-items-center rounded-md bg-primary/10 text-primary">
            <Sparkles className="h-5 w-5" />
          </div>
          <div>
            <p className="font-medium">Welcome — let's get you posting.</p>
            <p className="text-sm text-muted-foreground">
              Connect a social account, then compose your first post.
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            to="/connections"
            className="inline-flex items-center gap-1 rounded-md bg-primary px-3 py-2 text-xs font-medium text-primary-foreground hover:bg-primary/90"
          >
            <Plug className="h-3.5 w-3.5" />
            Connect your first account
          </Link>
          <Link
            to="/compose"
            className="inline-flex items-center gap-1 rounded-md border border-border bg-background px-3 py-2 text-xs font-medium hover:bg-accent"
          >
            <Sparkles className="h-3.5 w-3.5" />
            Generate your first AI post
          </Link>
        </div>
      </div>
    </div>
  );
}

function TimelineChart({ timeline }: { timeline: Timeline }) {
  const points = timeline.timeline;
  const max = Math.max(1, ...points.map((p) => p.count));
  const W = 800;
  const H = 200;
  const padX = 28;
  const padY = 24;
  const innerW = W - padX * 2;
  const innerH = H - padY * 2;

  const yTicks = [0, 0.25, 0.5, 0.75, 1].map((f) => Math.round(max * f));

  const pathD = points
    .map((p, i) => {
      const x = padX + (i / Math.max(1, points.length - 1)) * innerW;
      const y = padY + innerH - (p.count / max) * innerH;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  const areaD =
    points.length > 0
      ? `${pathD} L${(padX + innerW).toFixed(1)},${(padY + innerH).toFixed(1)} L${padX.toFixed(1)},${(padY + innerH).toFixed(1)} Z`
      : "";

  const labels: Array<{ x: number; date: string }> = [];
  if (points.length > 0) {
    labels.push({ x: padX, date: points[0].date });
    if (points.length > 2) {
      const mid = Math.floor(points.length / 2);
      const x = padX + (mid / Math.max(1, points.length - 1)) * innerW;
      labels.push({ x, date: points[mid].date });
    }
    labels.push({
      x: padX + innerW,
      date: points[points.length - 1].date,
    });
  }

  return (
    <div className="overflow-hidden">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="h-48 w-full"
        preserveAspectRatio="none"
        role="img"
        aria-label="Posts per day"
      >
        {yTicks.map((t, i) => {
          const y = padY + innerH - (t / max) * innerH;
          return (
            <g key={i}>
              <line
                x1={padX}
                x2={W - padX}
                y1={y}
                y2={y}
                stroke="currentColor"
                strokeWidth={1}
                className="text-border"
              />
              <text
                x={padX - 4}
                y={y}
                textAnchor="end"
                dominantBaseline="middle"
                className="fill-muted-foreground text-[10px]"
              >
                {t}
              </text>
            </g>
          );
        })}

        {areaD && (
          <path d={areaD} className="fill-primary/10" />
        )}
        {pathD && (
          <path
            d={pathD}
            fill="none"
            strokeWidth={2}
            className="stroke-primary"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        )}
        {points.map((p, i) => {
          const x = padX + (i / Math.max(1, points.length - 1)) * innerW;
          const y = padY + innerH - (p.count / max) * innerH;
          if (p.count === 0) return null;
          return (
            <circle
              key={p.date}
              cx={x}
              cy={y}
              r={2.5}
              className="fill-primary"
            >
              <title>
                {p.date}: {p.count} post{p.count === 1 ? "" : "s"}
              </title>
            </circle>
          );
        })}

        {labels.map((l) => (
          <text
            key={l.date}
            x={l.x}
            y={H - 4}
            textAnchor="middle"
            className="fill-muted-foreground text-[10px]"
          >
            {l.date.slice(5)}
          </text>
        ))}
      </svg>
    </div>
  );
}

function PlatformBreakdown({
  breakdown,
}: {
  breakdown: Record<string, number>;
}) {
  const entries = Object.entries(breakdown).sort((a, b) => b[1] - a[1]);
  const total = entries.reduce((sum, [, n]) => sum + n, 0);

  return (
    <div className="space-y-3">
      <div className="flex h-3 overflow-hidden rounded-full bg-muted">
        {entries.map(([platform, count]) => {
          const pct = total > 0 ? (count / total) * 100 : 0;
          if (pct === 0) return null;
          return (
            <div
              key={platform}
              style={{
                width: `${pct}%`,
                background: platformBrand(platform).bg,
              }}
              title={`${platformLabel(platform)}: ${count}`}
            />
          );
        })}
      </div>
      <ul className="space-y-2">
        {entries.map(([platform, count]) => {
          const pct = total > 0 ? (count / total) * 100 : 0;
          return (
            <li
              key={platform}
              className="flex items-center justify-between text-sm"
            >
              <PlatformBadge platform={platform} variant="dot" />
              <span className="tabular-nums text-muted-foreground">
                {count} <span className="text-xs">({pct.toFixed(0)}%)</span>
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function UpgradeBanner({ planInfo }: { planInfo: PlanInfo }) {
  const freeLimits = planInfo.limits.free;
  return (
    <div className="flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="flex-1">
        <p className="font-medium">Free plan</p>
        <p className="mt-0.5 text-amber-800">
          {freeLimits.platform_connections >= 0 &&
            `${freeLimits.platform_connections} platform connection${freeLimits.platform_connections === 1 ? "" : "s"} • `}
          {freeLimits.scheduled_posts >= 0 &&
            `${freeLimits.scheduled_posts} scheduled post${freeLimits.scheduled_posts === 1 ? "" : "s"} • `}
          <Link
            to="/settings/billing"
            className="font-medium underline underline-offset-2 hover:text-amber-950"
          >
            Upgrade to Pro
          </Link>
        </p>
      </div>
    </div>
  );
}

function QuickActions() {
  const actions = [
    { label: "New post", icon: Send, to: "/compose" },
    { label: "Schedule", icon: Calendar, to: "/schedules" },
    { label: "Create draft", icon: FileText, to: "/drafts" },
    { label: "Connect platform", icon: Plug, to: "/connections" },
  ];
  return (
    <div className="flex flex-wrap gap-2">
      {actions.map((a) => (
        <Link
          key={a.to}
          to={a.to}
          className="inline-flex h-9 items-center gap-1.5 rounded-md border border-border bg-background px-3 text-sm font-medium hover:bg-accent"
        >
          <a.icon className="h-3.5 w-3.5" />
          {a.label}
        </Link>
      ))}
    </div>
  );
}

function InfoCard({
  label,
  value,
  icon,
  tone = "neutral",
  subtitle,
  to,
}: {
  label: string;
  value: string | number;
  icon: React.ReactNode;
  tone?: "neutral" | "good" | "warn";
  subtitle?: string;
  to: string;
}) {
  const toneClass = {
    neutral: "text-foreground",
    good: "text-emerald-600",
    warn: "text-amber-600",
  }[tone];
  return (
    <Link
      to={to}
      className="block rounded-lg border border-border bg-background p-4 transition-colors hover:bg-accent/30"
    >
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>{label}</span>
        <span className="text-muted-foreground/60">{icon}</span>
      </div>
      <div
        className={cn("mt-2 text-2xl font-semibold tracking-tight", toneClass)}
      >
        {value}
      </div>
      {subtitle && (
        <p className="mt-0.5 text-xs text-muted-foreground">{subtitle}</p>
      )}
    </Link>
  );
}

function TopPostsList({ posts }: { posts: TopPost[] }) {
  return (
    <ol className="space-y-3">
      {posts.map((p, i) => (
        <li
          key={`${p.platform}-${i}`}
          className="flex items-start gap-3 border-b border-border pb-3 last:border-b-0 last:pb-0"
        >
          <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-primary/10 text-[11px] font-semibold text-primary">
            {i + 1}
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <PlatformBadge platform={p.platform} />
              {p.published_at && (
                <span className="inline-flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  {new Date(p.published_at).toLocaleDateString()}
                </span>
              )}
            </div>
            <p className="mt-1 line-clamp-2 text-sm">{p.text_preview}</p>
            <div className="mt-1 flex items-center gap-3 text-xs text-muted-foreground">
              <span>♥ {p.likes}</span>
              <span>💬 {p.comments}</span>
              <span>↗ {p.shares}</span>
              <span>{p.engagement_rate.toFixed(2)}%</span>
              {p.post_url && (
                <a
                  href={p.post_url}
                  target="_blank"
                  rel="noreferrer"
                  className="ml-auto inline-flex items-center gap-1 text-primary hover:underline"
                >
                  Open <ExternalLink className="h-3 w-3" />
                </a>
              )}
            </div>
          </div>
        </li>
      ))}
    </ol>
  );
}
