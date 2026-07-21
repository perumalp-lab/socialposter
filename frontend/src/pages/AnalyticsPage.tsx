import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  Heart,
  TrendingUp,
  XCircle,
} from "lucide-react";
import { ApiError } from "@/lib/api";
import {
  analyticsApi,
  type Engagement,
  type Heatmap,
  type HistoryItem,
  type HistoryList,
  type Summary,
  type Timeline,
  type TopPost,
} from "@/lib/analytics";
import { cn } from "@/lib/utils";
import { PlatformBadge } from "@/components/PlatformBadge";
import { platformBrand, platformLabel } from "@/lib/platformColors";

const RANGE_OPTIONS = [
  { label: "7d", value: 7 },
  { label: "30d", value: 30 },
  { label: "90d", value: 90 },
] as const;

type Level = "basic" | "mid" | "advanced";

const LEVEL_OPTIONS: Array<{
  label: string;
  value: Level;
  hint: string;
}> = [
  { label: "Basic", value: "basic", hint: "Counts & success" },
  { label: "Mid", value: "mid", hint: "+ Engagement & best time" },
  { label: "Advanced", value: "advanced", hint: "+ Top posts & history" },
];

const LEVEL_RANK: Record<Level, number> = { basic: 0, mid: 1, advanced: 2 };
const ANALYTICS_LEVEL_KEY = "sp.analytics.level";

export function AnalyticsPage() {
  const [days, setDays] = useState<number>(30);
  const [level, setLevel] = useState<Level>(() => {
    if (typeof window === "undefined") return "mid";
    const stored = window.localStorage.getItem(ANALYTICS_LEVEL_KEY);
    return stored === "basic" || stored === "advanced" ? stored : "mid";
  });

  useEffect(() => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(ANALYTICS_LEVEL_KEY, level);
    }
  }, [level]);

  const showAtLeast = (min: Level) => LEVEL_RANK[level] >= LEVEL_RANK[min];

  const [summary, setSummary] = useState<Summary | null>(null);
  const [timeline, setTimeline] = useState<Timeline | null>(null);
  const [engagement, setEngagement] = useState<Engagement | null>(null);
  const [top, setTop] = useState<TopPost[]>([]);
  const [heatmap, setHeatmap] = useState<Heatmap | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, t, e, tp, hm] = await Promise.all([
        analyticsApi.summary(days),
        analyticsApi.timeline(days),
        analyticsApi.engagement(days),
        analyticsApi.topPosts(days),
        analyticsApi
          .heatmap(days)
          .catch(() => ({ cells: [], days }) as Heatmap),
      ]);
      setSummary(s);
      setTimeline(t);
      setEngagement(e);
      setTop(tp.posts);
      setHeatmap(hm);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load analytics");
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  const totalEngagement = engagement
    ? engagement.totals.likes +
      engagement.totals.comments +
      engagement.totals.shares
    : 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Analytics</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Reach, engagement, and posting health across your platforms.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div
            className="flex gap-1 rounded-md border border-border bg-background p-1"
            role="group"
            aria-label="Detail level"
          >
            {LEVEL_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setLevel(opt.value)}
                title={opt.hint}
                className={cn(
                  "h-7 rounded px-3 text-xs font-medium",
                  level === opt.value
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-accent",
                )}
              >
                {opt.label}
              </button>
            ))}
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
      </div>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
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
            summary && summary.success_rate >= 95
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

      <Card title="Posting timeline" subtitle={`Last ${days} days`}>
        {loading && !timeline ? (
          <Loading />
        ) : !timeline || timeline.timeline.every((p) => p.count === 0) ? (
          <Empty hint="No posts in this range yet." />
        ) : (
          <TimelineChart timeline={timeline} />
        )}
      </Card>

      {showAtLeast("mid") && (
        <Card title="Platform comparison" subtitle="Engagement by platform">
          {!engagement || Object.keys(engagement.platforms).length === 0 ? (
            <Empty hint="No engagement metrics fetched yet." />
          ) : (
            <PlatformComparison engagement={engagement} />
          )}
        </Card>
      )}

      <div
        className={cn(
          "grid grid-cols-1 gap-4",
          showAtLeast("advanced") && "lg:grid-cols-2",
        )}
      >
        {showAtLeast("mid") && (
          <Card title="Engagement by platform" subtitle={`Last ${days} days`}>
            {!engagement ? (
              <Loading />
            ) : Object.keys(engagement.platforms).length === 0 ? (
              <Empty hint="No engagement metrics fetched yet." />
            ) : (
              <EngagementTable engagement={engagement} />
            )}
          </Card>
        )}

        {showAtLeast("advanced") && (
          <Card title="Top posts" subtitle={`By total engagement`}>
            {top.length === 0 ? (
              <Empty hint="No top posts yet." />
            ) : (
              <TopPostsList posts={top} />
            )}
          </Card>
        )}
      </div>

      {showAtLeast("mid") && (
        <Card
          title="Best time to post"
          subtitle="Posting frequency by weekday × hour"
        >
          {!heatmap || heatmap.cells.length === 0 ? (
            <Empty hint="Heatmap appears once you have published posts." />
          ) : (
            <PostingHeatmap heatmap={heatmap} />
          )}
        </Card>
      )}

      {showAtLeast("advanced") && (
        <Card title="History" subtitle="Every publish attempt, newest first">
          <HistorySection />
        </Card>
      )}
    </div>
  );
}

