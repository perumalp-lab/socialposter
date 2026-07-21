import { useCallback, useEffect, useMemo, useState } from "react";
import {
  CheckCircle2,
  Download,
  Loader2,
  Plus,
  Rocket,
  Send,
  Trash2,
  Upload,
  XCircle,
} from "lucide-react";
import { ApiError } from "@/lib/api";
import {
  draftsApi,
  PLATFORMS,
  SAMPLE_BULK_CSV,
  type BulkImportResult,
  type DraftDetail,
  type DraftInput,
  type DraftListItem,
  type DraftStatus,
  type PublishResult,
} from "@/lib/drafts";
import { cn } from "@/lib/utils";
import { PlatformBadge } from "@/components/PlatformBadge";
import { PlatformChip } from "@/components/PlatformChip";

type EditorState =
  | { mode: "closed" }
  | { mode: "create" }
  | { mode: "edit"; draft: DraftDetail };

const STATUS_FILTERS: Array<{ label: string; value: DraftStatus | "" }> = [
  { label: "All", value: "" },
  { label: "Draft", value: "draft" },
  { label: "Pending", value: "pending_approval" },
  { label: "Approved", value: "approved" },
  { label: "Rejected", value: "rejected" },
  { label: "Published", value: "published" },
];

export function DraftsPage() {
  const [items, setItems] = useState<DraftListItem[]>([]);
  const [filter, setFilter] = useState<DraftStatus | "">("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editor, setEditor] = useState<EditorState>({ mode: "closed" });
  const [bulkOpen, setBulkOpen] = useState(false);
  const [publishResults, setPublishResults] = useState<{
    name: string;
    results: PublishResult[];
  } | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { items } = await draftsApi.list(filter || undefined);
      setItems(items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load drafts");
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Drafts</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Compose, review, and approve posts before they go live.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setBulkOpen(true)}
            className="flex h-9 items-center gap-2 rounded-md border border-border px-3 text-sm font-medium hover:bg-accent"
          >
            <Upload className="h-4 w-4" />
            Bulk import
          </button>
          <button
            type="button"
            onClick={() => setEditor({ mode: "create" })}
            className="flex h-9 items-center gap-2 rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground hover:opacity-90"
          >
            <Plus className="h-4 w-4" />
            New draft
          </button>
        </div>
      </div>

      {bulkOpen && (
        <BulkImportDialog
          onClose={() => setBulkOpen(false)}
          onImported={async () => {
            await refresh();
          }}
        />
      )}

      <div className="flex flex-wrap gap-2">
        {STATUS_FILTERS.map((f) => (
          <button
            key={f.value || "all"}
            type="button"
            onClick={() => setFilter(f.value)}
            className={cn(
              "h-7 rounded-full border px-3 text-xs font-medium transition-colors",
              filter === f.value
                ? "border-primary bg-primary/10 text-primary"
                : "border-border text-muted-foreground hover:bg-accent",
            )}
          >
            {f.label}
          </button>
        ))}
      </div>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      {publishResults && (
        <div className="rounded-lg border border-border bg-background">
          <div className="flex items-center justify-between border-b border-border px-4 py-2">
            <div className="text-sm">
              Publish results for{" "}
              <span className="font-medium">{publishResults.name}</span>
            </div>
            <button
              type="button"
              onClick={() => setPublishResults(null)}
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              Dismiss
            </button>
          </div>
          <ul className="divide-y divide-border">
            {publishResults.results.map((r) => (
              <li
                key={r.platform}
                className="flex items-start gap-3 px-4 py-2 text-sm"
              >
                {r.success ? (
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                ) : (
                  <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-600" />
                )}
                <PlatformBadge platform={r.platform} variant="solid" />
                {r.error && <span className="text-red-700">{r.error}</span>}
                {r.post_url && (
                  <a
                    href={r.post_url}
                    target="_blank"
                    rel="noreferrer"
                    className="ml-auto text-xs text-primary hover:underline"
                  >
                    Open
                  </a>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="overflow-hidden rounded-lg border border-border bg-background">
        {loading ? (
          <div className="px-4 py-8 text-center text-sm text-muted-foreground">
            Loading drafts…
          </div>
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center justify-center px-4 py-12 text-center">
            <p className="text-sm font-medium">No drafts yet</p>
            <p className="mt-1 max-w-md text-xs text-muted-foreground">
              Drafts let you compose, review, and approve posts before
              publishing.
            </p>
            <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
              <button
                type="button"
                onClick={() => setEditor({ mode: "create" })}
                className="inline-flex items-center gap-1 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:opacity-90"
              >
                <Plus className="h-3 w-3" />
                Create your first draft
              </button>
              <button
                type="button"
                onClick={() => setBulkOpen(true)}
                className="inline-flex items-center gap-1 rounded-md border border-border bg-background px-3 py-1.5 text-xs font-medium hover:bg-accent"
              >
                <Upload className="h-3 w-3" />
                Bulk import from CSV
              </button>
            </div>
          </div>
        ) : (
          <ul className="divide-y divide-border">
            {items.map((d) => (
              <DraftRow
                key={d.id}
                draft={d}
                onOpen={async () => {
                  try {
                    const detail = await draftsApi.get(d.id);
                    setEditor({ mode: "edit", draft: detail });
                  } catch (err) {
                    setError(
                      err instanceof ApiError ? err.message : "Failed to open draft",
                    );
                  }
                }}
                onDelete={async () => {
                  if (!confirm(`Delete "${d.name}"?`)) return;
                  try {
                    await draftsApi.remove(d.id);
                    await refresh();
                  } catch (err) {
                    setError(
                      err instanceof ApiError ? err.message : "Failed to delete",
                    );
                  }
                }}
                onApprove={async () => {
                  try {
                    await draftsApi.approve(d.id);
                    await refresh();
                  } catch (err) {
                    setError(
                      err instanceof ApiError ? err.message : "Approve failed",
                    );
                  }
                }}
                onReject={async () => {
                  const comment = prompt("Reason for rejection?", "");
                  if (comment == null) return;
                  try {
                    await draftsApi.reject(d.id, comment || "Rejected");
                    await refresh();
                  } catch (err) {
                    setError(
                      err instanceof ApiError ? err.message : "Reject failed",
                    );
                  }
                }}
                onPublish={async () => {
                  if (
                    !confirm(
                      `Publish "${d.name}" to ${d.platforms.join(", ")} now?`,
                    )
                  )
                    return;
                  try {
                    const res = await draftsApi.publish(d.id);
                    setPublishResults({ name: d.name, results: res.results });
                    await refresh();
                  } catch (err) {
                    setError(
                      err instanceof ApiError ? err.message : "Publish failed",
                    );
                  }
                }}
              />
            ))}
          </ul>
        )}
      </div>

      {editor.mode !== "closed" && (
        <DraftEditor
          state={editor}
          onClose={() => setEditor({ mode: "closed" })}
          onSaved={async () => {
            setEditor({ mode: "closed" });
            await refresh();
          }}
        />
      )}
    </div>
  );
}

function DraftRow({
  draft,
  onOpen,
  onDelete,
  onApprove,
  onReject,
  onPublish,
}: {
  draft: DraftListItem;
  onOpen: () => void;
  onDelete: () => void;
  onApprove: () => void;
  onReject: () => void;
  onPublish: () => void;
}) {
  return (
    <li className="group flex items-center gap-4 px-4 py-3 hover:bg-accent/40">
      <button
        type="button"
        onClick={onOpen}
        className="min-w-0 flex-1 text-left"
      >
        <div className="flex items-center gap-2">
          <span className="truncate text-sm font-medium">{draft.name}</span>
          <StatusBadge status={draft.status} />
        </div>
        <div className="mt-0.5 truncate text-xs text-muted-foreground">
          {draft.text || <span className="italic">No content yet</span>}
        </div>
        <div className="mt-1 flex items-center gap-2 text-[11px] text-muted-foreground">
          <span>{draft.author || "—"}</span>
          {draft.platforms.length > 0 && (
            <>
              <span>·</span>
              <span className="flex flex-wrap items-center gap-1.5">
                {draft.platforms.map((p) => (
                  <PlatformBadge key={p} platform={p} variant="dot" />
                ))}
              </span>
            </>
          )}
          {draft.updated_at && (
            <>
              <span>·</span>
              <span>{new Date(draft.updated_at).toLocaleString()}</span>
            </>
          )}
        </div>
      </button>

      <div className="flex shrink-0 items-center gap-1">
        {draft.status === "pending_approval" && (
          <>
            <button
              type="button"
              onClick={onApprove}
              className="flex h-8 items-center gap-1 rounded-md border border-emerald-200 bg-emerald-50 px-2 text-xs font-medium text-emerald-700 hover:bg-emerald-100"
            >
              <CheckCircle2 className="h-3.5 w-3.5" />
              Approve
            </button>
            <button
              type="button"
              onClick={onReject}
              className="flex h-8 items-center gap-1 rounded-md border border-red-200 bg-red-50 px-2 text-xs font-medium text-red-700 hover:bg-red-100"
            >
              <XCircle className="h-3.5 w-3.5" />
              Reject
            </button>
          </>
        )}
        {draft.status === "approved" && (
          <button
            type="button"
            onClick={onPublish}
            className="flex h-8 items-center gap-1 rounded-md bg-primary px-3 text-xs font-medium text-primary-foreground hover:opacity-90"
          >
            <Rocket className="h-3.5 w-3.5" />
            Publish
          </button>
        )}
        <button
          type="button"
          onClick={onDelete}
          aria-label="Delete draft"
          className="grid h-8 w-8 place-items-center rounded-md text-muted-foreground opacity-0 transition-opacity hover:bg-red-50 hover:text-red-600 group-hover:opacity-100"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      </div>
    </li>
  );
}

function StatusBadge({ status }: { status: DraftStatus }) {
  const map: Record<DraftStatus, { label: string; className: string }> = {
    draft: { label: "Draft", className: "bg-muted text-muted-foreground" },
    pending_approval: {
      label: "Pending",
      className: "bg-amber-100 text-amber-800",
    },
    approved: { label: "Approved", className: "bg-emerald-100 text-emerald-800" },
    rejected: { label: "Rejected", className: "bg-red-100 text-red-700" },
    published: { label: "Published", className: "bg-blue-100 text-blue-700" },
  };
  const { label, className } = map[status];
  return (
    <span
      className={cn(
        "inline-flex h-5 items-center rounded-full px-2 text-[10px] font-semibold",
        className,
      )}
    >
      {label}
    </span>
  );
}

function DraftEditor({
  state,
  onClose,
  onSaved,
}: {
  state: Exclude<EditorState, { mode: "closed" }>;
  onClose: () => void;
  onSaved: () => void;
}) {
  const initial = useMemo<DraftInput>(() => {
    if (state.mode === "edit") {
      return {
        name: state.draft.name,
        text: state.draft.text,
        platforms: state.draft.platforms,
      };
    }
    return { name: "", text: "", platforms: [] };
  }, [state]);

  const [name, setName] = useState(initial.name);
  const [text, setText] = useState(initial.text);
  const [platforms, setPlatforms] = useState<string[]>(initial.platforms);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function togglePlatform(p: string) {
    setPlatforms((curr) =>
      curr.includes(p) ? curr.filter((x) => x !== p) : [...curr, p],
    );
  }

  async function save(submitForReview = false) {
    setSubmitting(true);
    setError(null);
    try {
      const payload: DraftInput = {
        name: name.trim() || "Untitled Draft",
        text,
        platforms,
      };
      let id: number;
      if (state.mode === "create") {
        const res = await draftsApi.create(payload);
        id = res.id;
      } else {
        await draftsApi.update(state.draft.id, payload);
        id = state.draft.id;
      }
      if (submitForReview) await draftsApi.submit(id);
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save");
    } finally {
      setSubmitting(false);
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
        aria-label={state.mode === "create" ? "New draft" : "Edit draft"}
        className="fixed inset-y-0 right-0 z-50 flex w-full max-w-xl flex-col border-l border-border bg-background shadow-2xl"
      >
        <div className="flex h-14 shrink-0 items-center justify-between border-b border-border px-5">
          <h2 className="text-base font-semibold">
            {state.mode === "create" ? "New draft" : "Edit draft"}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md px-2 py-1 text-sm text-muted-foreground hover:bg-accent hover:text-foreground"
          >
            Close
          </button>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto p-5">
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-muted-foreground">
              Name
            </span>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Q2 product launch announcement"
              className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </label>

          <label className="block">
            <span className="mb-1 block text-xs font-medium text-muted-foreground">
              Content
            </span>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={8}
              placeholder="What do you want to share?"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
            <span className="mt-1 block text-right text-[11px] text-muted-foreground">
              {text.length} chars
            </span>
          </label>

          <div>
            <span className="mb-2 block text-xs font-medium text-muted-foreground">
              Platforms
            </span>
            <div className="flex flex-wrap gap-2">
              {PLATFORMS.map((p) => (
                <PlatformChip
                  key={p}
                  platform={p}
                  selected={platforms.includes(p)}
                  onClick={() => togglePlatform(p)}
                />
              ))}
            </div>
          </div>

          {error && (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          )}
        </div>

        <div className="flex shrink-0 items-center justify-end gap-2 border-t border-border px-5 py-3">
          <button
            type="button"
            onClick={onClose}
            className="h-9 rounded-md px-3 text-sm hover:bg-accent"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={submitting}
            onClick={() => save(false)}
            className="h-9 rounded-md border border-border px-3 text-sm font-medium hover:bg-accent disabled:opacity-60"
          >
            Save draft
          </button>
          <button
            type="button"
            disabled={submitting || platforms.length === 0}
            onClick={() => save(true)}
            className="flex h-9 items-center gap-1.5 rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-60"
            title={
              platforms.length === 0
                ? "Pick at least one platform first"
                : undefined
            }
          >
            <Send className="h-3.5 w-3.5" />
            Save & submit
          </button>
        </div>
      </aside>
    </>
  );
}

function BulkImportDialog({
  onClose,
  onImported,
}: {
  onClose: () => void;
  onImported: () => Promise<void>;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [progress, setProgress] = useState<number>(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<BulkImportResult | null>(null);

  function downloadSample() {
    const blob = new Blob([SAMPLE_BULK_CSV], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "drafts_template.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  async function run() {
    if (!file) return;
    setBusy(true);
    setError(null);
    setResult(null);
    setProgress(0);
    try {
      const res = await draftsApi.bulkImport(file, setProgress);
      setResult(res);
      if (res.created_count > 0) {
        await onImported();
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Import failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div
        onClick={busy ? undefined : onClose}
        aria-hidden
        className="fixed inset-0 z-40 bg-black/40 animate-fade-in"
      />
      <div
        role="dialog"
        aria-modal="true"
        className="fixed left-1/2 top-1/2 z-50 w-full max-w-lg -translate-x-1/2 -translate-y-1/2 rounded-lg border border-border bg-background shadow-2xl"
      >
        <div className="flex items-center justify-between border-b border-border px-5 py-3">
          <h2 className="text-base font-semibold">Bulk import drafts</h2>
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            className="rounded-md px-2 py-1 text-sm text-muted-foreground hover:bg-accent disabled:opacity-60"
          >
            Close
          </button>
        </div>

        <div className="space-y-4 p-5">
          <p className="text-sm text-muted-foreground">
            Upload a CSV with columns{" "}
            <code className="rounded bg-muted px-1 text-xs">name</code>,{" "}
            <code className="rounded bg-muted px-1 text-xs">platforms</code>,{" "}
            <code className="rounded bg-muted px-1 text-xs">text</code>, and an
            optional{" "}
            <code className="rounded bg-muted px-1 text-xs">status</code>{" "}
            column. Quote any cell containing commas.
          </p>

          <button
            type="button"
            onClick={downloadSample}
            className="inline-flex items-center gap-1.5 rounded-md border border-border bg-background px-3 py-1.5 text-xs font-medium hover:bg-accent"
          >
            <Download className="h-3.5 w-3.5" />
            Download template CSV
          </button>

          <label className="block">
            <span className="mb-1 block text-xs font-medium">CSV file</span>
            <input
              type="file"
              accept=".csv,text/csv"
              onChange={(e) => {
                setFile(e.target.files?.[0] ?? null);
                setResult(null);
                setError(null);
              }}
              disabled={busy}
              className="block w-full text-sm file:mr-3 file:rounded-md file:border-0 file:bg-primary file:px-3 file:py-1.5 file:text-xs file:font-medium file:text-primary-foreground hover:file:opacity-90 disabled:opacity-60"
            />
          </label>

          {busy && (
            <div className="space-y-1">
              <div className="h-2 overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full bg-primary transition-[width] duration-150"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <p className="text-[11px] text-muted-foreground">
                Uploading… {progress}%
              </p>
            </div>
          )}

          {error && (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          )}

          {result && (
            <div className="space-y-2 rounded-md border border-border bg-muted/20 p-3 text-sm">
              <p>
                <span className="font-medium text-emerald-700">
                  {result.created_count}
                </span>{" "}
                draft{result.created_count === 1 ? "" : "s"} created
                {result.error_count > 0 && (
                  <>
                    {" · "}
                    <span className="font-medium text-red-700">
                      {result.error_count}
                    </span>{" "}
                    skipped
                  </>
                )}
                .
              </p>
              {result.errors.length > 0 && (
                <ul className="max-h-40 space-y-1 overflow-y-auto text-xs text-muted-foreground">
                  {result.errors.map((e) => (
                    <li key={e.row}>
                      <span className="font-mono text-red-700">row {e.row}:</span>{" "}
                      {e.error}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-border px-5 py-3">
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            className="h-9 rounded-md px-3 text-sm hover:bg-accent disabled:opacity-60"
          >
            {result ? "Done" : "Cancel"}
          </button>
          <button
            type="button"
            onClick={() => void run()}
            disabled={busy || !file}
            className="flex h-9 items-center gap-1.5 rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-60"
          >
            {busy ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Upload className="h-3.5 w-3.5" />
            )}
            Import
          </button>
        </div>
      </div>
    </>
  );
}
