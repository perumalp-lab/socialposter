import { useEffect, useMemo, useState } from "react";
import { CalendarClock, Loader2, X } from "lucide-react";
import { ApiError } from "@/lib/api";
import { asPlanLimit, type PlanLimitBody } from "@/lib/billing";
import { PlanLimitAlert } from "@/components/PlanLimitAlert";
import {
  REPEAT_PRESETS,
  fromDatetimeLocal,
  schedulesApi,
  toDatetimeLocal,
  type RepeatPreset,
  type ScheduleInput,
} from "@/lib/schedules";
import { cn } from "@/lib/utils";

type Props = {
  open: boolean;
  onClose: () => void;
  /** Compose-page state used to seed the schedule. */
  text: string;
  platforms: string[];
  mediaPayload: () => Array<Record<string, unknown>>;
  /** Reset function called after a successful create. */
  onScheduled?: () => void;
};

export function ScheduleDialog({
  open,
  onClose,
  text,
  platforms,
  mediaPayload,
  onScheduled,
}: Props) {
  const [name, setName] = useState("");
  const [when, setWhen] = useState<string>("");
  const [preset, setPreset] = useState<RepeatPreset>("once");
  const [customMinutes, setCustomMinutes] = useState<number>(60);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [planLimit, setPlanLimit] = useState<PlanLimitBody | null>(null);

  // Seed a sensible default name + a "next round-hour" datetime each open.
  useEffect(() => {
    if (!open) return;
    const seed = text.split("\n")[0].slice(0, 60).trim() || "Scheduled post";
    setName(seed);

    const d = new Date();
    d.setHours(d.getHours() + 1);
    d.setMinutes(0, 0, 0);
    setWhen(toDatetimeLocal(d));

    setPreset("once");
    setCustomMinutes(60);
    setError(null);
    setPlanLimit(null);
  }, [open, text]);

  const intervalMinutes = useMemo(() => {
    if (preset === "custom") return Math.max(1, Math.floor(customMinutes));
    return REPEAT_PRESETS.find((p) => p.value === preset)?.intervalMinutes ?? 1440;
  }, [preset, customMinutes]);

  const canSubmit =
    name.trim().length > 0 &&
    when.length > 0 &&
    text.trim().length > 0 &&
    platforms.length > 0 &&
    !submitting;

  async function submit() {
    setSubmitting(true);
    setError(null);
    setPlanLimit(null);
    try {
      const input: ScheduleInput = {
        name: name.trim(),
        platforms,
        text,
        media: mediaPayload(),
        interval_minutes: intervalMinutes,
        start_at: fromDatetimeLocal(when),
      };
      await schedulesApi.create(input);
      onScheduled?.();
      onClose();
    } catch (err) {
      const limit = asPlanLimit(err);
      if (limit) {
        setPlanLimit(limit);
      } else {
        setError(err instanceof ApiError ? err.message : "Schedule failed");
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (!open) return null;

  return (
    <>
      <div
        onClick={onClose}
        aria-hidden
        className="fixed inset-0 z-40 bg-black/40 animate-fade-in"
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Schedule post"
        className="fixed left-1/2 top-1/2 z-50 w-[min(36rem,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2 rounded-lg border border-border bg-background shadow-2xl animate-fade-in"
      >
        <div className="flex items-center justify-between border-b border-border px-5 py-3">
          <div className="flex items-center gap-2">
            <CalendarClock className="h-4 w-4 text-primary" />
            <h2 className="text-base font-semibold">Schedule this post</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="grid h-8 w-8 place-items-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-4 p-5">
          <Field label="Schedule name">
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Weekly product update"
              className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </Field>

          <Field label="First run (your local time)">
            <input
              type="datetime-local"
              value={when}
              onChange={(e) => setWhen(e.target.value)}
              className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </Field>

          <div>
            <span className="mb-1 block text-xs font-medium">Repeat</span>
            <div className="flex flex-wrap gap-2">
              {REPEAT_PRESETS.map((p) => (
                <button
                  key={p.value}
                  type="button"
                  onClick={() => setPreset(p.value)}
                  className={cn(
                    "h-8 rounded-full border px-3 text-xs font-medium transition-colors",
                    preset === p.value
                      ? "border-primary bg-primary/10 text-primary"
                      : "border-border text-muted-foreground hover:bg-accent",
                  )}
                >
                  {p.label}
                </button>
              ))}
            </div>
            <p className="mt-2 text-[11px] text-muted-foreground">
              {REPEAT_PRESETS.find((p) => p.value === preset)?.hint}
            </p>
          </div>

          {preset === "custom" && (
            <Field label="Re-fire every (minutes)">
              <input
                type="number"
                min={1}
                value={customMinutes}
                onChange={(e) =>
                  setCustomMinutes(Math.max(1, Number(e.target.value) || 1))
                }
                className="h-9 w-32 rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </Field>
          )}

          <Summary
            text={text}
            platforms={platforms}
            mediaCount={mediaPayload().length}
          />

          {planLimit && <PlanLimitAlert limit={planLimit} />}

          {error && (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-border px-5 py-3">
          <button
            type="button"
            onClick={onClose}
            className="h-9 rounded-md px-3 text-sm hover:bg-accent"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={!canSubmit}
            onClick={() => void submit()}
            className="flex h-9 items-center gap-1.5 rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-60"
          >
            {submitting ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <CalendarClock className="h-3.5 w-3.5" />
            )}
            Schedule
          </button>
        </div>
      </div>
    </>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium">{label}</span>
      {children}
    </label>
  );
}

function Summary({
  text,
  platforms,
  mediaCount,
}: {
  text: string;
  platforms: string[];
  mediaCount: number;
}) {
  return (
    <div className="rounded-md border border-border bg-muted/30 p-3 text-xs">
      <div className="font-medium text-foreground">Will publish</div>
      <ul className="mt-1 space-y-0.5 text-muted-foreground">
        <li>
          <span className="font-medium">Text:</span>{" "}
          {text.trim() ? (
            <span>{text.slice(0, 100)}{text.length > 100 ? "…" : ""}</span>
          ) : (
            <span className="italic text-amber-700">empty — write something first</span>
          )}
        </li>
        <li>
          <span className="font-medium">Platforms:</span>{" "}
          {platforms.length > 0 ? (
            platforms.join(", ")
          ) : (
            <span className="italic text-amber-700">none — pick at least one</span>
          )}
        </li>
        <li>
          <span className="font-medium">Media:</span> {mediaCount} attached
        </li>
      </ul>
    </div>
  );
}
