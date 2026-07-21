import { useEffect, useState } from "react";
import {
  Check,
  Copy,
  Hash,
  Image as ImageIcon,
  Loader2,
  Megaphone,
  Sparkles,
  Wand2,
  Wrench,
} from "lucide-react";
import { Link } from "react-router-dom";
import { ApiError } from "@/lib/api";
import {
  aiApi,
  type AIModelsResponse,
  type AIProviderInfo,
  type StructuredResponse,
} from "@/lib/ai";
import { cn } from "@/lib/utils";
import { PlatformBadge } from "@/components/PlatformBadge";

type Tab = "generate" | "studio" | "optimize" | "hashtags";

type Props = {
  text: string;
  selectedPlatforms: string[];
  onApplyText: (next: string) => void;
  onAppendText: (suffix: string) => void;
};

const STORAGE_KEY = "sp.ai.choice";

type StoredChoice = { provider: string; model: string };

function readStored(): StoredChoice | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as StoredChoice;
    if (parsed && typeof parsed.provider === "string") return parsed;
  } catch {
    // ignore
  }
  return null;
}

function writeStored(choice: StoredChoice) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(choice));
  } catch {
    // ignore
  }
}

export function AIAssistPanel({
  text,
  selectedPlatforms,
  onApplyText,
  onAppendText,
}: Props) {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<Tab>("generate");

  const [models, setModels] = useState<AIModelsResponse | null>(null);
  const [provider, setProvider] = useState<string>("");
  const [model, setModel] = useState<string>("");
  const [modelsError, setModelsError] = useState<string | null>(null);

  // Load model list whenever the panel is opened.
  useEffect(() => {
    if (!open || models) return;
    void aiApi
      .models()
      .then((data) => {
        setModels(data);
        const stored = readStored();
        const knownProvider = data.providers.find(
          (p) => p.provider === stored?.provider,
        );
        const initialProvider =
          knownProvider?.provider ||
          data.default_provider ||
          data.providers[0]?.provider ||
          "";
        setProvider(initialProvider);
        const initialModel =
          (stored?.model && stored.provider === initialProvider
            ? stored.model
            : null) ||
          data.providers.find((p) => p.provider === initialProvider)
            ?.user_default_model ||
          data.providers
            .find((p) => p.provider === initialProvider)
            ?.models.find((m) => m.is_default)?.model_id ||
          data.providers.find((p) => p.provider === initialProvider)?.models[0]
            ?.model_id ||
          "";
        setModel(initialModel);
      })
      .catch((err) => {
        setModelsError(
          err instanceof ApiError ? err.message : "Failed to load AI providers",
        );
      });
  }, [open, models]);

  // Persist choice changes.
  useEffect(() => {
    if (provider) writeStored({ provider, model });
  }, [provider, model]);

  function changeProvider(next: string) {
    setProvider(next);
    const info = models?.providers.find((p) => p.provider === next);
    const m =
      info?.user_default_model ||
      info?.models.find((x) => x.is_default)?.model_id ||
      info?.models[0]?.model_id ||
      "";
    setModel(m);
  }

  const aiOpts = { provider: provider || undefined, model: model || undefined };
  const hasAnyProvider = (models?.providers.length ?? 0) > 0;

  return (
    <div className="rounded-lg border border-border bg-background">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-center gap-2 px-4 py-2.5 text-left"
      >
        <span className="grid h-7 w-7 place-items-center rounded-md bg-primary/10 text-primary">
          <Sparkles className="h-4 w-4" />
        </span>
        <span className="flex-1">
          <span className="block text-sm font-semibold">AI assist</span>
          <span className="block text-xs text-muted-foreground">
            Generate posts, build a multi-output package, optimize per platform, or suggest hashtags.
          </span>
        </span>
        <span className="text-xs text-muted-foreground">{open ? "Hide" : "Show"}</span>
      </button>

      {open && (
        <div className="border-t border-border">
          <ProviderBar
            models={models}
            modelsError={modelsError}
            provider={provider}
            model={model}
            onProvider={changeProvider}
            onModel={setModel}
          />

          {!hasAnyProvider && models && (
            <div className="border-b border-border bg-amber-50 px-4 py-2 text-xs text-amber-900">
              No AI providers available yet.{" "}
              <Link to="/settings" className="font-medium underline underline-offset-2">
                Add your own key in Settings →
              </Link>
            </div>
          )}

          <div className="flex border-b border-border bg-muted/30">
            <TabButton active={tab === "generate"} onClick={() => setTab("generate")}>
              <Sparkles className="h-3.5 w-3.5" />
              Generate
            </TabButton>
            <TabButton active={tab === "studio"} onClick={() => setTab("studio")}>
              <Wrench className="h-3.5 w-3.5" />
              Studio
            </TabButton>
            <TabButton active={tab === "optimize"} onClick={() => setTab("optimize")}>
              <Wand2 className="h-3.5 w-3.5" />
              Optimize
            </TabButton>
            <TabButton active={tab === "hashtags"} onClick={() => setTab("hashtags")}>
              <Hash className="h-3.5 w-3.5" />
              Hashtags
            </TabButton>
          </div>

          <div className="p-4">
            {tab === "generate" && (
              <GenerateTab
                selectedPlatforms={selectedPlatforms}
                hasText={text.trim().length > 0}
                aiOpts={aiOpts}
                disabled={!hasAnyProvider}
                onApply={onApplyText}
              />
            )}
            {tab === "studio" && (
              <StudioTab
                selectedPlatforms={selectedPlatforms}
                hasText={text.trim().length > 0}
                aiOpts={aiOpts}
                disabled={!hasAnyProvider}
                onApplyCaption={onApplyText}
                onAppend={onAppendText}
              />
            )}
            {tab === "optimize" && (
              <OptimizeTab
                text={text}
                selectedPlatforms={selectedPlatforms}
                aiOpts={aiOpts}
                disabled={!hasAnyProvider}
                onApply={onApplyText}
              />
            )}
            {tab === "hashtags" && (
              <HashtagsTab
                text={text}
                selectedPlatforms={selectedPlatforms}
                aiOpts={aiOpts}
                disabled={!hasAnyProvider}
                onAppend={onAppendText}
              />
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function ProviderBar({
  models,
  modelsError,
  provider,
  model,
  onProvider,
  onModel,
}: {
  models: AIModelsResponse | null;
  modelsError: string | null;
  provider: string;
  model: string;
  onProvider: (v: string) => void;
  onModel: (v: string) => void;
}) {
  if (modelsError) {
    return (
      <div className="border-b border-border px-4 py-2 text-xs text-red-700">
        {modelsError}
      </div>
    );
  }
  if (!models) {
    return (
      <div className="border-b border-border px-4 py-2 text-xs text-muted-foreground">
        Loading providers…
      </div>
    );
  }
  const current: AIProviderInfo | undefined = models.providers.find(
    (p) => p.provider === provider,
  );

  return (
    <div className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-2 text-xs">
      <span className="text-muted-foreground">Using</span>
      <select
        value={provider}
        onChange={(e) => onProvider(e.target.value)}
        disabled={models.providers.length === 0}
        className="h-7 rounded-md border border-input bg-background px-2 text-xs focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-60"
      >
        {models.providers.length === 0 && <option value="">none configured</option>}
        {models.providers.map((p) => (
          <option key={p.provider} value={p.provider}>
            {p.provider_display}
            {p.user_key_set ? " · your key" : " · workspace"}
          </option>
        ))}
      </select>
      <select
        value={model}
        onChange={(e) => onModel(e.target.value)}
        disabled={!current}
        className="h-7 rounded-md border border-input bg-background px-2 text-xs focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-60"
      >
        {current?.models.map((m) => (
          <option key={m.model_id} value={m.model_id}>
            {m.display_name}
          </option>
        ))}
      </select>
      <Link
        to="/settings"
        className="ml-auto text-[11px] font-medium text-primary hover:underline"
      >
        Manage keys
      </Link>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex flex-1 items-center justify-center gap-1.5 px-3 py-2 text-xs font-medium transition-colors",
        active
          ? "border-b-2 border-primary text-primary"
          : "border-b-2 border-transparent text-muted-foreground hover:text-foreground",
      )}
    >
      {children}
    </button>
  );
}

type AIOpts = { provider?: string; model?: string };

function GenerateTab({
  selectedPlatforms,
  hasText,
  aiOpts,
  disabled,
  onApply,
}: {
  selectedPlatforms: string[];
  hasText: boolean;
  aiOpts: AIOpts;
  disabled: boolean;
  onApply: (next: string) => void;
}) {
  const [topic, setTopic] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    if (!topic.trim()) return;
    if (hasText && !confirm("Replace your current draft with the generated text?")) return;
    setBusy(true);
    setError(null);
    try {
      const { text } = await aiApi.generate({
        topic: topic.trim(),
        platforms: selectedPlatforms,
        ...aiOpts,
      });
      onApply(text);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Generation failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-2">
      <label className="block">
        <span className="mb-1 block text-xs font-medium">Topic or prompt</span>
        <input
          type="text"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !busy) {
              e.preventDefault();
              void run();
            }
          }}
          placeholder="e.g. Launch announcement for our new pricing plan"
          className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        />
      </label>
      {selectedPlatforms.length === 0 && (
        <p className="text-[11px] text-muted-foreground">
          Tip: select platforms first to tailor the output.
        </p>
      )}
      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
          {error}
        </div>
      )}
      <div className="flex justify-end">
        <button
          type="button"
          onClick={() => void run()}
          disabled={busy || !topic.trim() || disabled}
          className="flex h-8 items-center gap-1.5 rounded-md bg-primary px-3 text-xs font-medium text-primary-foreground hover:opacity-90 disabled:opacity-60"
        >
          {busy ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <Sparkles className="h-3 w-3" />
          )}
          Generate
        </button>
      </div>
    </div>
  );
}

