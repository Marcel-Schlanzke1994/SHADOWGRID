import { ShadowgridClient } from "@shadowgrid/api-client";
import type { User } from "@shadowgrid/shared-types";
import { create } from "zustand";

type AuthStatus = "loading" | "anonymous" | "authenticated";
interface AuthState {
  accessToken: string | null;
  user: User | null;
  status: AuthStatus;
  setSession: (accessToken: string, user: User) => void;
  clear: () => void;
  setStatus: (status: AuthStatus) => void;
}

export const useAuth = create<AuthState>((set) => ({
  accessToken: null,
  user: null,
  status: "loading",
  setSession: (accessToken, user) =>
    set({ accessToken, user, status: "authenticated" }),
  clear: () => set({ accessToken: null, user: null, status: "anonymous" }),
  setStatus: (status) => set({ status }),
}));

let refreshPromise: Promise<boolean> | null = null;
const refresh = (): Promise<boolean> => {
  if (refreshPromise) return refreshPromise;
  refreshPromise = fetch("/api/v1/auth/refresh", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: "{}",
  })
    .then(async (response) => {
      if (!response.ok) {
        useAuth.getState().clear();
        return false;
      }
      const tokens = (await response.json()) as { access_token: string };
      useAuth.setState({ accessToken: tokens.access_token });
      const user = await client.get<User>("/api/v1/auth/me");
      useAuth.getState().setSession(tokens.access_token, user);
      return true;
    })
    .catch(() => {
      useAuth.getState().clear();
      return false;
    })
    .finally(() => {
      refreshPromise = null;
    });
  return refreshPromise;
};

export const client = new ShadowgridClient({
  baseUrl: "/api/v1",
  getAccessToken: () => useAuth.getState().accessToken,
  onUnauthorized: refresh,
});

export const bootstrapAuth = refresh;

export const login = async (
  email: string,
  password: string,
  totp?: string,
): Promise<void> => {
  const tokens = await client.post<{ access_token: string }>("/auth/login", {
    email,
    password,
    totp_code: totp || undefined,
  });
  useAuth.setState({ accessToken: tokens.access_token });
  const user = await client.get<User>("/auth/me");
  useAuth.getState().setSession(tokens.access_token, user);
};

export const logout = async (): Promise<void> => {
  try {
    await client.post("/auth/logout");
  } finally {
    useAuth.getState().clear();
  }
};
