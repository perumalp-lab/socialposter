import { useCallback, useEffect, useState } from "react";
import {
  CheckCheck,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  Inbox as InboxIcon,
  Loader2,
  MessageSquare,
  MessagesSquare,
  Send,
  Sparkles,
} from "lucide-react";
import { ApiError } from "@/lib/api";
import {
  inboxApi,
  type ConversationDetail,
  type ConversationList,
  type ConversationListItem,
  type InboxComment,
  type InboxList,
  type InboxStats,
} from "@/lib/inbox";
import { cn } from "@/lib/utils";
import { PlatformBadge } from "@/components/PlatformBadge";

const STATUS_TABS: Array<{
  label: string;
  value: "all" | "unread" | "read";
}> = [
  { label: "All", value: "all" },
  { label: "Unread", value: "unread" },
  { label: "Read", value: "read" },
];

type Mode = "comments" | "messages";

export function InboxPage() {
  const [mode, setMode] = useState<Mode>("comments");
  const [data, setData] = useState<InboxList | null>(null);
  const [stats, setStats] = useState<InboxStats | null>(null);
  const [page, setPage] = useState(1);
  const [platform, setPlatform] = useState("");
  const [status, setStatus] = useState<"all" | "unread" | "read">("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<InboxComment | null>(null);
  const [bulkBusy, setBulkBusy] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const isRead =
        status === "unread" ? false : status === "read" ? true : "";
      const [list, st] = await Promise.all([
        inboxApi.list({ page, platform, isRead }),
        inboxApi.stats(),
      ]);
      setData(list);
      setStats(st);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load inbox");
    } finally {
      setLoading(false);
    }
  }, [page, platform, status]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // Reset to page 1 when filters change.
  useEffect(() => {
    setPage(1);
  }, [platform, status]);

  async function open(c: InboxComment) {
    setSelected(c);
    if (!c.is_read) {
      try {
        await inboxApi.markRead(c.id);
        // Optimistic update of the list and stats.
        setData((d) =>
          d
            ? {
                ...d,
                items: d.items.map((x) =>
                  x.id === c.id ? { ...x, is_read: true } : x,
                ),
              }
            : d,
        );
        setStats((s) => {
          if (!s) return s;
          const platformUnread = Math.max(0, (s.unread[c.platform] ?? 0) - 1);
          const next = { ...s.unread };
          if (platformUnread === 0) delete next[c.platform];
          else next[c.platform] = platformUnread;
          return {
            ...s,
            unread: next,
            total_unread: Math.max(0, s.total_unread - 1),
          };
        });
      } catch {
        // Non-fatal — re-fetch on next refresh.
      }
    }
  }

  async function markAll() {
    if (!confirm("Mark every comment as read?")) return;
    setBulkBusy(true);
    try {
      await inboxApi.bulkMarkRead();
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Bulk mark-read failed");
    } finally {
      setBulkBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Inbox</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Replies, comments, and mentions across every connected platform.
          </p>
        </div>
        {stats && stats.total_unread > 0 && (
          <button
            type="button"
            onClick={() => void markAll()}
            disabled={bulkBusy}
            className="flex h-9 items-center gap-2 rounded-md border border-border px-3 text-sm font-medium hover:bg-accent disabled:opacity-60"
          >
            {bulkBusy ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <CheckCheck className="h-4 w-4" />
            )}
            Mark all read
          </button>
        )}
      </div>

      {/* Mode tabs */}
      <div
        role="tablist"
        className="inline-flex rounded-md border border-border bg-background p-1"
      >
        <ModeTab
          active={mode === "comments"}
          onClick={() => setMode("comments")}
          icon={<MessageSquare className="h-3.5 w-3.5" />}
          label="Comments"
          badge={stats?.total_unread ?? 0}
        />
        <ModeTab
          active={mode === "messages"}
          onClick={() => setMode("messages")}
          icon={<MessagesSquare className="h-3.5 w-3.5" />}
          label="Messages"
          badge={stats?.total_unread_messages ?? 0}
        />
      </div>

      {mode === "comments" && (
        <>
          {/* Stats strip */}
          <StatsStrip
            stats={stats}
            platform={platform}
            onPlatform={setPlatform}
          />

          {/* Status tabs */}
          <div className="flex flex-wrap gap-2">
            {STATUS_TABS.map((t) => (
              <button
                key={t.value}
                type="button"
                onClick={() => setStatus(t.value)}
                className={cn(
                  "h-7 rounded-full border px-3 text-xs font-medium transition-colors",
                  status === t.value
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-border text-muted-foreground hover:bg-accent",
                )}
              >
                {t.label}
              </button>
            ))}
          </div>

          {error && (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          )}

          {/* List */}
          <div className="overflow-hidden rounded-lg border border-border bg-background">
            {loading && !data ? (
              <div className="px-4 py-12 text-center text-sm text-muted-foreground">
                Loading…
              </div>
            ) : !data || data.items.length === 0 ? (
              <EmptyState />
            ) : (
              <ul className="divide-y divide-border">
                {data.items.map((c) => (
                  <CommentRow
                    key={c.id}
                    comment={c}
                    onClick={() => void open(c)}
                  />
                ))}
              </ul>
            )}
          </div>

          {data && data.pages > 1 && (
            <Pagination page={data.page} pages={data.pages} onChange={setPage} />
          )}
        </>
      )}

      {mode === "messages" && <MessagesPanel platform={platform} />}

      {selected && (
        <DetailDrawer
          comment={selected}
          onClose={() => setSelected(null)}
          onReplied={async () => {
            await refresh();
          }}
        />
      )}
    </div>
  );
}

