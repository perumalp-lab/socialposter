import { api } from "./api";

export type IntegrationSettings = {
  zapier_api_key: string;
  pabbly_api_key: string;
};

export const integrationsApi = {
  getSettings: () => api.get<IntegrationSettings>("/api/integrations/settings"),
  updateSettings: (data: Partial<IntegrationSettings>) =>
    api.put<IntegrationSettings>("/api/integrations/settings", data),
};
