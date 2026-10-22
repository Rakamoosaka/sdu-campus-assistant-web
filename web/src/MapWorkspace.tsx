import { useLocation, useNavigate } from "react-router-dom";
import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
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
} from "lucide-react";
import { Button } from "./components/ui/button";
import { Dialog } from "./components/ui/dialog";
import {
  get,
  api,
  errorMessage,
  type Person,
  type Place,
  type CampusMap,
  type MapPlace,
  type PathResult,
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
}: MapProps) {
  const location = useLocation(),
    navigate = useNavigate();
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
    [report, setReport] = useState("");
  const zoom = useRef<ReactZoomPanPinchRef>(null),
    viewport = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(0.5);
  useEffect(() => {
    if (incomingRoute)
      navigate(location.pathname, { replace: true, state: null });
  }, []);
  const selectedPlace = all.find((p) => p.id === selected),
    mapPlace = map.places.find((p) => p.id === selected);
  const search = useQuery({
    queryKey: ["search", debounced],
    queryFn: () => get<Place[]>("/search?q=" + encodeURIComponent(debounced)),
    enabled: debounced.length > 0,
  });
  const results = debounced
    ? search.data || []
    : all.filter((p) => category === "All" || p.category === category);
  const saved = favorites.some((p) => p.id === selected);
  const planning = useMutation({
    mutationFn: () =>
      get<PathResult>(`/routes?start=${start}&destination=${selected}`),
    onSuccess: (data) => {
      setRoute(data);
      setRouteError("");
      if (data.route_floors?.length) setFloor(data.route_floors[0]);
    },
    onError: (e) => setRouteError(errorMessage(e)),
  });
  const reporting = useMutation({
    mutationFn: () =>
      api.post("/reports", { message: report, location_id: selected }),
    onSuccess: () => {
      setReportOpen(false);
      setReport("");
    },
  });
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
    if (selected === null) return;
    if (mapPlace?.map_floor && route?.destination_location_id !== selected)
      setFloor(mapPlace.map_floor);
    setPanelOpen(true);
  }, [selected]);
  const floorSegments = useMemo(
    () => route?.segments.filter((s) => s.floor === floor) || [],
    [route, floor],
  );
  useEffect(() => {
    if (!route && mapPlace?.has_position) {
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
  }, [selected, floor, scale]);
  useEffect(() => {
    if (floorSegments.length) {
      const timer = setTimeout(
        () => zoom.current?.zoomToElement("route-bounds", undefined, 350),
        150,
      );
      return () => clearTimeout(timer);
    } else if (route) {
      fit();
    }
  }, [route, floor, scale]);
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
              r={active ? 14 : 11}
              fill={active ? "#2662df" : "#fff"}
              stroke={isSaved ? "#b69247" : "#364e75"}
              strokeWidth={active ? 3 : 1.7}
            />
            <text
              x={x}
              y={y + 3}
              textAnchor="middle"
              fill={active ? "#fff" : "#30476c"}
              fontSize={8}
              fontWeight={700}
            >
              {p.category === "Stairs"
                ? p.map_key.match(/stair_main_0?(\d+)/)
                  ? `S${Number(p.map_key.match(/stair_main_0?(\d+)/)![1])}`
                  : "S"
                : p.category === "Lift"
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
              {search.isFetching && debounced ? (
                <StateBox />
              ) : search.isError && debounced ? (
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
                <a href="/assistant">
                  Meet your assistant <ArrowUpRight size={14} />
                </a>
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
                <span>Map position</span>
                <strong>
                  {mapPlace?.has_position ? "Schematic" : "Not mapped"}
                </strong>
              </div>
            </div>
            <p className="position-note">
              <Info size={15} />
              <span>
                {mapPlace?.notes ||
                  "Added to the catalogue. A mapped approach has not been confirmed."}{" "}
                Step-free approaches and lift availability are unverified.
              </span>
            </p>
            <div className="detail-actions">
              {person.role === "guest" ? (
                <Button variant="outline" onClick={onLogin}>
                  <Bookmark size={16} /> Log in to save
                </Button>
              ) : (
                <Button
                  variant={saved ? "secondary" : "outline"}
                  disabled={savePending || (!saved && favorites.length >= 5)}
                  onClick={() => onSave(selectedPlace)}
                >
                  <Bookmark size={16} fill={saved ? "currentColor" : "none"} />
                  {saved ? "Remove saved" : "Save place"}{" "}
                  <span className="count">{favorites.length}/5</span>
                </Button>
              )}
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
                  value={start}
                  onChange={(e) => {
                    setStart(Number(e.target.value));
                    setRoute(null);
                  }}
                  aria-label="Route start"
                >
                  {all
                    .filter((p) => map.places.some((m) => m.id === p.id))
                    .map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name} · {p.floor}
                      </option>
                    ))}
                </select>
              </label>
              <div className="route-destination">
                <MapPin size={16} /> {selectedPlace.name}
              </div>
              <Button
                className="w-full"
                disabled={planning.isPending}
                onClick={() => planning.mutate()}
              >
                <Navigation size={16} />
                {planning.isPending ? "Finding a route…" : "Find route"}
              </Button>
              <p className="route-hint">
                Choose your start manually. No live indoor positioning.
              </p>
              {routeError && (
                <div role="alert" className="error-box">
                  {routeError}
                </div>
              )}
            </div>
            {route && (
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
                    Stairs excluded · lift connections only
                  </span>
                )}
                <p>{route.message}</p>
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
                  <p className="muted text-xs">
                    Distance & walking time unavailable: the schematic has no
                    measured scale.
                  </p>
                )}
              </section>
            )}
            {person.role !== "guest" && (
              <Button
                variant="ghost"
                size="sm"
                className="mt-4"
                onClick={() => setReportOpen(true)}
              >
                <Flag size={14} /> Report an inaccuracy
              </Button>
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
            <Search size={16} /> Explore
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
        </div>
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
          {route && (
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
        <div className="map-attribution">
          SDU CAMPUS ASSISTANT <span>·</span> COURSE PROJECT
        </div>
      </section>
      <Dialog
        open={reportOpen}
        onOpenChange={setReportOpen}
        title="Help improve campus information"
        description={`Report an inaccuracy for ${selectedPlace?.name}.`}
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            reporting.mutate();
          }}
        >
          <label>
            What needs correcting?
            <textarea
              required
              maxLength={2000}
              value={report}
              onChange={(e) => setReport(e.target.value)}
              placeholder="Describe what you noticed…"
            />
          </label>
          {reporting.isError && <StateBox error={reporting.error} />}
          <Button
            type="submit"
            disabled={reporting.isPending || !report.trim()}
          >
            Submit report
          </Button>
        </form>
      </Dialog>
    </div>
  );
}
