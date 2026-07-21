import { api } from "./api";

export type Summary = {
  total: number;
  successes: number;
  success_rate: number;
  top_platform: string;
  platform_breakdown: Record<string, number>;
  days: number;
};

export type TimelinePoint = { date: string; count: number };
export type Timeline = { timeline: TimelinePoint[]; days: number };

export type HistoryItem = {
  id: number;
  platform: string;
  text: string;
  success: boolean;
  post_url: string | null;
  error_message: string | null;
  created_at: string | null;
};

export type HistoryList = {
  items: HistoryItem[];
  page: number;
  per_page: number;
  total: number;
  pages: number;
};

export type EngagementPlatform = {
  likes: number;
  comments: number;
  shares: number;
  views: number;
  clicks: number;
  avg_engagement_rate: number;
  count: number;
};

export type Engagement = {
  platforms: Record<string, EngagementPlatform>;
  totals: Omit<EngagementPlatform, "avg_engagement_rate" | "count">;
  days: number;
};

export type TopPost = {
  platform: string;
  text_preview: string;
  post_url: string | null;
  likes: number;
  comments: number;
  shares: number;
  views: number;
  engagement_rate: number;
  published_at: string | null;
};

export type BestTimes = {
  hours: Array<{ hour: number; post_count: number; avg_engagement_rate: number }>;
};

export type Heatmap = {
  cells: Array<{ weekday: number; hour: number; count: number }>;
  days: number;
};

export const analyticsApi = {
  summary: (days: number) =>
    api.get<Summary>("/api/analytics/summary", { query: { days } }),
  timeline: (days: number) =>
    api.get<Timeline>("/api/analytics/timeline", { query: { days } }),
  engagement: (days: number) =>
    api.get<Engagement>("/api/analytics/engagement", { query: { days } }),
  topPosts: (days: number) =>
    api.get<{ posts: TopPost[]; days: number }>("/api/analytics/top-posts", {
      query: { days },
    }),
  bestTimes: () => api.get<BestTimes>("/api/analytics/best-times"),
  heatmap: (days: number) =>
    api.get<Heatmap>("/api/analytics/heatmap", { query: { days } }),
  history: (params: {
    page?: number;
    platform?: string;
    success?: boolean | "";
  } = {}) =>
    api.get<HistoryList>("/api/analytics/history", {
      query: {
        page: params.page,
        platform: params.platform || undefined,
        success:
          params.success === true
            ? "true"
            : params.success === false
              ? "false"
              : undefined,
      },
    }),
};
