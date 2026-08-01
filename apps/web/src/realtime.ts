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

const invalidationRoots: Record<string, readonly string[]> = {
  "player.resources.updated": ["profile", "resources"],
  "company.metrics.updated": ["companies", "economy-status"],
  "market.snapshot.created": ["companies", "economy-status"],
  "exchange.order.updated": ["exchange"],
  "exchange.trade.executed": ["exchange", "notifications"],
  "cartel.invitation.created": ["cartels", "notifications"],
  "cartel.project.updated": ["cartels"],
  "world.event.started": ["events", "news", "world-events"],
  "world.event.ended": ["events", "news", "world-events"],
  "notification.created": ["notifications", "notification-unread-count"],
  "season.phase.changed": ["season", "admin-seasons"],
};

interface RealtimeEnvelope {
  event_id: string;
  type: string;
  event_version: number;
  payload?: Record<string, unknown>;
}

function isRealtimeEnvelope(value: unknown): value is RealtimeEnvelope {
  if (!value || typeof value !== "object") return false;
  const envelope = value as Record<string, unknown>;
  return (
    typeof envelope.event_id === "string" &&
    typeof envelope.type === "string" &&
    envelope.event_version === 1 &&
    (envelope.payload === undefined ||
      (typeof envelope.payload === "object" &&
        envelope.payload !== null &&
        !Array.isArray(envelope.payload)))
  );
}

export function useMultiplayerRealtime(): void {
  const token = useAuth((state) => state.accessToken);
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!token) return;
    let stopped = false;
    let socket: WebSocket | null = null;
    let reconnectTimer: number | undefined;
    let reconnectAttempt = 0;
    let worldId = "";

    const connect = async () => {
      try {
        const profile = await client.get<Profile>("/profiles/me");
        if (stopped) return;
        worldId = profile.world_id;
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        socket = new WebSocket(
          `${protocol}//${window.location.host}/api/v1/ws`,
        );
        socket.addEventListener("open", () => {
          reconnectAttempt = 0;
          const lastEventId = window.sessionStorage.getItem(
            `shadowgrid-realtime-cursor:${profile.world_id}`,
          );
          socket?.send(
            JSON.stringify({
              access_token: token,
              world_id: profile.world_id,
              last_event_id: lastEventId,
              protocol_version: 1,
            }),
          );
        });
        socket.addEventListener("message", (event) => {
          let parsed: unknown;
          try {
            parsed = JSON.parse(String(event.data));
          } catch {
            socket?.close(4400, "Invalid realtime envelope");
            return;
          }
          if (!isRealtimeEnvelope(parsed)) {
            socket?.close(4400, "Unsupported realtime envelope");
            return;
          }
          const hint = parsed;
          if (
            hint.type === "connected" ||
            hint.type === "heartbeat" ||
            hint.type === "pong"
          )
            return;
          window.sessionStorage.setItem(
            `shadowgrid-realtime-cursor:${profile.world_id}`,
            hint.event_id,
          );
          const roots = invalidationRoots[hint.type];
          if (roots) {
            for (const root of roots) {
              void queryClient.invalidateQueries({ queryKey: [root] });
            }
          } else {
            void queryClient.invalidateQueries({
              predicate: (query) =>
                multiplayerKeys.has(String(query.queryKey[0])),
            });
          }
          void queryClient.invalidateQueries({
            queryKey: ["realtime-events"],
          });
        });
        socket.addEventListener("close", (event) => {
          if (!stopped) {
            if (event.code === 4409) {
              window.sessionStorage.removeItem(
                `shadowgrid-realtime-cursor:${profile.world_id}`,
              );
            }
            const delay = Math.min(30_000, 1_000 * 2 ** reconnectAttempt);
            reconnectAttempt += 1;
            reconnectTimer = window.setTimeout(() => void connect(), delay);
          }
        });
      } catch {
        if (!stopped) {
          const delay = Math.min(30_000, 1_000 * 2 ** reconnectAttempt);
          reconnectAttempt += 1;
          reconnectTimer = window.setTimeout(() => void connect(), delay);
        }
      }
    };

    void connect();
    return () => {
      stopped = true;
      if (reconnectTimer) window.clearTimeout(reconnectTimer);
      socket?.close();
      if (worldId)
        window.sessionStorage.removeItem(
          `shadowgrid-realtime-active:${worldId}`,
        );
    };
  }, [queryClient, token]);
}