function ModeTab({
  active,
  onClick,
  icon,
  label,
  badge,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
  badge?: number;
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={cn(
        "flex h-8 items-center gap-1.5 rounded-md px-3 text-xs font-medium transition-colors",
        active
          ? "bg-primary text-primary-foreground"
          : "text-muted-foreground hover:bg-accent",
      )}
    >
      {icon}
      {label}
      {badge !== undefined && badge > 0 && (
        <span
          className={cn(
            "ml-1 inline-flex h-4 min-w-[16px] items-center justify-center rounded-full px-1 text-[10px] font-semibold",
            active
              ? "bg-primary-foreground/20 text-primary-foreground"
              : "bg-primary text-primary-foreground",
          )}
        >
          {badge}
        </span>
      )}
    </button>
  );
}

function MessagesPanel({ platform }: { platform: string }) {
  const [list, setList] = useState<ConversationList | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [active, setActive] = useState<ConversationListItem | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await inboxApi.conversations({
        page,
        platform: platform || undefined,
      });
      setList(res);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Failed to load conversations",
      );
    } finally {
      setLoading(false);
    }
  }, [page, platform]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    setPage(1);
  }, [platform]);

  if (loading && !list) {
    return (
      <div className="rounded-lg border border-border bg-background px-4 py-12 text-center text-sm text-muted-foreground">
        Loading messages…
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
        {error}
      </div>
    );
  }

  if (!list || list.items.length === 0) {
    return (
      <div className="flex flex-col items-center gap-3 rounded-lg border border-border bg-background py-16 text-center">
        <MessagesSquare className="h-8 w-8 text-muted-foreground" />
        <p className="text-sm font-medium">No conversations yet</p>
        <p className="max-w-md text-xs text-muted-foreground">
          DM threads from WhatsApp and other platforms appear here as soon as
          inbound messages arrive via webhook.
        </p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
      <ul className="overflow-hidden rounded-lg border border-border bg-background lg:col-span-1">
        {list.items.map((c) => (
          <ConversationRow
            key={c.id}
            conversation={c}
            active={active?.id === c.id}
            onClick={() => {
              setActive(c);
              if (c.unread_count > 0) {
                setList((prev) =>
                  prev
                    ? {
                        ...prev,
                        items: prev.items.map((x) =>
                          x.id === c.id ? { ...x, unread_count: 0 } : x,
                        ),
                      }
                    : prev,
                );
              }
            }}
          />
        ))}
      </ul>
      <div className="lg:col-span-2">
        {active ? (
          <ConversationView conversationId={active.id} />
        ) : (
          <div className="rounded-lg border border-dashed border-border bg-background py-16 text-center text-sm text-muted-foreground">
            Pick a conversation on the left to read the thread.
          </div>
        )}
      </div>
    </div>
  );
}

