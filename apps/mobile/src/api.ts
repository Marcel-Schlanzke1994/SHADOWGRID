import Constants from "expo-constants";
import * as SecureStore from "expo-secure-store";
import { ShadowgridClient } from "@shadowgrid/api-client";

const REFRESH_KEY = "shadowgrid.refresh-token";
let accessToken: string | null = null;
const baseUrl =
  process.env.EXPO_PUBLIC_API_URL ??
  (Constants.expoConfig?.extra?.apiUrl as string) ??
  "http://localhost:8000/api/v1";

const refresh = async (): Promise<boolean> => {
  const refreshToken = await SecureStore.getItemAsync(REFRESH_KEY);
  if (!refreshToken) return false;
  const response = await fetch(`${baseUrl}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Client-Kind": "mobile" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!response.ok) {
    await SecureStore.deleteItemAsync(REFRESH_KEY);
    accessToken = null;
    return false;
  }
  const body = (await response.json()) as {
    access_token: string;
    refresh_token: string;
  };
  accessToken = body.access_token;
  await SecureStore.setItemAsync(REFRESH_KEY, body.refresh_token, {
    keychainAccessible: SecureStore.AFTER_FIRST_UNLOCK_THIS_DEVICE_ONLY,
  });
  return true;
};

export const api = new ShadowgridClient({
  baseUrl,
  getAccessToken: () => accessToken,
  onUnauthorized: refresh,
});
export const restoreSession = refresh;
export const signIn = async (
  email: string,
  password: string,
  totp_code?: string,
): Promise<void> => {
  const body = await api.post<{ access_token: string; refresh_token: string }>(
    "/auth/login",
    { email, password, totp_code },
    undefined,
  );
  accessToken = body.access_token;
  await SecureStore.setItemAsync(REFRESH_KEY, body.refresh_token, {
    keychainAccessible: SecureStore.AFTER_FIRST_UNLOCK_THIS_DEVICE_ONLY,
  });
};
export const signOut = async (): Promise<void> => {
  try {
    await api.post("/auth/logout");
  } finally {
    accessToken = null;
    await SecureStore.deleteItemAsync(REFRESH_KEY);
  }
};
