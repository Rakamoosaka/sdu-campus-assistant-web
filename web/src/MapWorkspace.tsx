import { Link, useLocation, useNavigate } from "react-router-dom";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  TransformWrapper,
  TransformComponent,
  type ReactZoomPanPinchRef,
} from "react-zoom-pan-pinch";
import {
  Search,
  ArrowUpRight,
  MapPin,
  Navigation,
  X,
  Plus,
  Minus,
  Maximize,
  Bookmark,
  ChevronRight,
  Route,
  Layers,
  Info,
  Flag,
  ArrowLeft,
  SlidersHorizontal,
  Accessibility,
  Check,
} from "lucide-react";
import { Button } from "./components/ui/button";
import { Dialog } from "./components/ui/dialog";
import { ShareDestination } from "./components/MapActions";
import { PathPicker } from "./components/PathPicker";
import { features } from "./features";
import { searchSavedMap } from "./lib/offlineMap";
import {
  get,
  api,
  errorMessage,
  type Person,
  type Place,
  type CampusMap,
  type MapPlace,
  type PathResult,
  type Report,
  type News,
  type PathPart,
  type PathState,
  reportStatusLabel,
  localTime,
} from "./lib/api";
import floor1 from "../../assets/maps/floor-1-background.svg?url";
import floor2 from "../../assets/maps/floor-2-background.svg?url";
export function StateBox({
  error,
  empty,
  retry,
}: {
  error?: unknown;
  empty?: string;
  retry?: () => void;
}) {
  return (
    <div
      className={error ? "state-box error-box" : "state-box"}
      role={error ? "alert" : "status"}
    >
      {error ? errorMessage(error) : empty || "Loading campus…"}
      {retry && (
        <Button size="sm" variant="outline" onClick={retry}>
          Try again
        </Button>
      )}
    </div>
  );
}
export interface MapProps {
  person: Person;
  selected: number | null;
  onSelect: (id: number | null) => void;
  all: Place[];
  map: CampusMap;
  favorites: Place[];
  onSave: (place: Place) => void;
  onLogin: () => void;
  savePending: boolean;
  sharedDestination: boolean;
  offlineDate?: string;
  onRetryConnection?: () => void;
  offlineControl: ReactNode;
}
export function MapWorkspace({
  person,
  selected,
  onSelect,
  all,
  map,
  favorites,
  onSave,
  onLogin,
  savePending,
  sharedDestination,
  offlineDate,
  onRetryConnection,
  offlineControl,
}: MapProps) {
  const location = useLocation(),
    navigate = useNavigate(),
    qc = useQueryClient();
  const incomingRoute = location.state?.assistantRoute as
    PathResult | undefined;
  const [floor, setFloor] = useState(incomingRoute?.route_floors?.[0] || 1),
    [query, setQuery] = useState(""),
    [debounced, setDebounced] = useState(""),
    [category, setCategory] = useState("All"),
    [start, setStart] = useState(incomingRoute?.start_location_id || 1),
    [route, setRoute] = useState<PathResult | null>(incomingRoute || null),
    [routeError, setRouteError] = useState(""),
    [panelOpen, setPanelOpen] = useState(false),
    [reportOpen, setReportOpen] = useState(false),
    [report, setReport] = useState(""),
    [reportKind, setReportKind] = useState<"location" | "path">("location"),
    [reportEdge, setReportEdge] = useState(""),
    [reportDone, setReportDone] = useState<Report | null>(null),
    [showAccess, setShowAccess] = useState(false),
    [draftAvoid, setDraftAvoid] = useState<boolean | null>(null);
  const zoom = useRef<ReactZoomPanPinchRef>(null),
    viewport = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(0.5);
  useEffect(() => {
    if (incomingRoute)
      navigate(location.pathname, { replace: true, state: null });
  }, []);
  const selectedPlace = all.find((p) => p.id === selected),
    mapPlace = map.places.find((p) => p.id === selected);
  const offline = !!offlineDate;
  const searchInput = useRef<HTMLInputElement>(null);
  const search = useQuery({
    queryKey: ["search", debounced],
    queryFn: () => get<Place[]>("/search?q=" + encodeURIComponent(debounced)),
    enabled: !offline && debounced.length > 0,
  });
  const results = debounced
    ? offline
      ? searchSavedMap(all, debounced)
      : search.data || []
    : all.filter((p) => category === "All" || p.category === category);
  const saved = favorites.some((p) => p.id === selected);
  const routePlaces = all.filter((p) =>
    map.places.some(
      (m) =>
        m.id === p.id &&
        m.access === "public" &&
        m.map_key in map.routing.attachments,
    ),
  );
  const canRoute = routePlaces.some((p) => p.id === selected);
  const previousSelected = useRef(selected);
  const routeEndpoints = useRef({ start, selected });
  routeEndpoints.current = { start, selected };
  const planning = useMutation({
    mutationFn: (endpoints: { start: number; destination: number }) =>
      get<PathResult>(
        `/routes?start=${endpoints.start}&destination=${endpoints.destination}`,
      ),
    onSuccess: (data, endpoints) => {
      if (
        routeEndpoints.current.start !== endpoints.start ||
        routeEndpoints.current.selected !== endpoints.destination
      )
        return;
      setRoute(data);
      setRouteError("");
      if (data.route_floors?.length) setFloor(data.route_floors[0]);
    },
    onError: (e, endpoints) => {
      if (
        routeEndpoints.current.start === endpoints.start &&
        routeEndpoints.current.selected === endpoints.destination
      )
        setRouteError(errorMessage(e));
    },
  });
  const placeNews = useQuery({
    queryKey: ["news", "place", selected],
    queryFn: () => get<News[]>(`/announcements?location_id=${selected}`),
    enabled: features.announcements && !offline && selected !== null,
  });
  const nearbyPaths = useQuery({
    queryKey: ["nearby-paths", selected],
    queryFn: () => get<PathPart[]>(`/locations/${selected}/nearby-paths`),
    enabled: reportOpen && selected !== null,
  });
  const pathStates = useQuery({
    queryKey: ["path-states"],
    queryFn: () => get<PathState[]>("/paths/status"),
    enabled: reportOpen,
  });
  const routeParts =
    route?.destination_location_id === selected ? route?.connections || [] : [];
  const nearbyParts = (nearbyPaths.data || []).filter(
    (n) =>
      !routeParts.some(
        (r) => (r.a === n.a && r.b === n.b) || (r.a === n.b && r.b === n.a),
      ),
  );
  const pref = useQuery({
    queryKey: ["preferences"],
    queryFn: () => get<{ accessible_routes: boolean }>("/users/me/preferences"),
    enabled: !offline,
  });
  const savePref = useMutation({
    mutationFn: (value: boolean) =>
      api.put("/users/me/preferences", { accessible_routes: value }),
    onSettled: async () => {
      await qc.invalidateQueries({ queryKey: ["preferences"] });
      setDraftAvoid(null);
    },
    onSuccess: () => {
      if (route && selected !== null)
        planning.mutate({ start, destination: selected });
    },
  });
  const reporting = useMutation({
    mutationFn: () => {
      const [edge_a, edge_b] = reportEdge.split("|");
      return api.post<Report>(
        "/reports",
        reportKind === "path"
          ? {
              kind: "path",
              message: report,
              location_id: selected,
              edge_a,
              edge_b,
              route_start_id: route?.start_location_id,
              route_destination_id: route?.destination_location_id,
            }
          : { kind: "location", message: report, location_id: selected },
      );
    },
    onSuccess: (result) => {
      setReportDone(result.data);
      setReport("");
      qc.invalidateQueries({ queryKey: ["my-reports"] });
      qc.invalidateQueries({ queryKey: ["path-states"] });
    },
  });
  function openReport(kind: "location" | "path") {
    setReportKind(kind);
    setReportEdge("");
    setReportDone(null);
    reporting.reset();
    setReportOpen(true);
  }
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(query.trim()), 300);
    return () => clearTimeout(timer);
  }, [query]);
  useEffect(() => {
    const el = viewport.current;
    if (!el) return;
    const observer = new ResizeObserver(([entry]) => {
      const next = Math.min(
        (entry.contentRect.width - 56) / map.width,
        (entry.contentRect.height - 70) / map.height,
      );
      setScale(Math.max(0.2, next));
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [map]);
  const fit = () =>
    zoom.current?.setTransform(
      Math.max(
        0,
        ((viewport.current?.clientWidth || 0) - map.width * scale) / 2,
      ),
      Math.max(
        0,
        ((viewport.current?.clientHeight || 0) - map.height * scale) / 2,
      ),
      scale,
      250,
    );
  useEffect(() => {
    fit();
  }, [scale]);
  useEffect(() => {
    if (selected !== previousSelected.current) {
      setRoute(null);
      setRouteError("");
      previousSelected.current = selected;
    }
    if (selected === null) return;
    if (mapPlace?.map_floor && route?.destination_location_id !== selected)
      setFloor(mapPlace.map_floor);
    setPanelOpen(!sharedDestination);
  }, [selected, sharedDestination, mapPlace?.map_floor]);
  const floorSegments = useMemo(
    () => (!offline && route?.segments.filter((s) => s.floor === floor)) || [],
    [route, floor, offline],
  );
  useEffect(() => {
    if ((!route || offline) && mapPlace?.has_position) {
      const timer = setTimeout(
        () =>
          zoom.current?.zoomToElement(
            "place-" + selected,
            Math.max(scale * 1.6, 0.8),
            350,
          ),
        100,
      );
      return () => clearTimeout(timer);
    }
  }, [selected, floor, scale, offline, mapPlace?.has_position]);
  useEffect(() => {
    if (floorSegments.length) {
      const timer = setTimeout(
        () => zoom.current?.zoomToElement("route-bounds", undefined, 350),
        150,
      );
      return () => clearTimeout(timer);
    } else if (route && !offline) {
      fit();
    }
  }, [route, floor, scale, offline]);
  const routeBounds = useMemo(() => {
    const points = floorSegments.flatMap((s) => [s.from, s.to]);
    if (!points.length) return null;
    const xs = points.map((p) => p[0]),
      ys = points.map((p) => p[1]);
    return {
      x: Math.min(...xs) - 60,
      y: Math.min(...ys) - 60,
      width: Math.max(...xs) - Math.min(...xs) + 120,
      height: Math.max(...ys) - Math.min(...ys) + 120,
    };
  }, [floorSegments]);
  function choose(id: number) {
    setRoute(null);
    setRouteError("");
    onSelect(id);
  }
  function renderPlace(p: MapPlace) {
    const live = all.find((item) => item.id === p.id);
    if (!live) return null;
    const active = selected === p.id;
    const isSaved = favorites.some((item) => item.id === p.id);
    const isStair = p.category === "Stairs";
    const geometry = p.geometry;
    const x = live.x * map.width,
      y = live.y * map.height;
    const handlers = {
      onClick: () => choose(p.id),
      onKeyDown: (e: React.KeyboardEvent) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          choose(p.id);
        }
      },
    };
    const label = live.name;
    return (
      <g
        key={p.id}
        id={"place-" + p.id}
        className={"map-place " + (active ? "active" : "")}
        role="button"
        tabIndex={0}
        aria-label={`${label}, ${live.floor}`}
        {...handlers}
      >
        <title>
          {label} · {p.position_status}
        </title>
        {geometry ? (
          <>
            <rect
              {...geometry}
              rx={3}
              fill={active ? "#2662df" : isSaved ? "#fff4d6" : "#f6f8fd"}
              stroke={active ? "#123276" : isSaved ? "#b69247" : "#899cbb"}
              strokeWidth={active ? 3 : 1}
            />
            <text
              x={geometry.x + geometry.width / 2}
              y={geometry.y + geometry.height / 2 + 3}
              textAnchor="middle"
              fontSize={9}
              fontWeight={600}
              fill={active ? "white" : "#273f69"}
            >
              {label}
            </text>
          </>
        ) : (
          <>
            <circle
              cx={x}
              cy={y}
              r={active ? 14 : isStair ? 13 : 11}
              fill={active ? "#2662df" : "#fff"}
              stroke={isSaved ? "#b69247" : "#364e75"}
              strokeWidth={active ? 3 : 1.7}
            />
            {isStair ? (
              <path
                className="stair-icon"
                d="M-8 5h5V0h5v-5h6"
                transform={`translate(${x} ${y})`}
                fill="none"
                stroke={active ? "#fff" : "#30476c"}
                strokeWidth={2.6}
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              />
            ) : (
              <text
                x={x}
                y={y + 3}
                textAnchor="middle"
                fill={active ? "#fff" : "#30476c"}
                fontSize={8}
                fontWeight={700}
              >
                {p.category === "Lift"
                  ? "L"
                  : p.category === "Entrance"
                    ? "↗"
                    : p.category === "Study"
                      ? "B"
                      : p.category === "Health"
                        ? "+"
                        : p.category === "Food"
                          ? "F"
                          : p.category === "Printer"
                            ? "P"
                            : "•"}
              </text>
            )}
            {(active ||
              ["Entrance", "Study", "Health", "Printer", "Food"].includes(
                p.category,
              )) && (
              <text
                x={x + 16}
                y={y + 3}
                fontSize={10}
                fill="#1a3158"
                fontWeight={600}
                paintOrder="stroke"
                stroke="#f0f4f8"
                strokeWidth={3}
              >
                {label}
              </text>
            )}
          </>
        )}
      </g>
    );
  }
  return (
    <div className="map-workspace">
      <aside className={"explore-panel " + (panelOpen ? "mobile-open" : "")}>
        <div className="panel-heading">
          <div>
            <span className="eyebrow">YOUR CAMPUS, CONNECTED</span>
            <h2>Where to?</h2>
          </div>
          <button
            className="mobile-panel-close icon-button"
            aria-label="Close explore panel"
            onClick={() => setPanelOpen(false)}
          >
            <X size={20} />
          </button>
        </div>
        <div className="search-field">
          <Search size={19} />
          <input
            ref={searchInput}
            aria-label="Search campus"
            placeholder="Room, place or service…"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              onSelect(null);
              setRoute(null);
            }}
          />
          {query && (
            <button aria-label="Clear search" onClick={() => setQuery("")}>
              <X size={15} />
            </button>
          )}
        </div>
        {!selectedPlace && (
          <>
            <div className="category-list">
              {[
                "All",
                "Classroom",
                "Study",
                "Food",
                "Health",
                "Printer",
                "Lift",
              ].map((c) => (
                <button
                  key={c}
                  onClick={() => {
                    setCategory(c);
                    setQuery("");
                  }}
                  className={category === c ? "selected" : ""}
                >
                  {c === "All" ? "Explore all" : c}
                </button>
              ))}
            </div>
            <div className="results-heading">
              <span>{debounced ? "SEARCH RESULTS" : "CAMPUS DIRECTORY"}</span>
              <span>{results.length} places</span>
            </div>
            <div className="location-list">
              {!offline && search.isFetching && debounced ? (
                <StateBox />
              ) : !offline && search.isError && debounced ? (
                <StateBox error={search.error} retry={() => search.refetch()} />
              ) : results.length === 0 ? (
                <StateBox empty="No places found. Try a room code like D201 or a service name." />
              ) : (
                results.map((place) => (
                  <button
                    key={place.id}
                    className="location-row"
                    onClick={() => choose(place.id)}
                  >
                    <span
                      className={
                        "location-icon category-" + place.category.toLowerCase()
                      }
                    >
                      <MapPin size={18} />
                    </span>
                    <span>
                      <strong>{place.name}</strong>
                      <small>
                        {place.block} · {place.floor}
                      </small>
                    </span>
                    <ChevronRight size={16} />
                  </button>
                ))
              )}
            </div>
            <div className="panel-help">
              <span className="help-symbol">✧</span>
              <div>
                <strong>A question about campus?</strong>
                <p>Ask the assistant to point you in the right direction.</p>
                {offline ? (
                  <p>The assistant needs a connection.</p>
                ) : (
                  <Link to="/assistant">
                    Meet your assistant <ArrowUpRight size={14} />
                  </Link>
                )}
              </div>
            </div>
          </>
        )}
        {selectedPlace && (
          <div className="location-details">
            <button
              className="back-link"
              onClick={() => {
                onSelect(null);
                setRoute(null);
              }}
            >
              <ArrowLeft size={15} /> Back to places
            </button>
            <span className="category-tag">{selectedPlace.category}</span>
            <h3>{selectedPlace.name}</h3>
            <p className="muted">
              {selectedPlace.block} · {selectedPlace.floor}
            </p>
            <div className="detail-facts">
              <div>
                <span>Opening hours</span>
                <strong>{selectedPlace.opening_hours}</strong>
              </div>
              <div>
                <span>Contact</span>
                <strong>{selectedPlace.contact}</strong>
              </div>
              <div>
                <span>Step-free access</span>
                <strong>{selectedPlace.step_free_access || "Not verified"}</strong>
              </div>
              <div>
                <span>Map position</span>
                <strong>
                  {mapPlace?.has_position
                    ? "Schematic"
                    : "Map position unavailable"}
                </strong>
              </div>
            </div>
            {features.announcements && !offline && !!placeNews.data?.length && (
              <section
                className="place-announcements"
                aria-label="Announcements for this place"
              >
                {placeNews.data.map((n) => (
                  <article key={n.id}>
                    <strong>{n.title}</strong>
                    {n.body}
                    {n.ends_at && (
                      <small className="muted"> · Until {localTime(n.ends_at)}</small>
                    )}
                  </article>
                ))}
              </section>
            )}
            <div className="detail-actions">
              <ShareDestination key={selectedPlace.id} place={selectedPlace} />
              {!offline && (
                <Button variant="outline" onClick={() => openReport("location")}>
                  <Flag size={16} /> Report a problem
                </Button>
              )}
              {!offline &&
                (person.role === "guest" ? (
                  <Button variant="outline" onClick={onLogin}>
                    <Bookmark size={16} /> Log in to save
                  </Button>
                ) : (
                  <Button
                    variant={saved ? "secondary" : "outline"}
                    disabled={savePending || (!saved && favorites.length >= 5)}
                    onClick={() => onSave(selectedPlace)}
                  >
                    <Bookmark
                      size={16}
                      fill={saved ? "currentColor" : "none"}
                    />
                    {saved ? "Remove saved" : "Save place"}{" "}
                    <span className="count">{favorites.length}/5</span>
                  </Button>
                ))}
              {!saved && favorites.length >= 5 && (
                <p className="muted text-xs">
                  All five slots are filled. Remove a place in Saved to make
                  room.
                </p>
              )}
            </div>
            <div className="route-form">
              <div className="section-label">
                <Route size={17} /> Plan your route
              </div>
              <label>
                Start from
                <select
                  disabled={offline}
                  value={start}
                  onChange={(e) => {
                    setStart(Number(e.target.value));
                    setRoute(null);
                    setRouteError("");
                  }}
                  aria-label="Route start"
                >
                  {routePlaces.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} · {p.floor}
                    </option>
                  ))}
                </select>
              </label>
              <div className="route-destination">
                <MapPin size={16} /> {selectedPlace.name}
              </div>
              {!offline && (
                <label className="route-toggle">
                  <Accessibility size={18} />
                  <span>
                    <strong>Avoid stairs</strong>
                    <small>
                      Saved to your{" "}
                      {person.role === "guest" ? "guest session" : "account"}
                    </small>
                  </span>
                  <input
                    type="checkbox"
                    role="switch"
                    checked={draftAvoid ?? pref.data?.accessible_routes ?? false}
                    disabled={
                      pref.isPending || pref.isError || savePref.isPending
                    }
                    onChange={(e) => {
                      setDraftAvoid(e.target.checked);
                      savePref.mutate(e.target.checked);
                    }}
                  />
                </label>
              )}
              {savePref.isError && <StateBox error={savePref.error} />}
              <Button
                className="w-full"
                disabled={offline || planning.isPending || !canRoute || selected === null}
                onClick={() =>
                  selected !== null &&
                  planning.mutate({ start, destination: selected })
                }
              >
                <Navigation size={16} />
                {planning.isPending ? "Finding a route…" : "Find route"}
              </Button>
              <p className="route-hint">
                {offline ? "Reconnect to find a route." : canRoute
                  ? "Choose your start manually. No live indoor positioning."
                  : "This place has no public mapped approach yet. Choose another destination."}
              </p>
              {!offline && routeError && (
                <div role="alert" className="error-box">
                  {routeError}
                </div>
              )}
            </div>
            {!offline && route && (
              <section className="route-result" aria-label="Route directions">
                <div className="flex justify-between items-center">
                  <strong>
                    {route.status === "schematic_draft"
                      ? "Your route"
                      : "Route information"}
                  </strong>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => setRoute(null)}
                  >
                    Clear route
                  </Button>
                </div>
                {route.avoid_stairs && (
                  <span className="category-tag">
                    Step-free preference · stairs excluded
                  </span>
                )}
                <p>{route.message}</p>
                {!!route.warnings?.length && (
                  <ul className="route-warnings">
                    {route.warnings.map((w) => (
                      <li key={w}>{w}</li>
                    ))}
                  </ul>
                )}
                {route.route_floors && (
                  <div className="route-floor-tabs">
                    {route.route_floors.map((f) => (
                      <Button
                        size="sm"
                        variant={floor === f ? "default" : "outline"}
                        key={f}
                        onClick={() => setFloor(f)}
                      >
                        Floor {f}
                      </Button>
                    ))}
                  </div>
                )}
                <ol>
                  {route.steps.map((step, i) => (
                    <li key={i}>{step}</li>
                  ))}
                </ol>
                {route.status === "schematic_draft" && (
                  <>
                    <p className="muted text-xs">
                      Distance & walking time unavailable: the schematic has
                      no measured scale.
                    </p>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => openReport("path")}
                    >
                      <Flag size={14} /> Report a blocked path
                    </Button>
                  </>
                )}
              </section>
            )}
          </div>
        )}
        <div className="panel-foot">
          <span className="status-dot" /> Campus catalogue · Schematic map
        </div>
      </aside>
      <section className="map-canvas" aria-label="Interactive campus map">
        <div className="map-topbar">
          <div>
            <span className="eyebrow">SDU UNIVERSITY</span>
            <h2>
              Campus map <span className="map-status">SCHEMATIC</span>
            </h2>
          </div>
          <Button
            variant="outline"
            className="mobile-explore"
            onClick={() => setPanelOpen(true)}
          >
            <Search size={16} /> {selectedPlace ? "Place details" : "Explore"}
          </Button>
          <div className="floor-switch" aria-label="Select map floor">
            <Layers size={17} />
            {[1, 2, 3].map((f) => (
              <button
                key={f}
                aria-pressed={floor === f}
                onClick={() => setFloor(f)}
              >
                {f === 3 ? "3 · terminal" : `Floor ${f}`}
              </button>
            ))}
          </div>
          <div className="offline-map-control">{offlineControl}</div>
          {(offline || (sharedDestination && !selectedPlace)) && (
            <div className="map-notices">
              {offline && (
                <p role="status">
                  Offline · Using map saved on{" "}
                  {new Date(offlineDate!).toLocaleDateString()}
                  {onRetryConnection && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={onRetryConnection}
                    >
                      Retry connection
                    </Button>
                  )}
                </p>
              )}
              {sharedDestination && !selectedPlace && (
                <div role="alert">
                  {offline
                    ? "This destination isn’t in your saved map."
                    : "This destination is unavailable."}
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      setPanelOpen(true);
                      requestAnimationFrame(() => searchInput.current?.focus());
                    }}
                  >
                    {offline ? "Browse saved map" : "Search campus"}
                  </Button>
                </div>
              )}
            </div>
          )}
        </div>
        {sharedDestination && selectedPlace && !panelOpen && (
          <button
            className="shared-place-card"
            onClick={() => setPanelOpen(true)}
          >
            <MapPin size={17} />
            <span>
              <strong>{selectedPlace.name}</strong>
              <small>
                {selectedPlace.floor} ·{" "}
                {mapPlace?.has_position
                  ? "View details"
                  : "Map position unavailable"}
              </small>
            </span>
            <ChevronRight size={17} />
          </button>
        )}
        <div ref={viewport} className="map-viewport">
          <TransformWrapper
            ref={zoom}
            initialScale={0.5}
            minScale={0.15}
            maxScale={5}
            limitToBounds={false}
            centerOnInit
            panning={{ excluded: ["map-place"] }}
            doubleClick={{ disabled: true }}
          >
            <TransformComponent
              wrapperStyle={{ width: "100%", height: "100%" }}
              contentStyle={{ width: map.width, height: map.height }}
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width={map.width}
                height={map.height}
                viewBox={`0 0 ${map.width} ${map.height}`}
                className="campus-svg"
                aria-label={`Schematic floor ${floor}`}
              >
                {floor !== 3 && (
                  <image
                    href={floor === 1 ? floor1 : floor2}
                    width={map.width}
                    height={map.height}
                  />
                )}
                {floor === 1 &&
                  map.labels?.map((label, i) => (
                    <text
                      key={i}
                      x={label.x}
                      y={label.y}
                      fill={label.color || "#3b506e"}
                      fontSize={label.size}
                      textAnchor={label.align === "middle" ? "middle" : "start"}
                      fontWeight={label.bold ? 700 : 400}
                    >
                      {label.text}
                    </text>
                  ))}
                {floor === 2 &&
                  ["D", "E", "F", "G", "H"].map((b, i) => (
                    <text
                      key={b}
                      x={200}
                      y={[868, 685, 501, 318, 139][i]}
                      fontSize={17}
                      fontWeight={700}
                      fill="#60728e"
                    >
                      {b}
                    </text>
                  ))}
                {showAccess &&
                  map.network
                    ?.filter((c) => c.from_floor === floor && c.to_floor === floor)
                    .map((c) => {
                      const a = map.routing.nodes[c.a],
                        b = map.routing.nodes[c.b];
                      return (
                        <line
                          key={c.a + c.b}
                          x1={a[0]}
                          y1={a[1]}
                          x2={b[0]}
                          y2={b[1]}
                          stroke={
                            c.closed
                              ? "#dc2626"
                              : c.step_free
                                ? "#15803d"
                                : "#b45309"
                          }
                          strokeWidth={c.closed ? 5 : 3.5}
                          strokeDasharray={
                            c.closed || !c.step_free ? "5 5" : undefined
                          }
                          strokeLinecap="round"
                          opacity={0.85}
                          pointerEvents="none"
                        />
                      );
                    })}
                {routeBounds && (
                  <rect
                    id="route-bounds"
                    {...routeBounds}
                    fill="transparent"
                    pointerEvents="none"
                  />
                )}
                {floorSegments.map((segment, i) => (
                  <g key={i} pointerEvents="none">
                    <line
                      className="route-line"
                      x1={segment.from[0]}
                      y1={segment.from[1]}
                      x2={segment.to[0]}
                      y2={segment.to[1]}
                      stroke="white"
                      strokeWidth={9}
                      strokeLinecap="round"
                    />
                    <line
                      x1={segment.from[0]}
                      y1={segment.from[1]}
                      x2={segment.to[0]}
                      y2={segment.to[1]}
                      stroke={segment.approximate_door ? "#af8330" : "#2563eb"}
                      strokeWidth={5}
                      strokeLinecap="round"
                      strokeDasharray={
                        segment.approximate_door ? "6 6" : undefined
                      }
                    />
                  </g>
                ))}
                {map.places
                  .filter(
                    (p) =>
                      p.has_position &&
                      p.map_floor === floor &&
                      (category === "All" ||
                        p.category === category ||
                        p.id === selected ||
                        route),
                  )
                  .map(renderPlace)}
                {floor === 3 && (
                  <text
                    x={map.width / 2}
                    y={map.height / 2 + 95}
                    textAnchor="middle"
                    fontSize={18}
                    fill="#61728e"
                  >
                    Canteen terminal only · no full floor plan
                  </text>
                )}
              </svg>
            </TransformComponent>
          </TransformWrapper>
        </div>
        <div className="map-caption">
          <Info size={16} />
          <span>
            {floor === 2
              ? "Floor 2 follows the supplied annotated sketch. Pale areas give building context."
              : floor === 3
                ? "Only the canteen connection is mapped on floor 3."
                : "A campus schematic, with approximate room and doorway positions."}
          </span>
        </div>
        <div className="map-controls">
          <Button
            variant="outline"
            size="icon"
            aria-label="Zoom in"
            onClick={() => zoom.current?.zoomIn()}
          >
            <Plus size={20} />
          </Button>
          <Button
            variant="outline"
            size="icon"
            aria-label="Zoom out"
            onClick={() => zoom.current?.zoomOut()}
          >
            <Minus size={20} />
          </Button>
          <span />
          <Button
            variant="outline"
            size="icon"
            aria-label="Fit map"
            onClick={fit}
          >
            <Maximize size={18} />
          </Button>
          {!!map.network && (
            <Button
              variant={showAccess ? "default" : "outline"}
              size="icon"
              aria-label="Show step-free connections"
              aria-pressed={showAccess}
              title="Show step-free connections"
              onClick={() => setShowAccess(!showAccess)}
            >
              <Accessibility size={18} />
            </Button>
          )}
        </div>
        <div className="map-legend">
          <span>
            <i className="legend-room" />
            Classroom
          </span>
          <span>
            <i className="legend-service" />
            Campus service
          </span>
          {showAccess && (
            <>
              <span>
                <i className="legend-stepfree" />
                Step-free
              </span>
              <span>
                <i className="legend-steps" />
                Stairs / not step-free
              </span>
              <span>
                <i className="legend-closed" />
                Closed
              </span>
            </>
          )}
          {!offline && route && (
            <>
              <span>
                <i className="legend-route" />
                Route
              </span>
              <span>
                <i className="legend-approx" />
                Approximate connection
              </span>
            </>
          )}
        </div>
      </section>
      <Dialog
        open={reportOpen}
        onOpenChange={setReportOpen}
        title="Report a problem"
        description={`About ${selectedPlace?.name}. The campus team reviews every report.`}
      >
        {reportDone ? (
          <div className="report-done" role="status">
            <p className="success-text">
              <Check size={16} /> Report #{reportDone.id} received ·{" "}
              {reportStatusLabel(reportDone.status)}
            </p>
            <p>
              Follow its progress in <Link to="/reports">My reports</Link>.
              {person.role === "guest" &&
                " If you sign in on this device later, it moves to your account."}
            </p>
            <Button onClick={() => setReportOpen(false)}>Done</Button>
          </div>
        ) : (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              reporting.mutate();
            }}
          >
            <fieldset className="report-kind">
              <legend>What's the problem?</legend>
              <label>
                <input
                  type="radio"
                  name="report-kind"
                  checked={reportKind === "location"}
                  onChange={() => setReportKind("location")}
                />
                <span>
                  Wrong information about {selectedPlace?.name}
                  <small>Name, opening hours, contact, step-free access…</small>
                </span>
              </label>
              <label>
                <input
                  type="radio"
                  name="report-kind"
                  checked={reportKind === "path"}
                  onChange={() => setReportKind("path")}
                />
                <span>
                  A corridor, staircase or lift is blocked
                  <small>Closed, under repair, or not usable</small>
                </span>
              </label>
            </fieldset>
            {reportKind === "path" &&
              (nearbyPaths.isPending && !routeParts.length ? (
                <StateBox />
              ) : routeParts.length || nearbyParts.length ? (
                <PathPicker
                  routeParts={routeParts}
                  nearbyParts={nearbyParts}
                  states={pathStates.data || []}
                  map={map}
                  place={mapPlace}
                  value={reportEdge}
                  onChange={setReportEdge}
                />
              ) : (
                <p className="field-hint">
                  {selectedPlace?.name} isn't connected to the mapped
                  corridors, so a blocked path can't be pinned here. Open a
                  nearby room or corridor on the map and report it from there.
                </p>
              ))}
            <label>
              {reportKind === "path" ? "What did you see?" : "What's wrong?"}
              <textarea
                required
                maxLength={2000}
                value={report}
                onChange={(e) => setReport(e.target.value)}
                placeholder={
                  reportKind === "path"
                    ? "e.g. The corridor is closed for repairs until Friday"
                    : "e.g. It's open 9:00–17:00, not 8:00–18:00"
                }
              />
            </label>
            {reporting.isError && <StateBox error={reporting.error} />}
            <Button
              type="submit"
              disabled={
                reporting.isPending ||
                !report.trim() ||
                (reportKind === "path" && !reportEdge)
              }
            >
              Submit report
            </Button>
          </form>
        )}
      </Dialog>
    </div>
  );
}