function Kpi({
  label,
  value,
  icon,
  tone = "neutral",
}: {
  label: string;
  value: string | number;
  icon: React.ReactNode;
  tone?: "neutral" | "good" | "warn";
}) {
  const toneClass = {
    neutral: "text-foreground",
    good: "text-emerald-600",
    warn: "text-amber-600",
  }[tone];
  return (
    <div className="rounded-lg border border-border bg-background p-4">
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>{label}</span>
        <span className="text-muted-foreground/60">{icon}</span>
      </div>
      <div className={cn("mt-2 text-2xl font-semibold tracking-tight capitalize", toneClass)}>
        {value}
      </div>
    </div>
  );
}

function Card({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-lg border border-border bg-background">
      <header className="border-b border-border px-5 py-3">
        <h2 className="text-sm font-semibold">{title}</h2>
        {subtitle && (
          <p className="text-xs text-muted-foreground">{subtitle}</p>
        )}
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

function Empty({ hint }: { hint: string }) {
  return (
    <div className="py-8 text-center text-sm text-muted-foreground">{hint}</div>
  );
}

function TimelineChart({ timeline }: { timeline: Timeline }) {
  // Inline SVG bar chart; widthless via viewBox, scales to container.
  const points = timeline.timeline;
  const max = Math.max(1, ...points.map((p) => p.count));
  const W = 800;
  const H = 200;
  const padX = 24;
  const padY = 24;
  const innerW = W - padX * 2;
  const innerH = H - padY * 2;
  const slot = innerW / Math.max(1, points.length);
  const barW = Math.max(2, slot * 0.6);

  const yTicks = [0, 0.25, 0.5, 0.75, 1].map((f) => Math.round(max * f));

  // Sample x labels: first, middle, last.
  const labels: Array<{ x: number; date: string }> = [];
  if (points.length > 0) {
    labels.push({ x: padX + slot / 2, date: points[0].date });
    if (points.length > 2) {
      const mid = Math.floor(points.length / 2);
      labels.push({ x: padX + slot * mid + slot / 2, date: points[mid].date });
    }
    labels.push({
      x: padX + slot * (points.length - 1) + slot / 2,
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
        {/* y-grid */}
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

        {/* bars */}
        {points.map((p, i) => {
          const x = padX + i * slot + (slot - barW) / 2;
          const h = (p.count / max) * innerH;
          const y = padY + innerH - h;
          return (
            <g key={p.date}>
              <rect
                x={x}
                y={y}
                width={barW}
                height={Math.max(0, h)}
                rx={2}
                className={cn(
                  "fill-primary/80",
                  p.count === 0 && "fill-muted",
                )}
              >
                <title>
                  {p.date}: {p.count} post{p.count === 1 ? "" : "s"}
                </title>
              </rect>
            </g>
          );
        })}

        {/* x labels */}
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

function EngagementTable({ engagement }: { engagement: Engagement }) {
  const rows = Object.entries(engagement.platforms);
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs text-muted-foreground">
            <th className="px-2 py-2 font-medium">Platform</th>
            <th className="px-2 py-2 font-medium text-right">Likes</th>
            <th className="px-2 py-2 font-medium text-right">Comments</th>
            <th className="px-2 py-2 font-medium text-right">Shares</th>
            <th className="px-2 py-2 font-medium text-right">Views</th>
            <th className="px-2 py-2 font-medium text-right">Avg rate</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([platform, p]) => (
            <tr key={platform} className="border-b border-border last:border-b-0">
              <td className="px-2 py-2 text-sm font-medium">
                <PlatformBadge platform={platform} variant="dot" />
              </td>
              <td className="px-2 py-2 text-right tabular-nums">
                {p.likes.toLocaleString()}
              </td>
              <td className="px-2 py-2 text-right tabular-nums">
                {p.comments.toLocaleString()}
              </td>
              <td className="px-2 py-2 text-right tabular-nums">
                {p.shares.toLocaleString()}
              </td>
              <td className="px-2 py-2 text-right tabular-nums">
                {p.views.toLocaleString()}
              </td>
              <td className="px-2 py-2 text-right tabular-nums">
                {p.avg_engagement_rate.toFixed(2)}%
              </td>
            </tr>
          ))}
          <tr className="border-t-2 border-border bg-muted/30 font-medium">
            <td className="px-2 py-2 text-sm">Total</td>
            <td className="px-2 py-2 text-right tabular-nums">
              {engagement.totals.likes.toLocaleString()}
            </td>
            <td className="px-2 py-2 text-right tabular-nums">
              {engagement.totals.comments.toLocaleString()}
            </td>
            <td className="px-2 py-2 text-right tabular-nums">
              {engagement.totals.shares.toLocaleString()}
            </td>
            <td className="px-2 py-2 text-right tabular-nums">
              {engagement.totals.views.toLocaleString()}
            </td>
            <td className="px-2 py-2 text-right text-muted-foreground">—</td>
          </tr>
        </tbody>
      </table>
    </div>
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
                <span>{new Date(p.published_at).toLocaleDateString()}</span>
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

function HistorySection() {
  const [data, setData] = useState<HistoryList | null>(null);
  const [page, setPage] = useState(1);
  const [platform, setPlatform] = useState("");
  const [success, setSuccess] = useState<"" | "true" | "false">("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await analyticsApi.history({
        page,
        platform: platform || undefined,
        success:
          success === "true" ? true : success === "false" ? false : "",
      });
      setData(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load history");
    } finally {
      setLoading(false);
    }
  }, [page, platform, success]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    setPage(1);
  }, [platform, success]);

  const platformOptions = useMemo(() => {
    if (!data) return [];
    return Array.from(new Set(data.items.map((h) => h.platform))).sort();
  }, [data]);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <select
          value={platform}
          onChange={(e) => setPlatform(e.target.value)}
          className="h-8 rounded-md border border-input bg-background px-2 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="">All platforms</option>
          {platformOptions.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
        <select
          value={success}
          onChange={(e) =>
            setSuccess(e.target.value as "" | "true" | "false")
          }
          className="h-8 rounded-md border border-input bg-background px-2 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="">All statuses</option>
          <option value="true">Successful</option>
          <option value="false">Failed</option>
        </select>
      </div>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      {loading && !data ? (
        <div className="py-6 text-center text-sm text-muted-foreground">
          Loading…
        </div>
      ) : !data || data.items.length === 0 ? (
        <Empty hint="No publish attempts in this view." />
      ) : (
        <ul className="divide-y divide-border">
          {data.items.map((h) => (
            <HistoryRow key={h.id} item={h} />
          ))}
        </ul>
      )}

      {data && data.pages > 1 && (
        <div className="flex items-center justify-end gap-2 text-sm">
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
            className="grid h-8 w-8 place-items-center rounded-md hover:bg-accent disabled:opacity-40"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <span className="text-muted-foreground">
            Page {data.page} of {data.pages}
          </span>
          <button
            type="button"
            disabled={page >= data.pages}
            onClick={() => setPage((p) => p + 1)}
            className="grid h-8 w-8 place-items-center rounded-md hover:bg-accent disabled:opacity-40"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      )}
    </div>
  );
}

function PlatformComparison({ engagement }: { engagement: Engagement }) {
  const entries = Object.entries(engagement.platforms);
  if (entries.length === 0) return null;

  const rows = entries.map(([platform, p]) => ({
    platform,
    likes: p.likes,
    comments: p.comments,
    shares: p.shares,
    total: p.likes + p.comments + p.shares,
    rate: p.avg_engagement_rate,
  }));
  const maxTotal = Math.max(1, ...rows.map((r) => r.total));

  return (
    <div className="space-y-3">
      {rows
        .sort((a, b) => b.total - a.total)
        .map((r) => {
          const brand = platformBrand(r.platform);
          const widthPct = (r.total / maxTotal) * 100;
          const likesW = r.total > 0 ? (r.likes / r.total) * widthPct : 0;
          const commentsW = r.total > 0 ? (r.comments / r.total) * widthPct : 0;
          const sharesW = r.total > 0 ? (r.shares / r.total) * widthPct : 0;
          return (
            <div key={r.platform}>
              <div className="mb-1 flex items-center justify-between text-xs">
                <PlatformBadge platform={r.platform} variant="dot" />
                <span className="tabular-nums text-muted-foreground">
                  {r.total.toLocaleString()} interactions ·{" "}
                  {r.rate.toFixed(2)}% rate
                </span>
              </div>
              <div className="flex h-3 overflow-hidden rounded-full bg-muted">
                <div
                  style={{ width: `${likesW}%`, background: brand.bg }}
                  title={`${platformLabel(r.platform)}: ${r.likes} likes`}
                />
                <div
                  style={{
                    width: `${commentsW}%`,
                    background: brand.bg,
                    opacity: 0.65,
                  }}
                  title={`${platformLabel(r.platform)}: ${r.comments} comments`}
                />
                <div
                  style={{
                    width: `${sharesW}%`,
                    background: brand.bg,
                    opacity: 0.4,
                  }}
                  title={`${platformLabel(r.platform)}: ${r.shares} shares`}
                />
              </div>
            </div>
          );
        })}
      <div className="flex items-center gap-3 pt-1 text-[10px] text-muted-foreground">
        <span className="inline-flex items-center gap-1">
          <span className="inline-block h-2 w-3 rounded-sm bg-foreground/70" />
          Likes
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="inline-block h-2 w-3 rounded-sm bg-foreground/40" />
          Comments
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="inline-block h-2 w-3 rounded-sm bg-foreground/20" />
          Shares
        </span>
      </div>
    </div>
  );
}

const WEEKDAY_HEATMAP_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function PostingHeatmap({ heatmap }: { heatmap: Heatmap }) {
  // Build a 7×24 grid. weekday 0=Mon..6=Sun.
  const grid: number[][] = Array.from({ length: 7 }, () =>
    new Array<number>(24).fill(0),
  );
  for (const c of heatmap.cells) {
    if (c.weekday >= 0 && c.weekday < 7 && c.hour >= 0 && c.hour < 24) {
      grid[c.weekday][c.hour] += c.count;
    }
  }
  const max = Math.max(1, ...grid.flat());

  // Find the peak cell for an "best time" callout.
  let peakDow = 0;
  let peakHour = 0;
  let peakCount = 0;
  for (let d = 0; d < 7; d++) {
    for (let h = 0; h < 24; h++) {
      if (grid[d][h] > peakCount) {
        peakCount = grid[d][h];
        peakDow = d;
        peakHour = h;
      }
    }
  }

  return (
    <div className="space-y-3">
      <div className="overflow-x-auto">
        <table className="w-full border-separate border-spacing-0.5 text-[10px]">
          <thead>
            <tr>
              <th className="w-9" />
              {Array.from({ length: 24 }, (_, h) => (
                <th
                  key={h}
                  className="text-muted-foreground font-medium"
                  style={{ width: `${100 / 25}%` }}
                >
                  {h % 3 === 0 ? h : ""}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {WEEKDAY_HEATMAP_LABELS.map((day, d) => (
              <tr key={day}>
                <td className="pr-1 text-right text-muted-foreground">{day}</td>
                {Array.from({ length: 24 }, (_, h) => {
                  const count = grid[d][h];
                  const intensity = count / max;
                  return (
                    <td
                      key={h}
                      className="rounded-[2px] border border-border/40"
                      style={{
                        background:
                          count === 0
                            ? undefined
                            : `hsl(var(--primary) / ${0.15 + intensity * 0.7})`,
                        height: 20,
                      }}
                      title={`${day} ${h}:00 — ${count} post${count === 1 ? "" : "s"}`}
                    />
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {peakCount > 0 && (
        <p className="text-xs text-muted-foreground">
          Peak posting time: <span className="font-medium text-foreground">
            {WEEKDAY_HEATMAP_LABELS[peakDow]} at {formatHour12(peakHour)}
          </span>{" "}
          ({peakCount} post{peakCount === 1 ? "" : "s"} over {heatmap.days} days)
        </p>
      )}
    </div>
  );
}

function formatHour12(h: number): string {
  if (h === 0) return "12 AM";
  if (h < 12) return `${h} AM`;
  if (h === 12) return "12 PM";
  return `${h - 12} PM`;
}

function HistoryRow({ item }: { item: HistoryItem }) {
  return (
    <li className="flex items-start gap-3 py-3">
      {item.success ? (
        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
      ) : (
        <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-600" />
      )}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <PlatformBadge platform={item.platform} />
          {item.created_at && (
            <span>{new Date(item.created_at).toLocaleString()}</span>
          )}
          {item.post_url && (
            <a
              href={item.post_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-primary hover:underline"
            >
              Open <ExternalLink className="h-3 w-3" />
            </a>
          )}
        </div>
        <div className="mt-0.5 line-clamp-2 text-sm">{item.text}</div>
        {item.error_message && (
          <div className="mt-1 text-xs text-red-700">{item.error_message}</div>
        )}
      </div>
    </li>
  );
}
