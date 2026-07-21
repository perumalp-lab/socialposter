import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  Crown,
  Loader2,
  Mail,
  ShieldCheck,
  UserPlus,
  Users,
  X,
} from "lucide-react";
import { useAuth } from "@/auth/AuthContext";
import { ApiError } from "@/lib/api";
import {
  ROLES,
  ROLE_DESCRIPTIONS,
  teamApi,
  type Member,
  type Role,
  type TeamResponse,
} from "@/lib/team";
import { cn } from "@/lib/utils";

export function TeamPage() {
  const [data, setData] = useState<TeamResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await teamApi.get();
      setData(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load team");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Team</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Members, roles, and approvals.
        </p>
      </div>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      {loading && !data ? (
        <div className="text-sm text-muted-foreground">Loading…</div>
      ) : !data?.team ? (
        <CreateTeam onCreated={refresh} />
      ) : (
        <Workspace data={data} onRefresh={refresh} />
      )}
    </div>
  );
}

function CreateTeam({ onCreated }: { onCreated: () => Promise<void> }) {
  const [name, setName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setErr(null);
    try {
      await teamApi.create(name.trim());
      await onCreated();
    } catch (e2) {
      setErr(e2 instanceof ApiError ? e2.message : "Create failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="rounded-lg border border-dashed border-border bg-background p-8">
      <div className="mx-auto max-w-md text-center">
        <Users className="mx-auto h-8 w-8 text-muted-foreground" />
        <h2 className="mt-3 text-base font-semibold">You're not on a team yet</h2>
        <p className="mt-1 text-xs text-muted-foreground">
          Create a workspace to invite collaborators and share drafts, media,
          and approvals.
        </p>
        <form onSubmit={onSubmit} className="mt-5 flex gap-2">
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Team name"
            className="h-9 flex-1 rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
          <button
            type="submit"
            disabled={submitting || !name.trim()}
            className="flex h-9 items-center gap-2 rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-60"
          >
            {submitting ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <UserPlus className="h-4 w-4" />
            )}
            Create
          </button>
        </form>
        {err && (
          <div className="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-left text-xs text-red-700">
            {err}
          </div>
        )}
      </div>
    </div>
  );
}

function Workspace({
  data,
  onRefresh,
}: {
  data: TeamResponse;
  onRefresh: () => Promise<void>;
}) {
  const { user } = useAuth();
  const isAdmin = data.role === "admin";

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-border bg-background p-5">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="text-xs text-muted-foreground">Workspace</div>
            <h2 className="text-lg font-semibold">{data.team!.name}</h2>
            <div className="mt-0.5 text-xs text-muted-foreground">
              /{data.team!.slug} ·{" "}
              {data.members.length} member
              {data.members.length === 1 ? "" : "s"}
            </div>
          </div>
          <RolePill role={data.role!} className="self-start" />
        </div>
      </div>

      {isAdmin && <InviteForm onInvited={onRefresh} />}

      <div className="rounded-lg border border-border bg-background">
        <header className="border-b border-border px-5 py-3">
          <h2 className="text-sm font-semibold">Members</h2>
        </header>
        <ul className="divide-y divide-border">
          {data.members.map((m) => (
            <MemberRow
              key={m.id}
              member={m}
              isAdmin={isAdmin}
              isSelf={m.user_id === user?.id}
              isSiteAdmin={!!user?.is_admin}
              onRefresh={onRefresh}
            />
          ))}
        </ul>
      </div>

      <div className="rounded-lg border border-border bg-muted/30 p-4 text-xs text-muted-foreground">
        <div className="mb-1 font-medium text-foreground">Role reference</div>
        <ul className="space-y-1">
          {ROLES.map((r) => (
            <li key={r}>
              <span className="font-medium capitalize text-foreground">
                {r}:
              </span>{" "}
              {ROLE_DESCRIPTIONS[r]}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function InviteForm({ onInvited }: { onInvited: () => Promise<void> }) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("editor");
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setErr(null);
    setOk(null);
    try {
      const res = await teamApi.invite(email.trim().toLowerCase(), role);
      setOk(`Added ${res.display_name}`);
      setEmail("");
      await onInvited();
    } catch (e2) {
      setErr(e2 instanceof ApiError ? e2.message : "Invite failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="rounded-lg border border-border bg-background p-5">
      <div className="mb-3 flex items-center gap-2">
        <UserPlus className="h-4 w-4 text-muted-foreground" />
        <h2 className="text-sm font-semibold">Invite a member</h2>
      </div>
      <form onSubmit={onSubmit} className="flex flex-wrap items-end gap-2">
        <label className="flex-1 min-w-[200px]">
          <span className="mb-1 block text-xs font-medium">Email</span>
          <div className="relative">
            <Mail className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="user@example.com"
              className="h-9 w-full rounded-md border border-input bg-background pl-8 pr-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
        </label>
        <label>
          <span className="mb-1 block text-xs font-medium">Role</span>
          <select
            value={role}
            onChange={(e) => setRole(e.target.value as Role)}
            className="h-9 rounded-md border border-input bg-background px-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          >
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {r[0].toUpperCase() + r.slice(1)}
              </option>
            ))}
          </select>
        </label>
        <button
          type="submit"
          disabled={submitting || !email.trim()}
          className="flex h-9 items-center gap-2 rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-60"
        >
          {submitting ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <UserPlus className="h-4 w-4" />
          )}
          Invite
        </button>
      </form>
      <p className="mt-2 text-[11px] text-muted-foreground">
        The user must already have an account. Invites accept any registered
        email.
      </p>
      {err && (
        <div className="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
          {err}
        </div>
      )}
      {ok && (
        <div className="mt-3 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-800">
          {ok}
        </div>
      )}
    </div>
  );
}

function MemberRow({
  member,
  isAdmin,
  isSelf,
  isSiteAdmin,
  onRefresh,
}: {
  member: Member;
  isAdmin: boolean;
  isSelf: boolean;
  isSiteAdmin: boolean;
  onRefresh: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function changeRole(role: Role) {
    setBusy(true);
    setErr(null);
    try {
      await teamApi.changeRole(member.id, role);
      await onRefresh();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Failed");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!confirm(`Remove ${member.display_name || member.email} from the team?`)) return;
    setBusy(true);
    setErr(null);
    try {
      await teamApi.remove(member.id);
      await onRefresh();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Remove failed");
    } finally {
      setBusy(false);
    }
  }

  async function toggleSiteAdmin() {
    setBusy(true);
    setErr(null);
    try {
      await teamApi.toggleSiteAdmin(member.user_id, !member.is_admin);
      await onRefresh();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Failed");
    } finally {
      setBusy(false);
    }
  }

  const initials = (member.display_name || member.email)
    .split(/\s+/)
    .map((s) => s[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <li className="flex flex-wrap items-center gap-3 px-5 py-3">
      <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
        {initials || "?"}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 text-sm">
          <span className="truncate font-medium">
            {member.display_name || member.email}
          </span>
          {isSelf && (
            <span className="rounded-full bg-muted px-1.5 text-[10px] font-medium text-muted-foreground">
              you
            </span>
          )}
          {member.is_admin && (
            <span
              className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-1.5 text-[10px] font-medium text-amber-700"
              title="Site admin"
            >
              <Crown className="h-2.5 w-2.5" />
              site admin
            </span>
          )}
        </div>
        <div className="truncate text-xs text-muted-foreground">{member.email}</div>
        {member.joined_at && (
          <div className="text-[10px] text-muted-foreground">
            Joined {new Date(member.joined_at).toLocaleDateString()}
          </div>
        )}
      </div>

      <div className="flex shrink-0 items-center gap-2">
        {isAdmin && !isSelf ? (
          <select
            value={member.role}
            disabled={busy}
            onChange={(e) => void changeRole(e.target.value as Role)}
            className="h-8 rounded-md border border-input bg-background px-2 text-xs focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-60"
          >
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        ) : (
          <RolePill role={member.role} />
        )}

        {isSiteAdmin && !isSelf && (
          <button
            type="button"
            onClick={() => void toggleSiteAdmin()}
            disabled={busy}
            title={member.is_admin ? "Revoke site-admin" : "Grant site-admin"}
            className={cn(
              "grid h-8 w-8 place-items-center rounded-md text-muted-foreground hover:bg-accent",
              member.is_admin && "text-amber-600",
            )}
          >
            <ShieldCheck className="h-4 w-4" />
          </button>
        )}

        {isAdmin && !isSelf && (
          <button
            type="button"
            onClick={() => void remove()}
            disabled={busy}
            aria-label="Remove member"
            className="grid h-8 w-8 place-items-center rounded-md text-muted-foreground hover:bg-red-50 hover:text-red-600 disabled:opacity-60"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>
      {err && (
        <div className="basis-full text-right text-[11px] text-red-700">
          {err}
        </div>
      )}
    </li>
  );
}

function RolePill({
  role,
  className,
}: {
  role: Role;
  className?: string;
}) {
  const map: Record<Role, string> = {
    admin: "bg-amber-100 text-amber-800",
    editor: "bg-blue-100 text-blue-700",
    viewer: "bg-muted text-muted-foreground",
  };
  return (
    <span
      className={cn(
        "rounded-full px-2 py-0.5 text-[10px] font-semibold capitalize",
        map[role],
        className,
      )}
    >
      {role}
    </span>
  );
}
