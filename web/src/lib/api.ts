import axios from "axios";
export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "/api",
  withCredentials: true,
});
let csrf: string | undefined;
api.interceptors.request.use(async (config) => {
  if (
    !["get", "head", "options"].includes(config.method || "get") &&
    !config.url?.match(/^\/auth\/(login|register|guest)$/)
  ) {
    if (!csrf) {
      try {
        csrf = (await api.get("/auth/csrf")).data.csrf_token;
      } catch {
        /* server supplies actionable auth error */
      }
    }
    if (csrf) config.headers.set("X-CSRF-Token", csrf);
  }
  return config;
});
export function setCsrf(value?: string) {
  csrf = value;
}
export const get = <T>(url: string) => api.get<T>(url).then((r) => r.data);
export function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    return typeof detail === "string"
      ? detail
      : error.response
        ? "Check the form and try again."
        : "Cannot reach the campus server. Check the connection and try again.";
  }
  return error instanceof Error
    ? error.message
    : "Something went wrong. Please try again.";
}
export interface Person {
  id?: number;
  full_name?: string;
  name?: string;
  sdu_id?: string;
  role: "guest" | "student" | "teacher" | "admin";
}
export interface Place {
  id: number;
  name: string;
  category: string;
  block: string;
  floor: string;
  x: number;
  y: number;
  opening_hours: string;
  contact: string;
  accessible: boolean;
  aliases: string;
  step_free_access?: string;
}
export interface MapPlace extends Place {
  map_key: string;
  access: string;
  map_floor: number | null;
  floors: number[];
  has_position: boolean;
  geometry?: { x: number; y: number; width: number; height: number } | null;
  notes: string;
  position_status: string;
  accessibility_status: string;
}
export interface Connection {
  a: string;
  b: string;
  kind: string;
  label: string | null;
  from_floor: number;
  to_floor: number;
  step_free: boolean;
  closed: boolean;
}
export interface PathPart {
  a: string;
  b: string;
  kind: string;
  label: string;
  floor: number;
  to_floor: number;
  step_free?: boolean;
}
export interface PathState {
  a: string;
  b: string;
  state: "closed" | "not_step_free" | null;
  open_reports: number;
}
export interface CampusMap {
  routing: {
    attachments: Record<string, string>;
    nodes: Record<string, [number, number]>;
  };
  network?: Connection[];
  width: number;
  height: number;
  places: MapPlace[];
  labels: {
    text: string;
    x: number;
    y: number;
    color: string;
    size: number;
    align: string;
    bold: boolean;
  }[];
  mapped_floors: number[];
}
export interface PathResult {
  start_location_id?: number;
  destination_location_id?: number;
  status: string;
  message: string;
  steps: string[];
  start?: string;
  destination?: string;
  route_floors?: number[];
  avoid_stairs: boolean;
  warnings?: string[];
  connections?: PathPart[];
  transfers?: {
    kind: string;
    label: string;
    from_floor: number;
    to_floor: number;
  }[];
  segments: {
    from: number[];
    to: number[];
    floor: number;
    approximate_door: boolean;
  }[];
}
export interface News {
  id: number;
  title: string;
  body: string;
  published_at: string;
  location_id: number | null;
  starts_at: string | null;
  ends_at: string | null;
  state?: "scheduled" | "showing" | "expired";
}
const asUtc = (date: string) =>
  new Date(/Z$|[+-]\d\d:\d\d$/.test(date) ? date : date + "Z");
// Value for a datetime-local input showing Asia/Almaty (UTC+5) time.
export const almatyInputValue = (date: string | null) =>
  date
    ? new Date(asUtc(date).getTime() + 5 * 3600000).toISOString().slice(0, 16)
    : "";
export interface Lesson {
  id: number;
  course: string;
  room: string;
  location_id: number | null;
  starts_at: string;
  sample: boolean;
  kind: string;
}
export interface Report {
  id: number;
  author: string;
  kind: "location" | "path";
  location_id: number | null;
  location_name: string | null;
  connection_label: string | null;
  edge_a: string | null;
  edge_b: string | null;
  route: string | null;
  message: string;
  status: string;
  resolution_note: string;
  created_at: string;
  updated_at: string | null;
  reporter_unread: boolean;
  similar_open: number[];
  path_status: { id: number; state: string; reopens_at: string | null } | null;
}
export interface PathClosure {
  id: number;
  edge_a: string;
  edge_b: string;
  state: string;
  note: string;
  label: string;
  report_id: number | null;
  created_at: string;
  reopens_at: string | null;
}
export const STEP_FREE_STATES = ["Not verified", "Step-free", "Not step-free"];
export const reportStatusLabel = (status: string) =>
  (
    ({
      new: "Received",
      reviewing: "Under review",
      resolved: "Resolved",
      rejected: "Not changed",
      withdrawn: "Withdrawn",
    }) as Record<string, string>
  )[status] || status;
export interface Answer {
  conversation_id?: string;
  engine?: "openrouter" | "rules";
  model?: string;
  fallback_reason?: string;
  locations?: Place[];
  route?: PathResult;
  answer: string;
  location: Place | null;
  needs_clarification: boolean;
  choices: Place[];
  context_id?: string;
  action?: string;
}
export const localTime = (date: string) =>
  new Date(
    date.endsWith("Z") || /[+-]\d\d:\d\d$/.test(date) ? date : date + "Z",
  ).toLocaleString("en-GB", {
    timeZone: "Asia/Almaty",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