function ConversationRow({
  conversation,
  active,
  onClick,
}: {
  conversation: ConversationListItem;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex w-full items-start gap-3 border-b border-border px-4 py-3 text-left last:border-b-0 hover:bg-accent/40",
        active && "bg-primary/[0.05]",
        !active && conversation.unread_count > 0 && "bg-primary/[0.02]",
      )}
    >
      <Avatar
        url={conversation.participant_avatar_url}
        name={conversation.participant_name}
      />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 text-sm">
          <span
            className={cn(
              "truncate",
              conversation.unread_count > 0 && "font-semibold",
            )}
          >
            {conversation.participant_name || conversation.platform_thread_id}
          </span>
          <PlatformBadge platform={conversation.platform} />
          {conversation.unread_count > 0 && (
            <span className="ml-auto inline-flex h-5 min-w-[20px] items-center justify-center rounded-full bg-primary px-1.5 text-[10px] font-semibold text-primary-foreground">
              {conversation.unread_count}
            </span>
          )}
        </div>
        <p className="mt-0.5 truncate text-xs text-muted-foreground">
          {conversation.last_message_text || "(no messages yet)"}
        </p>
        {conversation.last_message_at && (
          <p className="mt-1 text-[10px] text-muted-foreground">
            {new Date(conversation.last_message_at).toLocaleString()}
          </p>
        )}
      </div>
    </button>
  );
}

