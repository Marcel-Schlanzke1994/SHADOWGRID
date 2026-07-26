import http from "k6/http";
import { check, sleep } from "k6";

const apiUrl = __ENV.API_URL || "http://localhost:8000/api/v1";
const token = __ENV.ACCESS_TOKEN || "";

export const options = {
  scenarios: {
    pvp_target_readers: {
      executor: "constant-vus",
      exec: "pvpTargets",
      vus: 25,
      duration: "30s",
    },
    territory_observers: {
      executor: "constant-vus",
      exec: "territories",
      vus: 25,
      duration: "30s",
    },
    war_room_observers: {
      executor: "constant-vus",
      exec: "wars",
      vus: 25,
      duration: "30s",
    },
    communication_observers: {
      executor: "constant-vus",
      exec: "channels",
      vus: 25,
      duration: "30s",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<750"],
  },
};

function authorizedGet(path) {
  if (!token) return http.get(`${apiUrl}/health`);
  return http.get(`${apiUrl}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

function observe(path) {
  const response = authorizedGet(path);
  check(response, { "authoritative read succeeds": (value) => value.status === 200 });
  sleep(0.25);
}

export function pvpTargets() {
  observe("/pvp/targets");
}

export function territories() {
  observe("/territories");
}

export function wars() {
  observe("/cartel-wars");
}

export function channels() {
  observe("/chat/channels");
}

export default function () {
  observe("/health");
}
