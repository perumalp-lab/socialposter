import { api } from "./api";

export type InboxComment = {
  id: number;
  platform: string;
  author_name: string;
  author_avatar_url: string | null;
  text: string;
  is_read: boolean;
  platform_post_url: string | null;
  posted_at: string | null;
  fetched_at: string | null;
};

export type InboxList = {
  items: InboxComment[];
  page: number;
  per_page: number;
  total: number;
  pages: number;
};

export type InboxStats = {
  unread: Record<string, number>;
  total_unread: number;
  unread_messages: Record<string, number>;
  total_unread_messages: number;
};

export type ConversationListItem = {
  id: number;
  platform: string;
  platform_thread_id: string;
  participant_id: string;
  participant_name: string;
  participant_avatar_url: string | null;
  last_message_text: string;
  last_message_at: string | null;
  unread_count: number;
  created_at: string | null;
};

export type ConversationList = {
  items: ConversationListItem[];
  page: number;
  per_page: number;
  total: number;
  pages: number;
};

export type MessageItem = {
  id: number;
  platform_message_id: string | null;
  direction: "in" | "out";
  sender_type: "customer" | "user" | "ai";
  sender_name: string;
  text: string;
  sent_at: string | null;
};

export type ConversationDetail = {
  conversation: {
    id: number;
    platform: string;
    participant_name: string;
    participant_avatar_url: string | null;
    platform_thread_id: string;
  };
  items: MessageItem[];
};

export const inboxApi = {
  list: (params: { page?: number; platform?: string; isRead?: boolean | "" } = {}) =>
    api.get<InboxList>("/api/inbox/comments", {
      query: {
        page: params.page,
        platform: params.platform || undefined,
        is_read:
          params.isRead === true
            ? "true"
            : params.isRead === false
              ? "false"
              : undefined,
      },
    }),
  stats: () => api.get<InboxStats>("/api/inbox/stats"),
  markRead: (id: number) =>
    api.post<{ ok: true }>(`/api/inbox/comments/${id}/read`),
  bulkMarkRead: (ids?: number[]) =>
    api.post<{ ok: true }>("/api/inbox/comments/mark-read", {
      ids: ids ?? [],
    }),
  reply: (id: number, text: string) =>
    api.post<{ ok: true }>(`/api/inbox/comments/${id}/reply`, { text }),
  aiSuggest: (
    id: number,
    body: { tone?: string; provider?: string; model?: string } = {},
  ) => api.post<{ text: string }>(`/api/inbox/comments/${id}/ai-suggest`, body),
  conversations: (params: { page?: number; platform?: string } = {}) =>
    api.get<ConversationList>("/api/inbox/conversations", {
      query: {
        page: params.page,
        platform: params.platform || undefined,
      },
    }),
  conversationMessages: (id: number) =>
    api.get<ConversationDetail>(`/api/inbox/conversations/${id}/messages`),
  conversationReply: (id: number, text: string) =>
    api.post<{ ok: true; message: MessageItem }>(
      `/api/inbox/conversations/${id}/reply`,
      { text },
    ),
  conversationAiSuggest: (
    id: number,
    body: { tone?: string; provider?: string; model?: string } = {},
  ) =>
    api.post<{ text: string }>(
      `/api/inbox/conversations/${id}/ai-suggest`,
      body,
    ),
};