function ConversationView({ conversationId }: { conversationId: number }) {
  const [data, setData] = useState<ConversationDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [reply, setReply] = useState("");
  const [tone, setTone] = useState("friendly");
  const [sending, setSending] = useState(false);
  const [suggesting, setSuggesting] = useState(false);
  const [composeError, setComposeError] = useState<string | null>(null);

  const refreshThread = useCallback(async () => {
    try {
      const d = await inboxApi.conversationMessages(conversationId);
      setData(d);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load thread");
    }
  }, [conversationId]);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    inboxApi
      .conversationMessages(conversationId)
      .then((d) => {
        if (alive) setData(d);
      })
      .catch((err) => {
        if (alive)
          setError(
            err instanceof ApiError ? err.message : "Failed to load thread",
          );
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [conversationId]);

  useEffect(() => {
    setReply("");
    setComposeError(null);
  }, [conversationId]);

  async function send() {
    if (!reply.trim()) return;
    setSending(true);
    setComposeError(null);
    const text = reply;
    setReply("");
    try {
      const res = await inboxApi.conversationReply(conversationId, text);
      // Optimistic: append the returned outbound message.
      setData((d) =>
        d ? { ...d, items: [...d.items, res.message] } : d,
      );
    } catch (err) {
      setReply(text); // restore
      setComposeError(
        err instanceof ApiError ? err.message : "Reply failed",
      );
      // Re-fetch in case the server stored anything.
      await refreshThread();
    } finally {
      setSending(false);
    }
  }

  async function suggest() {
    if (
      reply.trim() &&
      !confirm("Replace your draft reply with the AI suggestion?")
    )
      return;
    setSuggesting(true);
    setComposeError(null);
    try {
      const { text } = await inboxApi.conversationAiSuggest(conversationId, {
        tone,
      });
      setReply(text);
    } catch (err) {
      setComposeError(
        err instanceof ApiError ? err.message : "AI suggestion failed",
      );
    } finally {
      setSuggesting(false);
    }
  }

  if (loading) {
    return (
      <div className="rounded-lg border border-border bg-background py-12 text-center text-sm text-muted-foreground">
        Loading…
      </div>
    );
  }
  if (error) {
    return (
      <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
        {error}
      </div>
    );
  }
  if (!data) return null;

  const REPLY_SUPPORTED_PLATFORMS = ["whatsapp", "twitter"] as const;
  const replySupported = (REPLY_SUPPORTED_PLATFORMS as readonly string[]).includes(
    data.conversation.platform,
  );

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-background">
      <header className="flex items-center gap-3 border-b border-border px-4 py-2.5">
        <Avatar
          url={data.conversation.participant_avatar_url}
          name={data.conversation.participant_name}
        />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 text-sm font-semibold">
            <span className="truncate">
              {data.conversation.participant_name ||
                data.conversation.platform_thread_id}
            </span>
            <PlatformBadge platform={data.conversation.platform} />
          </div>
          <p className="truncate text-[11px] text-muted-foreground">
            {data.conversation.platform_thread_id}
          </p>
        </div>
      </header>
      <ul className="space-y-2 p-4">
        {data.items.length === 0 ? (
          <li className="py-6 text-center text-sm text-muted-foreground">
            No messages in this thread yet.
          </li>
        ) : (
          data.items.map((m) => <MessageBubble key={m.id} message={m} />)
        )}
      </ul>

      <div className="border-t border-border p-3">
        {!replySupported && (
          <p className="mb-2 text-[11px] text-muted-foreground">
            Outbound replies for {data.conversation.platform} aren't wired
            yet — use the platform's app to respond.
          </p>
        )}

        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <span className="text-xs font-medium">Reply</span>
          <div className="flex items-center gap-1.5">
            <select
              value={tone}
              onChange={(e) => setTone(e.target.value)}
              className="h-7 rounded-md border border-input bg-background px-2 text-[11px] focus:outline-none focus:ring-2 focus:ring-ring"
              aria-label="AI reply tone"
            >
              <option value="friendly">Friendly</option>
              <option value="professional">Professional</option>
              <option value="empathetic">Empathetic</option>
              <option value="enthusiastic">Enthusiastic</option>
              <option value="apologetic">Apologetic</option>
              <option value="brief">Brief</option>
            </select>
            <button
              type="button"
              onClick={() => void suggest()}
              disabled={suggesting}
              className="flex h-7 items-center gap-1 rounded-md border border-border bg-background px-2 text-[11px] font-medium hover:bg-accent disabled:opacity-60"
              title="Draft a reply with AI"
            >
              {suggesting ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <Sparkles className="h-3 w-3 text-primary" />
              )}
              AI suggest
            </button>
          </div>
        </div>

        <textarea
          value={reply}
          onChange={(e) => setReply(e.target.value)}
          rows={3}
          placeholder={
            replySupported
              ? "Type your reply, or click AI suggest…"
              : "AI suggest still works — copy the draft to your platform app"
          }
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        />

        {composeError && (
          <div className="mt-2 rounded-md border border-red-200 bg-red-50 px-3 py-1.5 text-xs text-red-700">
            {composeError}
          </div>
        )}

        <div className="mt-2 flex justify-end">
          <button
            type="button"
            onClick={() => void send()}
            disabled={sending || !reply.trim() || !replySupported}
            className="flex h-8 items-center gap-1.5 rounded-md bg-primary px-3 text-xs font-medium text-primary-foreground hover:opacity-90 disabled:opacity-60"
            title={
              !replySupported
                ? `Outbound replies on ${data.conversation.platform} aren't wired yet`
                : undefined
            }
          >
            {sending ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Send className="h-3.5 w-3.5" />
            )}
            Send reply
          </button>
        </div>
      </div>
    </div>
  );
}

function MessageBubble({
  message,
}: {
  message: { direction: "in" | "out"; sender_name: string; text: string; sent_at: string | null };
}) {
  const isOut = message.direction === "out";
  return (
    <li className={cn("flex", isOut ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[80%] rounded-lg px-3 py-2 text-sm",
          isOut
            ? "bg-primary text-primary-foreground"
            : "bg-muted text-foreground",
        )}
      >
        {!isOut && message.sender_name && (
          <div className="mb-0.5 text-[11px] font-medium opacity-70">
            {message.sender_name}
          </div>
        )}
        <p className="whitespace-pre-wrap">{message.text}</p>
        {message.sent_at && (
          <div className="mt-1 text-[10px] opacity-60">
            {new Date(message.sent_at).toLocaleString()}
          </div>
        )}
      </div>
    </li>
  );
}