const TONE_OPTIONS = [
  { value: "", label: "Default" },
  { value: "professional", label: "Professional" },
  { value: "casual", label: "Casual" },
  { value: "funny", label: "Funny" },
  { value: "inspirational", label: "Inspirational" },
  { value: "informative", label: "Informative" },
];

const GOAL_OPTIONS = [
  { value: "", label: "Pick a goal" },
  { value: "engagement", label: "Engagement" },
  { value: "awareness", label: "Awareness" },
  { value: "sales", label: "Sales / conversion" },
  { value: "education", label: "Education" },
  { value: "support", label: "Support / community" },
];

function StudioTab({
  selectedPlatforms,
  hasText,
  aiOpts,
  disabled,
  onApplyCaption,
  onAppend,
}: {
  selectedPlatforms: string[];
  hasText: boolean;
  aiOpts: AIOpts;
  disabled: boolean;
  onApplyCaption: (next: string) => void;
  onAppend: (suffix: string) => void;
}) {
  const [topic, setTopic] = useState("");
  const [audience, setAudience] = useState("");
  const [goal, setGoal] = useState("");
  const [tone, setTone] = useState("");
  const [creativity, setCreativity] = useState(0.7);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<StructuredResponse | null>(null);

  async function run() {
    if (!topic.trim()) return;
    if (
      hasText &&
      result === null &&
      !confirm("Generate a fresh content package for the current draft?")
    )
      return;
    setBusy(true);
    setError(null);
    try {
      const res = await aiApi.generateStructured({
        topic: topic.trim(),
        platforms: selectedPlatforms,
        audience: audience.trim() || undefined,
        goal: goal || undefined,
        tone: tone || undefined,
        temperature: creativity,
        ...aiOpts,
      });
      setResult(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Generation failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">
        Generate a ready-to-post package: caption, hashtags, image idea, and CTA.
      </p>

      <label className="block">
        <span className="mb-1 block text-xs font-medium">Topic</span>
        <input
          type="text"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          placeholder="What is this post about?"
          className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        />
      </label>

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        <label className="block">
          <span className="mb-1 block text-xs font-medium">Audience</span>
          <input
            type="text"
            value={audience}
            onChange={(e) => setAudience(e.target.value)}
            placeholder="e.g. small business owners"
            className="h-8 w-full rounded-md border border-input bg-background px-2 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-xs font-medium">Goal</span>
          <select
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            className="h-8 w-full rounded-md border border-input bg-background px-2 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
          >
            {GOAL_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="mb-1 block text-xs font-medium">Tone</span>
          <select
            value={tone}
            onChange={(e) => setTone(e.target.value)}
            className="h-8 w-full rounded-md border border-input bg-background px-2 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
          >
            {TONE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="mb-1 flex items-center justify-between text-xs font-medium">
            <span>Creativity</span>
            <span className="font-mono text-[10px] text-muted-foreground">
              {creativity.toFixed(2)}
            </span>
          </span>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={creativity}
            onChange={(e) => setCreativity(Number(e.target.value))}
            className="w-full accent-primary"
          />
        </label>
      </div>

      {selectedPlatforms.length === 0 && (
        <p className="text-[11px] text-muted-foreground">
          Tip: select platforms first to tailor the output.
        </p>
      )}

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
          {error}
        </div>
      )}

      <div className="flex justify-end">
        <button
          type="button"
          onClick={() => void run()}
          disabled={busy || !topic.trim() || disabled}
          className="flex h-8 items-center gap-1.5 rounded-md bg-primary px-3 text-xs font-medium text-primary-foreground hover:opacity-90 disabled:opacity-60"
        >
          {busy ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <Wrench className="h-3 w-3" />
          )}
          Generate package
        </button>
      </div>

      {result && (
        <div className="space-y-2 rounded-md border border-border bg-muted/10 p-3">
          <OutputBlock
            icon={<Sparkles className="h-3.5 w-3.5 text-primary" />}
            title="Caption"
            value={result.caption}
            actions={
              <button
                type="button"
                onClick={() => onApplyCaption(result.caption)}
                className="h-6 rounded-md bg-primary px-2 text-[11px] font-medium text-primary-foreground hover:opacity-90"
              >
                Apply
              </button>
            }
          />
          <OutputBlock
            icon={<Hash className="h-3.5 w-3.5 text-primary" />}
            title="Hashtags"
            value={result.hashtags.join(" ")}
            empty={result.hashtags.length === 0}
            actions={
              result.hashtags.length > 0 ? (
                <button
                  type="button"
                  onClick={() => onAppend(result.hashtags.join(" "))}
                  className="h-6 rounded-md border border-border bg-background px-2 text-[11px] font-medium hover:bg-accent"
                >
                  Append
                </button>
              ) : null
            }
          >
            {result.hashtags.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {result.hashtags.map((t) => (
                  <button
                    key={t}
                    type="button"
                    onClick={() => onAppend(t.startsWith("#") ? t : `#${t}`)}
                    className="rounded-full border border-border bg-background px-2 py-0.5 text-[10px] font-medium hover:border-primary hover:bg-primary/5 hover:text-primary"
                  >
                    {t.startsWith("#") ? t : `#${t}`}
                  </button>
                ))}
              </div>
            )}
          </OutputBlock>
          <OutputBlock
            icon={<ImageIcon className="h-3.5 w-3.5 text-primary" />}
            title="Image idea"
            value={result.image_idea}
            empty={!result.image_idea}
            copyable
          />
          <OutputBlock
            icon={<Megaphone className="h-3.5 w-3.5 text-primary" />}
            title="Call-to-action"
            value={result.cta}
            empty={!result.cta}
            actions={
              result.cta ? (
                <button
                  type="button"
                  onClick={() => onAppend(`\n\n${result.cta}`)}
                  className="h-6 rounded-md border border-border bg-background px-2 text-[11px] font-medium hover:bg-accent"
                >
                  Append
                </button>
              ) : null
            }
          />
        </div>
      )}

      {selectedPlatforms.length > 0 && result && (
        <p className="text-[11px] text-muted-foreground">
          Tailored for{" "}
          {selectedPlatforms.map((p, i) => (
            <span key={p}>
              <PlatformBadge platform={p} />
              {i < selectedPlatforms.length - 1 ? " " : ""}
            </span>
          ))}
          .
        </p>
      )}
    </div>
  );
}

