import { api } from "./api";

export type Role = "admin" | "editor" | "viewer";

export type TeamInfo = {
  id: number;
  name: string;
  slug: string;
  created_at: string | null;
};

export type Member = {
  id: number;
  user_id: number;
  email: string;
  display_name: string;
  is_admin: boolean;
  role: Role;
  joined_at: string | null;
};

export type TeamResponse = {
  team: TeamInfo | null;
  role: Role | null;
  members: Member[];
};

export const ROLES: Role[] = ["admin", "editor", "viewer"];

export const ROLE_DESCRIPTIONS: Record<Role, string> = {
  admin: "Full access — invite members, edit and approve drafts, change settings.",
  editor: "Can compose, edit, and submit drafts for approval.",
  viewer: "Read-only access to drafts and analytics.",
};

export const teamApi = {
  get: () => api.get<TeamResponse>("/api/team"),
  create: (name: string) =>
    api.post<{ ok: true; team_id: number; slug: string }>("/api/team", {
      name,
    }),
  invite: (email: string, role: Role) =>
    api.post<{ ok: true; user_id: number; display_name: string }>(
      "/api/team/invite",
      { email, role },
    ),
  changeRole: (memberId: number, role: Role) =>
    api.post<{ ok: true }>(`/api/team/members/${memberId}/role`, { role }),
  remove: (memberId: number) =>
    api.post<{ ok: true }>(`/api/team/members/${memberId}/remove`),
  toggleSiteAdmin: (userId: number, isAdmin: boolean) =>
    api.post<{ ok: true; is_admin: boolean }>(
      `/api/team/members/${userId}/site-admin`,
      { is_admin: isAdmin },
    ),
};
