import { useCallback, useEffect, useState } from "react";
import { File as FileIcon, FileVideo, Image as ImageIcon, Loader2, X } from "lucide-react";
import { ApiError } from "@/lib/api";
import { mediaApi, type MediaAsset } from "@/lib/media";
import { cn } from "@/lib/utils";

type Props = {
  open: boolean;
  selectedIds: number[];
  onClose: () => void;
  onConfirm: (assets: MediaAsset[]) => void;
};

export function MediaPicker({ open, selectedIds, onClose, onConfirm }: Props) {
  const [items, setItems] = useState<MediaAsset[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [picked, setPicked] = useState<Set<number>>(new Set(selectedIds));

  useEffect(() => {
    if (!open) return;
    setPicked(new Set(selectedIds));
  }, [open, selectedIds]);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await mediaApi.list({ page: 1 });
      setItems(res.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load media");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) void refresh();
  }, [open, refresh]);

  function toggle(id: number) {
    setPicked((curr) => {
      const next = new Set(curr);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function confirm() {
    onConfirm(items.filter((i) => picked.has(i.id)));
  }

  if (!open) return null;

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
        aria-label="Pick media"
        className="fixed inset-y-0 right-0 z-50 flex w-full max-w-2xl flex-col border-l border-border bg-background shadow-2xl"
      >
        <div className="flex h-14 shrink-0 items-center justify-between border-b border-border px-5">
          <div>
            <h2 className="text-base font-semibold">Pick media</h2>
            <p className="text-xs text-muted-foreground">
              {picked.size} selected · drop new files in the Media library to add more
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md px-2 py-1 text-sm text-muted-foreground hover:bg-accent hover:text-foreground"
          >
            Close
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          {error && (
            <div className="mb-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          )}
          {loading ? (
            <div className="grid place-items-center py-12 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
            </div>
          ) : items.length === 0 ? (
            <div className="rounded-md border border-dashed border-border bg-muted/30 px-4 py-12 text-center text-sm text-muted-foreground">
              Your media library is empty. Upload files in <strong>Media</strong>.
            </div>
          ) : (
            <ul className="grid grid-cols-3 gap-3 sm:grid-cols-4">
              {items.map((m) => {
                const on = picked.has(m.id);
                return (
                  <li key={m.id}>
                    <button
                      type="button"
                      onClick={() => toggle(m.id)}
                      className={cn(
                        "group relative block w-full overflow-hidden rounded-lg border-2 bg-background text-left",
                        on ? "border-primary" : "border-border hover:border-primary/40",
                      )}
                    >
                      <div className="relative aspect-square w-full bg-muted/50">
                        <Thumb asset={m} />
                        {on && (
                          <span className="absolute right-1.5 top-1.5 grid h-5 w-5 place-items-center rounded-full bg-primary text-[10px] font-bold text-primary-foreground">
                            ✓
                          </span>
                        )}
                      </div>
                      <div className="p-1.5">
                        <div className="truncate text-[11px] font-medium">
                          {m.filename}
                        </div>
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
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
            onClick={confirm}
            className="h-9 rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground hover:opacity-90"
          >
            Use {picked.size} selected
          </button>
        </div>
      </aside>
    </>
  );
}

function Thumb({ asset }: { asset: MediaAsset }) {
  if (asset.media_type === "image" && asset.url) {
    return (
      <img
        src={asset.url}
        alt={asset.alt_text || asset.filename}
        loading="lazy"
        className="h-full w-full object-cover"
      />
    );
  }
  if (asset.media_type === "video") {
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

export function AttachedMediaStrip({
  assets,
  onRemove,
}: {
  assets: MediaAsset[];
  onRemove: (id: number) => void;
}) {
  if (assets.length === 0) return null;
  return (
    <ul className="flex flex-wrap gap-2">
      {assets.map((m) => (
        <li
          key={m.id}
          className="group relative h-16 w-16 overflow-hidden rounded-md border border-border bg-muted/40"
        >
          {m.media_type === "image" && m.url ? (
            <img
              src={m.url}
              alt={m.alt_text || m.filename}
              className="h-full w-full object-cover"
            />
          ) : (
            <div className="grid h-full place-items-center text-muted-foreground">
              {m.media_type === "video" ? (
                <FileVideo className="h-5 w-5" />
              ) : (
                <FileIcon className="h-5 w-5" />
              )}
            </div>
          )}
          <button
            type="button"
            onClick={() => onRemove(m.id)}
            aria-label={`Remove ${m.filename}`}
            className="absolute right-0.5 top-0.5 grid h-5 w-5 place-items-center rounded-full bg-black/60 text-white opacity-0 transition-opacity group-hover:opacity-100"
          >
            <X className="h-3 w-3" />
          </button>
        </li>
      ))}
    </ul>
  );
}
