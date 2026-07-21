import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent,
} from "react";
import {
  ChevronLeft,
  ChevronRight,
  File as FileIcon,
  FileVideo,
  Image as ImageIcon,
  Loader2,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { ApiError } from "@/lib/api";
import {
  formatBytes,
  mediaApi,
  type MediaAsset,
  type MediaListResponse,
  type MediaType,
} from "@/lib/media";
import { cn } from "@/lib/utils";

const TYPE_FILTERS: Array<{ label: string; value: MediaType | "" }> = [
  { label: "All", value: "" },
  { label: "Images", value: "image" },
  { label: "Videos", value: "video" },
  { label: "Files", value: "document" },
];

type Upload = {
  id: string;
  file: File;
  progress: number;
  error?: string;
};

export function MediaPage() {
  const [data, setData] = useState<MediaListResponse | null>(null);
  const [page, setPage] = useState(1);
  const [type, setType] = useState<MediaType | "">("");
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<MediaAsset | null>(null);
  const [uploads, setUploads] = useState<Upload[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef<HTMLInputElement | null>(null);

  // Debounce search
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(t);
  }, [search]);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await mediaApi.list({ page, type, search: debouncedSearch });
      setData(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load media");
    } finally {
      setLoading(false);
    }
  }, [page, type, debouncedSearch]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // Reset page when filters change.
  useEffect(() => {
    setPage(1);
  }, [type, debouncedSearch]);

  function startUploads(files: FileList | File[]) {
    const list = Array.from(files);
    if (list.length === 0) return;
    const items: Upload[] = list.map((f) => ({
      id: `${f.name}-${f.size}-${crypto.randomUUID()}`,
      file: f,
      progress: 0,
    }));
    setUploads((u) => [...u, ...items]);
    items.forEach((u) => void runUpload(u));
  }

  async function runUpload(u: Upload) {
    try {
      await mediaApi.upload(u.file, (pct) => {
        setUploads((curr) =>
          curr.map((x) => (x.id === u.id ? { ...x, progress: pct } : x)),
        );
      });
      // Drop completed entry, refresh list.
      setUploads((curr) => curr.filter((x) => x.id !== u.id));
      await refresh();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Upload failed";
      setUploads((curr) =>
        curr.map((x) => (x.id === u.id ? { ...x, error: msg, progress: 100 } : x)),
      );
    }
  }

  function onDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files.length > 0) startUploads(e.dataTransfer.files);
  }

  function onPick(e: ChangeEvent<HTMLInputElement>) {
    if (e.target.files) startUploads(e.target.files);
    e.target.value = "";
  }

  async function deleteAsset(id: number) {
    if (!confirm("Delete this asset? This is permanent.")) return;
    try {
      await mediaApi.remove(id);
      setSelected(null);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Delete failed");
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Media</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Reusable images, videos, and files for your posts.
          </p>
        </div>
        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          className="flex h-9 items-center gap-2 rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground hover:opacity-90"
        >
          <Upload className="h-4 w-4" />
          Upload
        </button>
        <input
          ref={fileRef}
          type="file"
          multiple
          hidden
          onChange={onPick}
        />
      </div>

      {/* Filter row */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex flex-wrap gap-2">
          {TYPE_FILTERS.map((f) => (
            <button
              key={f.value || "all"}
              type="button"
              onClick={() => setType(f.value)}
              className={cn(
                "h-7 rounded-full border px-3 text-xs font-medium transition-colors",
                type === f.value
                  ? "border-primary bg-primary/10 text-primary"
                  : "border-border text-muted-foreground hover:bg-accent",
              )}
            >
              {f.label}
            </button>
          ))}
        </div>
        <div className="relative ml-auto w-64 max-w-full">
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search filename…"
            className="h-8 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
      </div>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Drop zone wraps the grid so dragging anywhere works. */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        className={cn(
          "relative rounded-lg border-2 border-dashed border-transparent p-1 transition-colors",
          dragOver && "border-primary bg-primary/5",
        )}
      >
        {dragOver && (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center rounded-lg bg-primary/10 text-sm font-medium text-primary">
            Drop to upload
          </div>
        )}

        {loading && !data ? (
          <div className="px-4 py-12 text-center text-sm text-muted-foreground">
            Loading…
          </div>
        ) : data && data.items.length === 0 ? (
          <EmptyState onPick={() => fileRef.current?.click()} />
        ) : (
          data && (
            <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
              {data.items.map((m) => (
                <li key={m.id}>
                  <AssetTile asset={m} onClick={() => setSelected(m)} />
                </li>
              ))}
            </ul>
          )
        )}
      </div>

      {data && data.pages > 1 && (
        <Pagination
          page={data.page}
          pages={data.pages}
          onChange={setPage}
        />
      )}

      {uploads.length > 0 && <UploadStack uploads={uploads} onClear={(id) => setUploads((u) => u.filter((x) => x.id !== id))} />}

      {selected && (
        <DetailDrawer
          asset={selected}
          onClose={() => setSelected(null)}
          onSaved={async (updated) => {
            setSelected({ ...selected, ...updated });
            await refresh();
          }}
          onDelete={() => deleteAsset(selected.id)}
        />
      )}
    </div>
  );
}

function AssetTile({
  asset,
  onClick,
}: {
  asset: MediaAsset;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group block w-full overflow-hidden rounded-lg border border-border bg-background text-left transition-shadow hover:shadow-md"
    >
      <div className="relative aspect-square w-full bg-muted/50">
        <Thumbnail asset={asset} />
        <span className="absolute right-1.5 top-1.5 rounded bg-black/60 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-white">
          {asset.media_type}
        </span>
      </div>
      <div className="p-2">
        <div className="truncate text-xs font-medium">{asset.filename}</div>
        <div className="mt-0.5 flex items-center justify-between text-[10px] text-muted-foreground">
          <span>{formatBytes(asset.file_size)}</span>
          {asset.usage_count > 0 && <span>· used {asset.usage_count}×</span>}
        </div>
      </div>
    </button>
  );
}

function Thumbnail({ asset }: { asset: MediaAsset }) {
  if (asset.media_type === "image" && asset.url) {
    return (
      <img
        src={asset.url}
        alt={asset.alt_text || asset.filename}
        loading="lazy"
        className="h-full w-full object-cover transition-transform group-hover:scale-[1.02]"
      />
    );
  }
  if (asset.media_type === "video" && asset.url) {
    return (
      <div className="grid h-full place-items-center text-muted-foreground">
        <FileVideo className="h-8 w-8" />
      </div>
    );
  }
  if (asset.media_type === "image") {
    return (
      <div className="grid h-full place-items-center text-muted-foreground">
        <ImageIcon className="h-8 w-8" />
      </div>
    );
  }
  return (
    <div className="grid h-full place-items-center text-muted-foreground">
      <FileIcon className="h-8 w-8" />
    </div>
  );
}

function EmptyState({ onPick }: { onPick: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border bg-background py-16 text-center">
      <Upload className="h-8 w-8 text-muted-foreground" />
      <p className="mt-3 text-sm font-medium">No media yet</p>
      <p className="mt-1 text-xs text-muted-foreground">
        Drag and drop files anywhere here, or click below.
      </p>
      <button
        type="button"
        onClick={onPick}
        className="mt-4 flex h-9 items-center gap-2 rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground hover:opacity-90"
      >
        <Upload className="h-4 w-4" />
        Pick files
      </button>
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

function UploadStack({
  uploads,
  onClear,
}: {
  uploads: Upload[];
  onClear: (id: string) => void;
}) {
  return (
    <div className="fixed bottom-4 right-4 z-30 w-80 max-w-[calc(100vw-2rem)] space-y-2">
      {uploads.map((u) => (
        <div
          key={u.id}
          className="rounded-lg border border-border bg-background p-3 shadow-md"
        >
          <div className="flex items-start gap-2">
            <Loader2
              className={cn(
                "mt-0.5 h-4 w-4 shrink-0 text-primary",
                u.error ? "text-red-600" : "animate-spin",
              )}
            />
            <div className="min-w-0 flex-1">
              <div className="truncate text-xs font-medium">{u.file.name}</div>
              <div className="mt-1 h-1 overflow-hidden rounded-full bg-muted">
                <div
                  className={cn(
                    "h-full transition-[width]",
                    u.error ? "bg-red-500" : "bg-primary",
                  )}
                  style={{ width: `${u.progress}%` }}
                />
              </div>
              <div className="mt-1 flex justify-between text-[10px] text-muted-foreground">
                <span>{formatBytes(u.file.size)}</span>
                <span>{u.error ? u.error : `${u.progress}%`}</span>
              </div>
            </div>
            {u.error && (
              <button
                type="button"
                onClick={() => onClear(u.id)}
                className="grid h-5 w-5 place-items-center rounded text-muted-foreground hover:bg-accent"
                aria-label="Dismiss"
              >
                <X className="h-3 w-3" />
              </button>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

function DetailDrawer({
  asset,
  onClose,
  onSaved,
  onDelete,
}: {
  asset: MediaAsset;
  onClose: () => void;
  onSaved: (updated: { tags: string[]; alt_text: string }) => Promise<void>;
  onDelete: () => void;
}) {
  const [tagInput, setTagInput] = useState(asset.tags.join(", "));
  const [altText, setAltText] = useState(asset.alt_text);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const tags = useMemo(
    () =>
      tagInput
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean),
    [tagInput],
  );

  async function save() {
    setSaving(true);
    setMsg(null);
    try {
      const res = await mediaApi.updateTags(asset.id, { tags, alt_text: altText });
      await onSaved({ tags: res.tags, alt_text: res.alt_text });
      setMsg("Saved");
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : "Save failed");
    } finally {
      setSaving(false);
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
          <h2 className="truncate text-base font-semibold">{asset.filename}</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md px-2 py-1 text-sm text-muted-foreground hover:bg-accent hover:text-foreground"
          >
            Close
          </button>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto p-5">
          <div className="overflow-hidden rounded-lg border border-border bg-muted/30">
            {asset.media_type === "image" && asset.url ? (
              <img
                src={asset.url}
                alt={asset.alt_text || asset.filename}
                className="max-h-[40vh] w-full object-contain"
              />
            ) : asset.media_type === "video" && asset.url ? (
              <video
                src={asset.url}
                controls
                className="max-h-[40vh] w-full"
              />
            ) : (
              <div className="grid place-items-center py-16 text-muted-foreground">
                <FileIcon className="h-10 w-10" />
                <a
                  href={asset.url ?? "#"}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-2 text-xs text-primary hover:underline"
                >
                  Open file
                </a>
              </div>
            )}
          </div>

          <dl className="grid grid-cols-2 gap-y-2 text-xs">
            <dt className="text-muted-foreground">Type</dt>
            <dd className="capitalize">{asset.media_type}</dd>
            <dt className="text-muted-foreground">Size</dt>
            <dd>{formatBytes(asset.file_size)}</dd>
            <dt className="text-muted-foreground">MIME</dt>
            <dd>{asset.mime_type || "—"}</dd>
            <dt className="text-muted-foreground">Used in</dt>
            <dd>{asset.usage_count} post(s)</dd>
            <dt className="text-muted-foreground">Uploaded</dt>
            <dd>
              {asset.created_at
                ? new Date(asset.created_at).toLocaleString()
                : "—"}
            </dd>
          </dl>

          <label className="block">
            <span className="mb-1 block text-xs font-medium">Alt text</span>
            <input
              type="text"
              value={altText}
              onChange={(e) => setAltText(e.target.value)}
              placeholder="Describe the image for accessibility"
              className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </label>

          <label className="block">
            <span className="mb-1 block text-xs font-medium">
              Tags <span className="text-muted-foreground">(comma-separated)</span>
            </span>
            <input
              type="text"
              value={tagInput}
              onChange={(e) => setTagInput(e.target.value)}
              placeholder="product, hero, q2"
              className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
            {tags.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1">
                {tags.map((t) => (
                  <span
                    key={t}
                    className="rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium text-muted-foreground"
                  >
                    {t}
                  </span>
                ))}
              </div>
            )}
          </label>
        </div>

        <div className="flex shrink-0 items-center justify-between gap-2 border-t border-border px-5 py-3">
          <button
            type="button"
            onClick={onDelete}
            className="flex h-9 items-center gap-1.5 rounded-md border border-red-200 px-3 text-sm font-medium text-red-700 hover:bg-red-50"
          >
            <Trash2 className="h-3.5 w-3.5" />
            Delete
          </button>
          <div className="flex items-center gap-2">
            {msg && <span className="text-xs text-muted-foreground">{msg}</span>}
            <button
              type="button"
              onClick={() => void save()}
              disabled={saving}
              className="h-9 rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-60"
            >
              {saving ? "Saving…" : "Save"}
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
