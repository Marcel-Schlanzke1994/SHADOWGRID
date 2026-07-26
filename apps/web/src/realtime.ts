import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { Profile } from "@shadowgrid/shared-types";
import { client, useAuth } from "./auth";

const multiplayerKeys = new Set([
  "alliances",
  "cartel-wars",
  "chat-channels",
  "chat-messages",
  "direct-messages",
  "market-offers",
  "notifications",
  "pvp-operations",
  "pvp-targets",
  "territories",
]);

export function useMultiplayerRealtime(): void {
  const token = useAuth((state) => state.accessToken);
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!token) return;
    let stopped = false;
    let socket: WebSocket | null = null;
    let reconnectTimer: number | undefined;

    const connect = async () => {
      try {
        const profile = await client.get<Profile>("/profiles/me");
        if (stopped) return;
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        socket = new WebSocket(
          `${protocol}//${window.location.host}/api/v1/ws`,
        );
        socket.addEventListener("open", () => {
          socket?.send(
            JSON.stringify({ access_token: token, world_id: profile.world_id }),
          );
        });
        socket.addEventListener("message", (event) => {
          const hint = JSON.parse(String(event.data)) as { type?: string };
          if (
            !hint.type ||
            hint.type === "connected" ||
            hint.type === "heartbeat"
          )
            return;
          void queryClient.invalidateQueries({
            predicate: (query) =>
              multiplayerKeys.has(String(query.queryKey[0])),
          });
        });
        socket.addEventListener("close", () => {
          if (!stopped)
            reconnectTimer = window.setTimeout(() => void connect(), 2_000);
        });
      } catch {
        if (!stopped)
          reconnectTimer = window.setTimeout(() => void connect(), 5_000);
      }
    };

    void connect();
    return () => {
      stopped = true;
      if (reconnectTimer) window.clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, [queryClient, token]);
}
