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
}
export interface MapPlace extends Place {
  map_key: string;
  map_floor: number | null;
  floors: number[];
  has_position: boolean;
  geometry?: { x: number; y: number; width: number; height: number } | null;
  notes: string;
  position_status: string;
  accessibility_status: string;
}
export interface CampusMap {
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
}
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
  location_id: number | null;
  message: string;
  status: string;
}
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
