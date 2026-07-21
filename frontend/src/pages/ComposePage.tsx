import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertCircle,
  CalendarClock,
  CheckCircle2,
  ExternalLink,
  Loader2,
  Paperclip,
  Save,
  Send,
} from "lucide-react";
import { ApiError } from "@/lib/api";
import {
  composeApi,
  type PlatformInfo,
  type PostResult,
} from "@/lib/compose";
import { draftsApi } from "@/lib/drafts";
import type { MediaAsset } from "@/lib/media";
import { cn } from "@/lib/utils";
import { AIAssistPanel } from "@/components/compose/AIAssistPanel";
import {
  AttachedMediaStrip,
  MediaPicker,
} from "@/components/compose/MediaPicker";
import { ScheduleDialog } from "@/components/compose/ScheduleDialog";
import { PlatformChip } from "@/components/PlatformChip";
import { PlatformBadge } from "@/components/PlatformBadge";

type Posting = "idle" | "publishing" | "saving";

export function ComposePage() {
  const [platforms, setPlatforms] = useState<PlatformInfo[]>([]);
  const [loadingPlatforms, setLoadingPlatforms] = useState(true);
  const [platformsError, setPlatformsError] = useState<string | null>(null);

  const [text, setText] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [attached, setAttached] = useState<MediaAsset[]>([]);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [scheduleOpen, setScheduleOpen] = useState(false);
  const [scheduledNotice, setScheduledNotice] = useState(false);
  const [posting, setPosting] = useState<Posting>("idle");
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<PostResult[] | null>(null);
  const [savedDraftId, setSavedDraftId] = useState<number | null>(null);

  function mediaPayload() {
    return attached.map((a) => ({
      path: a.file_path,
      media_type: a.media_type,
      alt_text: a.alt_text || undefined,
    }));
  }

  const loadPlatforms = useCallback(async () => {
    setLoadingPlatforms(true);
    setPlatformsError(null);
    try {
      const data = await composeApi.platforms();
      setPlatforms(data);
    } catch (err) {
      setPlatformsError(
        err instanceof ApiError ? err.message : "Failed to load platforms",
      );
    } finally {
      setLoadingPlatforms(false);
    }
  }, []);

  useEffect(() => {
    void loadPlatforms();
  }, [loadPlatforms]);

  const minMaxLength = useMemo(() => {
    const lengths = platforms
      .filter((p) => selected.includes(p.name) && p.max_text_length)
      .map((p) => p.max_text_length as number);
    return lengths.length ? Math.min(...lengths) : null;
  }, [platforms, selected]);

  const overLimit = minMaxLength != null && text.length > minMaxLength;
  const noneConnected = platforms.length > 0 && platforms.every((p) => !p.connected);
  const canPost =
    selected.length > 0 &&
    text.trim().length > 0 &&
    !overLimit &&
    posting === "idle";
  const canSave = text.trim().length > 0 && posting === "idle";

  function toggle(name: string) {
    setSelected((curr) =>
      curr.includes(name) ? curr.filter((n) => n !== name) : [...curr, name],
    );
  }

  async function publish() {
    setPosting("publishing");
    setError(null);
    setResults(null);
    setSavedDraftId(null);
    try {
      const res = await composeApi.post({
        text,
        platforms: selected,
        media: mediaPayload(),
      });
      setResults(res.results);
      const allOk = res.results.every((r) => r.success);
      if (allOk) {
        setText("");
        setSelected([]);
        setAttached([]);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to publish");
    } finally {
      setPosting("idle");
    }
  }

  async function saveDraft() {
    setPosting("saving");
    setError(null);
    setResults(null);
    setSavedDraftId(null);
    try {
      const res = await draftsApi.create({
        name: text.split("\n")[0].slice(0, 60) || "Untitled draft",
        text,
        platforms: selected,
        media: mediaPayload(),
      });
      setSavedDraftId(res.id);
      setText("");
      setSelected([]);
      setAttached([]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save draft");
    } finally {
      setPosting("idle");
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Compose</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Write once, publish to every connected platform.
        </p>
      </div>

      {noneConnected && (
        <Notice tone="warn">
          <span>You haven't connected any platforms yet.</span>{" "}
          <Link
            to="/connections"
            className="font-medium underline underline-offset-2"
          >
            Set up connections →
          </Link>
        </Notice>
      )}

      {platformsError && <Notice tone="error">{platformsError}</Notice>}

      <AIAssistPanel
        text={text}
        selectedPlatforms={selected}
        onApplyText={setText}
        onAppendText={(suffix) =>
          setText((curr) =>
            curr.trim() ? `${curr.trimEnd()}\n\n${suffix}` : suffix,
          )
        }
      />

      <div className="rounded-lg border border-border bg-background">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={8}
          placeholder="What do you want to share?"
          className="block w-full resize-none rounded-t-lg bg-transparent px-4 py-3 text-sm focus:outline-none"
        />
        {attached.length > 0 && (
          <div className="border-t border-border px-4 py-3">
            <AttachedMediaStrip
              assets={attached}
              onRemove={(id) =>
                setAttached((curr) => curr.filter((m) => m.id !== id))
              }
            />
          </div>
        )}
        <div className="flex items-center justify-between border-t border-border px-4 py-2 text-xs text-muted-foreground">
          <span>
            {text.length} chars
            {minMaxLength != null && (
              <>
                {" "}
                / {minMaxLength}{" "}
                <span className="text-muted-foreground/70">
                  (tightest selected platform)
                </span>
              </>
            )}
          </span>
          {overLimit && (
            <span className="font-medium text-red-600">Too long</span>
          )}
        </div>
      </div>

      <div>
        <div className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
          Platforms
        </div>
        {loadingPlatforms ? (
          <div className="text-sm text-muted-foreground">Loading platforms…</div>
        ) : platforms.length === 0 ? (
          <div className="text-sm text-muted-foreground">
            No platforms registered.
          </div>
        ) : (
          <div className="flex flex-wrap gap-2">
            {platforms.map((p) => (
              <PlatformChip
                key={p.name}
                platform={p.name}
                selected={selected.includes(p.name)}
                disabled={!p.connected}
                onClick={() => toggle(p.name)}
                title={
                  p.connected
                    ? p.display_name
                    : `${p.display_name} — not connected`
                }
              >
                {!p.connected && (
                  <span className="ml-1 text-muted-foreground">·offline</span>
                )}
              </PlatformChip>
            ))}
          </div>
        )}
      </div>

      {error && <Notice tone="error">{error}</Notice>}

      {savedDraftId != null && (
        <Notice tone="success">
          Saved as draft.{" "}
          <Link
            to="/drafts"
            className="font-medium underline underline-offset-2"
          >
            Go to drafts →
          </Link>
        </Notice>
      )}

      {scheduledNotice && (
        <Notice tone="success">
          Scheduled.{" "}
          <Link
            to="/schedules"
            className="font-medium underline underline-offset-2"
          >
            Manage schedules →
          </Link>
        </Notice>
      )}

      {results && <ResultList results={results} />}

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => setPickerOpen(true)}
          className="flex h-9 items-center gap-1.5 rounded-md border border-border px-3 text-sm font-medium hover:bg-accent"
        >
          <Paperclip className="h-3.5 w-3.5" />
          {attached.length > 0
            ? `${attached.length} attached`
            : "Attach media"}
        </button>
        <div className="ml-auto" />
        <button
          type="button"
          disabled={!canSave}
          onClick={() => void saveDraft()}
          className="flex h-9 items-center gap-1.5 rounded-md border border-border px-3 text-sm font-medium hover:bg-accent disabled:opacity-50"
        >
          {posting === "saving" ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Save className="h-3.5 w-3.5" />
          )}
          Save as draft
        </button>
        <button
          type="button"
          disabled={
            text.trim().length === 0 || selected.length === 0 || posting !== "idle"
          }
          onClick={() => setScheduleOpen(true)}
          className="flex h-9 items-center gap-1.5 rounded-md border border-border px-3 text-sm font-medium hover:bg-accent disabled:opacity-50"
        >
          <CalendarClock className="h-3.5 w-3.5" />
          Schedule…
        </button>
        <button
          type="button"
          disabled={!canPost}
          onClick={() => void publish()}
          className="flex h-9 items-center gap-1.5 rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
        >
          {posting === "publishing" ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Send className="h-3.5 w-3.5" />
          )}
          Post now
        </button>
      </div>

      <MediaPicker
        open={pickerOpen}
        selectedIds={attached.map((a) => a.id)}
        onClose={() => setPickerOpen(false)}
        onConfirm={(assets) => {
          setAttached(assets);
          setPickerOpen(false);
        }}
      />

      <ScheduleDialog
        open={scheduleOpen}
        onClose={() => setScheduleOpen(false)}
        text={text}
        platforms={selected}
        mediaPayload={mediaPayload}
        onScheduled={() => {
          setScheduledNotice(true);
          setText("");
          setSelected([]);
          setAttached([]);
        }}
      />
    </div>
  );
}