function StatsStrip({
  stats,
  platform,
  onPlatform,
}: {
  stats: InboxStats | null;
  platform: string;
  onPlatform: (p: string) => void;
}) {
  const entries = stats ? Object.entries(stats.unread) : [];
  const total = stats?.total_unread ?? 0;
  return (
    <div className="flex flex-wrap items-center gap-2">
      <button
        type="button"
        onClick={() => onPlatform("")}
        className={cn(
          "flex h-9 items-center gap-2 rounded-md border px-3 text-sm font-medium transition-colors",
          platform === ""
            ? "border-primary bg-primary/5 text-primary"
            : "border-border hover:bg-accent",
        )}
      >
        <InboxIcon className="h-4 w-4" />
        All
        <Badge value={total} />
      </button>
      {entries.length === 0 ? null : (
        entries.map(([p, count]) => (
          <button
            key={p}
            type="button"
            onClick={() => onPlatform(p)}
            className={cn(
              "flex h-9 items-center gap-2 rounded-md border px-3 text-sm font-medium transition-colors",
              platform === p
                ? "border-primary bg-primary/5 text-primary"
                : "border-border hover:bg-accent",
            )}
          >
            <PlatformBadge platform={p} variant="dot" />
            <Badge value={count} />
          </button>
        ))
      )}
    </div>
  );
}

function Badge({ value }: { value: number }) {
  if (!value) return null;
  return (
    <span className="inline-flex h-5 min-w-[20px] items-center justify-center rounded-full bg-primary px-1.5 text-[10px] font-semibold text-primary-foreground">
      {value}
    </span>
  );
}

function CommentRow({
  comment,
  onClick,
}: {
  comment: InboxComment;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex w-full items-start gap-3 px-4 py-3 text-left hover:bg-accent/40",
        !comment.is_read && "bg-primary/[0.03]",
      )}
    >
      <Avatar
        url={comment.author_avatar_url}
        name={comment.author_name}
      />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 text-sm">
          <span
            className={cn(
              "truncate",
              !comment.is_read && "font-semibold",
            )}
          >
            {comment.author_name || "Anonymous"}
          </span>
          <PlatformBadge platform={comment.platform} />
          {!comment.is_read && (
            <span
              aria-hidden
              className="ml-auto h-2 w-2 shrink-0 rounded-full bg-primary"
            />
          )}
        </div>
        <div className="mt-0.5 truncate text-xs text-muted-foreground">
          {comment.text}
        </div>
        {comment.posted_at && (
          <div className="mt-1 text-[10px] text-muted-foreground">
            {new Date(comment.posted_at).toLocaleString()}
          </div>
        )}
      </div>
    </button>
  );
}