function OutputBlock({
  icon,
  title,
  value,
  empty,
  copyable,
  actions,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  value: string;
  empty?: boolean;
  copyable?: boolean;
  actions?: React.ReactNode;
  children?: React.ReactNode;
}) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // ignore
    }
  }

  return (
    <div className="rounded-md border border-border bg-background p-2.5">
      <div className="mb-1 flex items-center justify-between gap-2">
        <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground">
          {icon}
          {title}
        </span>
        <div className="flex items-center gap-1">
          {actions}
          {copyable && value && (
            <button
              type="button"
              onClick={() => void copy()}
              className="grid h-6 w-6 place-items-center rounded-md border border-border hover:bg-accent"
              aria-label={`Copy ${title}`}
            >
              {copied ? (
                <Check className="h-3 w-3 text-emerald-600" />
              ) : (
                <Copy className="h-3 w-3" />
              )}
            </button>
          )}
        </div>
      </div>
      {empty ? (
        <p className="text-xs text-muted-foreground italic">— not provided</p>
      ) : children ? (
        children
      ) : (
        <p className="whitespace-pre-wrap text-xs">{value}</p>
      )}
    </div>
  );
}

function OptimizeTab({
  text,
  selectedPlatforms,
  aiOpts,
  disabled,
  onApply,
}: {
  text: string;
  selectedPlatforms: string[];
  aiOpts: AIOpts;
  disabled: boolean;
  onApply: (next: string) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<Record<string, string> | null>(null);

  async function run() {
    setBusy(true);
    setError(null);
    setResults(null);
    try {
      const { optimized } = await aiApi.optimize({
        text,
        platforms: selectedPlatforms,
        ...aiOpts,
      });
      setResults(optimized);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Optimize failed");
    } finally {
      setBusy(false);
    }
  }

  const canRun =
    text.trim().length > 0 && selectedPlatforms.length > 0 && !busy && !disabled;

  return (
    <div className="space-y-2">
      <p className="text-xs text-muted-foreground">
        Rewrite your current draft tailored to each selected platform. Pick one
        version to apply.
      </p>
      {(text.trim().length === 0 || selectedPlatforms.length === 0) && (
        <p className="text-[11px] text-amber-700">
          Enter some text and select at least one platform first.
        </p>
      )}
      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
          {error}
        </div>
      )}
      <div className="flex justify-end">
        <button
          type="button"
          onClick={() => void run()}
          disabled={!canRun}
          className="flex h-8 items-center gap-1.5 rounded-md bg-primary px-3 text-xs font-medium text-primary-foreground hover:opacity-90 disabled:opacity-60"
        >
          {busy ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <Wand2 className="h-3 w-3" />
          )}
          Optimize for {selectedPlatforms.length || "—"}{" "}
          {selectedPlatforms.length === 1 ? "platform" : "platforms"}
        </button>
      </div>

      {results && (
        <ul className="mt-3 space-y-2">
          {Object.entries(results).map(([platform, body]) => (
            <li
              key={platform}
              className="rounded-md border border-border bg-muted/20 p-3"
            >
              <div className="mb-1 flex items-center justify-between">
                <PlatformBadge platform={platform} />
                <button
                  type="button"
                  onClick={() => onApply(body)}
                  className="h-6 rounded-md bg-primary px-2 text-[11px] font-medium text-primary-foreground hover:opacity-90"
                >
                  Apply
                </button>
              </div>
              <pre className="whitespace-pre-wrap text-xs">{body}</pre>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function HashtagsTab({
  text,
  selectedPlatforms,
  aiOpts,
  disabled,
  onAppend,
}: {
  text: string;
  selectedPlatforms: string[];
  aiOpts: AIOpts;
  disabled: boolean;
  onAppend: (suffix: string) => void;
}) {
  const [platform, setPlatform] = useState(selectedPlatforms[0] ?? "");
  const [count, setCount] = useState(5);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tags, setTags] = useState<string[] | null>(null);

  async function run() {
    if (!platform || !text.trim()) return;
    setBusy(true);
    setError(null);
    setTags(null);
    try {
      const { hashtags } = await aiApi.hashtags({
        text,
        platform,
        count,
        ...aiOpts,
      });
      setTags(hashtags);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Hashtag suggestion failed");
    } finally {
      setBusy(false);
    }
  }

  const platformOptions =
    selectedPlatforms.length > 0
      ? selectedPlatforms
      : ["linkedin", "twitter", "facebook", "instagram"];

  return (
    <div className="space-y-2">
      <p className="text-xs text-muted-foreground">
        Suggest hashtags based on your draft. Click a tag to append it.
      </p>

      <div className="flex flex-wrap items-end gap-2">
        <label>
          <span className="mb-1 block text-xs font-medium">Platform</span>
          <select
            value={platform}
            onChange={(e) => setPlatform(e.target.value)}
            className="h-8 rounded-md border border-input bg-background px-2 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="">Pick one…</option>
            {platformOptions.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="mb-1 block text-xs font-medium">How many</span>
          <input
            type="number"
            min={1}
            max={20}
            value={count}
            onChange={(e) =>
              setCount(Math.max(1, Math.min(20, Number(e.target.value) || 5)))
            }
            className="h-8 w-20 rounded-md border border-input bg-background px-2 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </label>
        <button
          type="button"
          onClick={() => void run()}
          disabled={busy || !platform || !text.trim() || disabled}
          className="flex h-8 items-center gap-1.5 rounded-md bg-primary px-3 text-xs font-medium text-primary-foreground hover:opacity-90 disabled:opacity-60"
        >
          {busy ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <Hash className="h-3 w-3" />
          )}
          Suggest
        </button>
      </div>

      {text.trim().length === 0 && (
        <p className="text-[11px] text-amber-700">Write some text first.</p>
      )}

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
          {error}
        </div>
      )}

      {tags && (
        <div className="mt-2">
          {tags.length === 0 ? (
            <p className="text-xs text-muted-foreground">
              No suggestions returned.
            </p>
          ) : (
            <>
              <div className="flex flex-wrap gap-1.5">
                {tags.map((t) => (
                  <button
                    key={t}
                    type="button"
                    onClick={() =>
                      onAppend(t.startsWith("#") ? t : `#${t}`)
                    }
                    className="rounded-full border border-border bg-background px-2 py-1 text-[11px] font-medium hover:border-primary hover:bg-primary/5 hover:text-primary"
                  >
                    {t.startsWith("#") ? t : `#${t}`}
                  </button>
                ))}
              </div>
              <button
                type="button"
                onClick={() =>
                  onAppend(
                    tags
                      .map((t) => (t.startsWith("#") ? t : `#${t}`))
                      .join(" "),
                  )
                }
                className="mt-2 text-[11px] font-medium text-primary hover:underline"
              >
                Append all
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