function ResultList({ results }: { results: PostResult[] }) {
  return (
    <ul className="overflow-hidden rounded-lg border border-border bg-background">
      {results.map((r) => (
        <li
          key={r.platform}
          className="flex items-start gap-3 border-b border-border px-4 py-3 last:border-b-0"
        >
          {r.success ? (
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
          ) : (
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-600" />
          )}
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 text-sm font-medium">
              <PlatformBadge platform={r.platform} variant="solid" />
              <span
                className={cn(
                  "rounded-full px-2 py-0.5 text-[10px] font-semibold",
                  r.success
                    ? "bg-emerald-100 text-emerald-700"
                    : "bg-red-100 text-red-700",
                )}
              >
                {r.success ? "Posted" : "Failed"}
              </span>
            </div>
            {r.error && (
              <div className="mt-0.5 truncate text-xs text-red-700">{r.error}</div>
            )}
            {r.post_url && (
              <a
                href={r.post_url}
                target="_blank"
                rel="noreferrer"
                className="mt-0.5 inline-flex items-center gap-1 text-xs text-primary hover:underline"
              >
                View post <ExternalLink className="h-3 w-3" />
              </a>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}

function Notice({
  tone,
  children,
}: {
  tone: "warn" | "error" | "success";
  children: React.ReactNode;
}) {
  const toneClass = {
    warn: "border-amber-200 bg-amber-50 text-amber-900",
    error: "border-red-200 bg-red-50 text-red-700",
    success: "border-emerald-200 bg-emerald-50 text-emerald-800",
  }[tone];
  return (
    <div className={cn("rounded-md border px-3 py-2 text-sm", toneClass)}>
      {children}
    </div>
  );
}