function Avatar({ url, name }: { url: string | null; name: string }) {
  if (url) {
    return (
      <img
        src={url}
        alt=""
        className="h-9 w-9 shrink-0 rounded-full bg-muted object-cover"
      />
    );
  }
  const initials = (name || "?")
    .split(/\s+/)
    .map((s) => s[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase();
  return (
    <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
      {initials || "?"}
    </span>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <InboxIcon className="h-8 w-8 text-muted-foreground" />
      <p className="mt-3 text-sm font-medium">Inbox is empty</p>
      <p className="mt-1 max-w-md text-xs text-muted-foreground">
        Connect a platform and publish a post — replies and mentions will land here.
      </p>
      <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
        <a
          href="/connections"
          className="inline-flex items-center gap-1 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:opacity-90"
        >
          Connect an account
        </a>
        <a
          href="/compose"
          className="inline-flex items-center gap-1 rounded-md border border-border bg-background px-3 py-1.5 text-xs font-medium hover:bg-accent"
        >
          Compose a post
        </a>
      </div>
    </div>
  );
}

function Pagination({
  page,
  pages,
  onChange,
}: {
  page: number;
  pages: number;
  onChange: (n: number) => void;
}) {
  return (
    <div className="flex items-center justify-end gap-2 text-sm">
      <button
        type="button"
        disabled={page <= 1}
        onClick={() => onChange(page - 1)}
        className="grid h-8 w-8 place-items-center rounded-md hover:bg-accent disabled:opacity-40"
      >
        <ChevronLeft className="h-4 w-4" />
      </button>
      <span className="text-muted-foreground">
        Page {page} of {pages}
      </span>
      <button
        type="button"
        disabled={page >= pages}
        onClick={() => onChange(page + 1)}
        className="grid h-8 w-8 place-items-center rounded-md hover:bg-accent disabled:opacity-40"
      >
        <ChevronRight className="h-4 w-4" />
      </button>
    </div>
  );
}

function DetailDrawer({
  comment,
  onClose,
  onReplied,
}: {
  comment: InboxComment;
  onClose: () => void;
  onReplied: () => Promise<void>;
}) {
  const [reply, setReply] = useState("");
  const [sending, setSending] = useState(false);
  const [suggesting, setSuggesting] = useState(false);
  const [tone, setTone] = useState("friendly");
  const [msg, setMsg] = useState<string | null>(null);

  async function send() {
    if (!reply.trim()) return;
    setSending(true);
    setMsg(null);
    try {
      await inboxApi.reply(comment.id, reply);
      setReply("");
      setMsg("Reply sent");
      await onReplied();
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : "Reply failed");
    } finally {
      setSending(false);
    }
  }

  async function suggest() {
    if (
      reply.trim() &&
      !confirm("Replace your draft reply with the AI suggestion?")
    )
      return;
    setSuggesting(true);
    setMsg(null);
    try {
      const { text } = await inboxApi.aiSuggest(comment.id, { tone });
      setReply(text);
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : "AI suggestion failed");
    } finally {
      setSuggesting(false);
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
          <h2 className="text-base font-semibold">Comment</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md px-2 py-1 text-sm text-muted-foreground hover:bg-accent hover:text-foreground"
          >
            Close
          </button>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto p-5">
          <div className="flex items-start gap-3">
            <Avatar
              url={comment.author_avatar_url}
              name={comment.author_name}
            />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold">
                  {comment.author_name || "Anonymous"}
                </span>
                <PlatformBadge platform={comment.platform} />
              </div>
              {comment.posted_at && (
                <div className="text-[11px] text-muted-foreground">
                  {new Date(comment.posted_at).toLocaleString()}
                </div>
              )}
            </div>
          </div>

          <div className="rounded-md border border-border bg-muted/30 p-3 text-sm whitespace-pre-wrap">
            {comment.text}
          </div>

          {comment.platform_post_url && (
            <a
              href={comment.platform_post_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
            >
              View original post
              <ExternalLink className="h-3 w-3" />
            </a>
          )}

          <div>
            <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
              <span className="text-xs font-medium">Reply</span>
              <div className="flex items-center gap-1.5">
                <select
                  value={tone}
                  onChange={(e) => setTone(e.target.value)}
                  className="h-7 rounded-md border border-input bg-background px-2 text-[11px] focus:outline-none focus:ring-2 focus:ring-ring"
                  aria-label="AI reply tone"
                >
                  <option value="friendly">Friendly</option>
                  <option value="professional">Professional</option>
                  <option value="empathetic">Empathetic</option>
                  <option value="enthusiastic">Enthusiastic</option>
                  <option value="apologetic">Apologetic</option>
                  <option value="brief">Brief</option>
                </select>
                <button
                  type="button"
                  onClick={() => void suggest()}
                  disabled={suggesting}
                  className="flex h-7 items-center gap-1 rounded-md border border-border bg-background px-2 text-[11px] font-medium hover:bg-accent disabled:opacity-60"
                  title="Draft a reply with AI"
                >
                  {suggesting ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <Sparkles className="h-3 w-3 text-primary" />
                  )}
                  AI suggest
                </button>
              </div>
            </div>
            <textarea
              value={reply}
              onChange={(e) => setReply(e.target.value)}
              rows={4}
              placeholder="Type your reply, or click AI suggest…"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
        </div>

        <div className="flex shrink-0 items-center justify-end gap-2 border-t border-border px-5 py-3">
          {msg && <span className="mr-auto text-xs text-muted-foreground">{msg}</span>}
          <button
            type="button"
            onClick={onClose}
            className="h-9 rounded-md px-3 text-sm hover:bg-accent"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => void send()}
            disabled={sending || !reply.trim()}
            className="flex h-9 items-center gap-1.5 rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-60"
          >
            {sending ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Send className="h-3.5 w-3.5" />
            )}
            Send reply
          </button>
        </div>
      </aside>
    </>
  );
}
