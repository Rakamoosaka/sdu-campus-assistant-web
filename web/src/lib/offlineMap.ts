import { api, type CampusMap, type Place } from "./api";

const DATA_CACHE = "sdu-public-map-v1";
const DATA_KEY = "/__saved-campus-map";
let registration: Promise<ServiceWorkerRegistration> | undefined;

export interface SavedMap {
  savedAt: string;
  map: CampusMap;
  places: Place[];
}

export const offlineSupported =
  import.meta.env.PROD && "serviceWorker" in navigator && "caches" in window;

export function prepareOfflineShell() {
  if (!offlineSupported) return;
  registration ??= navigator.serviceWorker
    .register("/offline-worker.js")
    .catch((error: unknown) => {
      registration = undefined;
      throw error;
    });
  return registration;
}

export async function readSavedMap(): Promise<SavedMap | null> {
  if (!offlineSupported) return null;
  const response = await (await caches.open(DATA_CACHE)).match(DATA_KEY);
  return response ? response.json() : null;
}

function waitForOfflineShell(signal: AbortSignal) {
  return new Promise<ServiceWorkerRegistration>((resolve, reject) => {
    const stop = () => finish(() => reject(signal.reason));
    const timeout = setTimeout(
      () =>
        finish(() =>
          reject(
            new Error("The offline map couldn’t finish preparing. Try again."),
          ),
        ),
      15000,
    );
    function finish(callback: () => void) {
      clearTimeout(timeout);
      signal.removeEventListener("abort", stop);
      callback();
    }
    signal.addEventListener("abort", stop, { once: true });
    if (signal.aborted) stop();
    void navigator.serviceWorker.ready.then((worker) =>
      finish(() => resolve(worker)),
    );
  });
}

export async function downloadMap(signal: AbortSignal): Promise<SavedMap> {
  const worker = await prepareOfflineShell();
  if (!worker) throw new Error("Offline maps are unavailable in this browser.");

  const [places, map, ready] = await Promise.all([
    api.get<Place[]>("/locations", { signal, timeout: 15000 }),
    api.get<CampusMap>("/campus-map", { signal, timeout: 15000 }),
    waitForOfflineShell(signal),
  ]);
  signal.throwIfAborted();
  // Registration readiness also confirms that the shell and both SVGs cached successfully.
  if (
    !ready.active ||
    !Array.isArray(places.data) ||
    !Array.isArray(map.data?.places)
  ) {
    throw new Error("The campus map could not be downloaded.");
  }
  const saved = {
    savedAt: new Date().toISOString(),
    places: places.data,
    map: map.data,
  };
  const cache = await caches.open(DATA_CACHE);
  signal.throwIfAborted();
  // A single cache entry replaces the previous complete snapshot.
  await cache.put(DATA_KEY, Response.json(saved));
  return saved;
}

export async function removeSavedMap() {
  await caches.delete(DATA_CACHE);
}

const normalize = (value: string) =>
  value.toLowerCase().replace(/[^a-z0-9]/g, "");
const aliases: Record<string, string> = {
  "Medical Point": "doctor,clinic,first aid,sick,medical",
  Library: "books,reading,study",
  "Print & Stationery": "printing,printer,photocopy,copy",
  Canteen: "cafeteria,food",
};

function oneEditAway(a: string, b: string): boolean {
  if (Math.abs(a.length - b.length) > 1) return false;
  if (a.length > b.length) return oneEditAway(b, a);
  const index = [...a].findIndex((letter, i) => letter !== b[i]);
  if (index === -1) return true;
  if (a.length < b.length) return a.slice(index) === b.slice(index + 1);
  return (
    a.slice(index + 1) === b.slice(index + 1) ||
    (a[index] === b[index + 1] &&
      a[index + 1] === b[index] &&
      a.slice(index + 2) === b.slice(index + 2))
  );
}

export function searchSavedMap(places: Place[], query: string): Place[] {
  const needle = normalize(query);
  if (!needle) return [];
  return places
    .map((place) => {
      const name = normalize(place.name);
      const terms = [
        place.name,
        place.category,
        place.block,
        ...place.aliases.split(",").filter((alias) => !alias.startsWith("[")),
        ...(aliases[place.name] || "").split(","),
      ].map(normalize);
      const score =
        name === needle
          ? 4
          : terms.includes(needle)
            ? 3
            : terms.some((term) => term.includes(needle))
              ? 2
              : needle.length >= 4 &&
                  terms.some((term) => oneEditAway(needle, term))
                ? 1
                : 0;
      return { place, score };
    })
    .filter(({ score }) => score > 0)
    .sort(
      (a, b) => b.score - a.score || a.place.name.localeCompare(b.place.name),
    )
    .slice(0, 30)
    .map(({ place }) => place);
}
