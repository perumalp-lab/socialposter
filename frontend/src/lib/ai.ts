import { api } from "./api";

export type AIModelOption = {
  model_id: string;
  display_name: string;
  is_default: boolean;
};

export type AIProviderInfo = {
  provider: string;
  provider_display: string;
  models: AIModelOption[];
  user_key_set: boolean;
  user_default_model: string | null;
  workspace_available: boolean;
};

export type AIModelsResponse = {
  providers: AIProviderInfo[];
  default_provider: string;
};

export type UserAIKey = {
  provider: string;
  default_model: string | null;
  is_default: boolean;
  masked: string;
};

export type GenerateRequest = {
  topic: string;
  platforms: string[];
  provider?: string;
  model?: string;
  temperature?: number;
};

export type StructuredRequest = {
  topic: string;
  platforms: string[];
  audience?: string;
  goal?: string;
  tone?: string;
  provider?: string;
  model?: string;
  temperature?: number;
};

export type StructuredResponse = {
  caption: string;
  hashtags: string[];
  image_idea: string;
  cta: string;
};

export type OptimizeRequest = {
  text: string;
  platforms: string[];
  provider?: string;
  model?: string;
  temperature?: number;
};

export type HashtagsRequest = {
  text: string;
  platform: string;
  count?: number;
  provider?: string;
  model?: string;
  temperature?: number;
};

export type AIPreferences = {
  cost_optimization: boolean;
};

export const aiApi = {
  models: () => api.get<AIModelsResponse>("/api/ai/models"),
  preferences: {
    get: () => api.get<AIPreferences>("/api/ai/preferences"),
    update: (body: Partial<AIPreferences>) =>
      api.put<AIPreferences & { ok: true }>("/api/ai/preferences", body),
  },
  generate: (input: GenerateRequest) =>
    api.post<{ text: string }>("/api/ai/generate", input),
  generateStructured: (input: StructuredRequest) =>
    api.post<StructuredResponse>("/api/ai/generate-structured", input),
  optimize: (input: OptimizeRequest) =>
    api.post<{ optimized: Record<string, string> }>("/api/ai/optimize", input),
  hashtags: (input: HashtagsRequest) =>
    api.post<{ hashtags: string[] }>("/api/ai/hashtags", input),
  userKeys: {
    list: () => api.get<UserAIKey[]>("/api/ai/user-keys"),
    upsert: (
      provider: string,
      body: { api_key?: string; default_model?: string },
    ) =>
      api.put<UserAIKey & { ok: true }>(
        `/api/ai/user-keys/${provider}`,
        body,
      ),
    remove: (provider: string) =>
      api.delete<{ ok: true }>(`/api/ai/user-keys/${provider}`),
    setDefault: (provider: string) =>
      api.post<{ ok: true }>(`/api/ai/user-keys/${provider}/default`),
  },
};

export const SUPPORTED_PROVIDERS = [
  { value: "claude", label: "Claude (Anthropic)" },
  { value: "openai", label: "OpenAI" },
  { value: "gemini", label: "Gemini (Google)" },
  { value: "perplexity", label: "Perplexity" },
] as const;

export const SUGGESTED_MODELS: Record<string, Array<{ id: string; label: string }>> = {
  claude: [
    { id: "claude-sonnet-4-5-20250929", label: "Claude Sonnet 4.5" },
    { id: "claude-opus-4-7", label: "Claude Opus 4.7" },
    { id: "claude-haiku-4-5-20251001", label: "Claude Haiku 4.5" },
  ],
  openai: [
    { id: "gpt-4o", label: "GPT-4o" },
    { id: "gpt-4o-mini", label: "GPT-4o mini" },
    { id: "o3-mini", label: "o3-mini" },
  ],
  gemini: [
    { id: "gemini-2.0-flash", label: "Gemini 2.0 Flash" },
    { id: "gemini-1.5-pro", label: "Gemini 1.5 Pro" },
  ],
  perplexity: [
    { id: "sonar", label: "Sonar" },
    { id: "sonar-pro", label: "Sonar Pro" },
  ],
};
