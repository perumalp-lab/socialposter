import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { ApiError, api } from "@/lib/api";

export type User = {
  id: number;
  email: string;
  display_name: string;
  is_admin: boolean;
};

type AuthState =
  | { status: "loading"; user: null }
  | { status: "unauthenticated"; user: null }
  | { status: "authenticated"; user: User };

type AuthContextValue = AuthState & {
  login: (email: string, password: string) => Promise<void>;
  signup: (input: SignupInput) => Promise<void>;
  logout: () => Promise<void>;
  updateProfile: (input: { display_name?: string; timezone?: string }) => Promise<User>;
  changePassword: (input: {
    current_password: string;
    new_password: string;
  }) => Promise<void>;
};

type SignupInput = {
  email: string;
  password: string;
  display_name?: string;
  timezone?: string;
};

const Ctx = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: "loading", user: null });

  const refresh = useCallback(async () => {
    try {
      const { user } = await api.get<{ user: User }>("/api/auth/me");
      setState({ status: "authenticated", user });
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setState({ status: "unauthenticated", user: null });
      } else {
        // Network errors etc. — treat as unauthenticated so UI is usable.
        setState({ status: "unauthenticated", user: null });
      }
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const login = useCallback(
    async (email: string, password: string) => {
      const { user } = await api.post<{ user: User }>("/api/auth/session-login", {
        email,
        password,
      });
      setState({ status: "authenticated", user });
    },
    [],
  );

  const signup = useCallback(async (input: SignupInput) => {
    const { user } = await api.post<{ user: User }>("/api/auth/session-signup", input);
    setState({ status: "authenticated", user });
  }, []);

  const logout = useCallback(async () => {
    await api.post("/api/auth/session-logout");
    setState({ status: "unauthenticated", user: null });
  }, []);

  const updateProfile = useCallback(
    async (input: { display_name?: string; timezone?: string }) => {
      const { user } = await api.put<{ user: User }>("/api/auth/profile", input);
      setState({ status: "authenticated", user });
      return user;
    },
    [],
  );

  const changePassword = useCallback(
    async (input: { current_password: string; new_password: string }) => {
      await api.post("/api/auth/password", input);
    },
    [],
  );

  const value = useMemo<AuthContextValue>(
    () => ({ ...state, login, signup, logout, updateProfile, changePassword }),
    [state, login, signup, logout, updateProfile, changePassword],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
