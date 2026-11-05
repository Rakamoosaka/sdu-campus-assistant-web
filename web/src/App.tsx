import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  NavLink,
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";
import {
  Map,
  Sparkles,
  Bookmark,
  CalendarDays,
  Megaphone,
  UserRound,
  ShieldCheck,
  LogOut,
  ArrowUpRight,
} from "lucide-react";
import { Auth } from "./Auth";
import { MapWorkspace, StateBox } from "./MapWorkspace";
import {
  AdminPage,
  AssistantPage,
  SavedPage,
  UpdatesPage,
  SchedulePage,
  ProfilePage,
  initials,
  roleLabel,
} from "./Pages";
import { Button } from "./components/ui/button";
import { OfflineMapControl } from "./components/MapActions";
import {
  prepareOfflineShell,
  readSavedMap,
  type SavedMap,
} from "./lib/offlineMap";
import { isAxiosError } from "axios";
import {
  api,
  get,
  setCsrf,
  errorMessage,
  type Person,
  type Place,
  type CampusMap,
  type PathResult,
} from "./lib/api";
import logo from "../../assets/images/sdu_30_logo.png";
const visitor: Person = { role: "guest" };

export default function App() {
  const qc = useQueryClient(),
    navigate = useNavigate(),
    location = useLocation();
  const shared =
    location.pathname === "/map"
      ? new URLSearchParams(location.search).get("place")
      : null;
  const sharedId = shared && /^[1-9]\d*$/.test(shared) ? Number(shared) : null;
  const [connected, setConnected] = useState(navigator.onLine);
  const [publicVisitor, setPublicVisitor] = useState(false);
  const [retainingSnapshot, setRetainingSnapshot] = useState(!navigator.onLine);
  const savedMap = useQuery({
    queryKey: ["offline-map"],
    queryFn: readSavedMap,
    networkMode: "always",
    retry: false,
    staleTime: Infinity,
  });
  const saved = savedMap.data || null;
  useEffect(() => {
    const onConnection = () => {
      setConnected(navigator.onLine);
      if (navigator.onLine) {
        void qc.invalidateQueries({ queryKey: ["identity"] });
      }
    };
    window.addEventListener("online", onConnection);
    window.addEventListener("offline", onConnection);
    void prepareOfflineShell()?.catch(() => {
      /* Download can retry registration. */
    });
    return () => {
      window.removeEventListener("online", onConnection);
      window.removeEventListener("offline", onConnection);
    };
  }, [qc]);
  const [selected, setSelected] = useState<number | null>(null),
    [toast, setToast] = useState(""),
    [authOverride, setAuthOverride] = useState(false);
  const identity = useQuery({
    queryKey: ["identity"],
    queryFn: ({ signal }) =>
      api
        .get<Person>("/users/me", { signal, timeout: 5000 })
        .then((response) => response.data),
    enabled: connected,
    networkMode: "always",
    retry: false,
  });
  const networkUnavailable =
    !connected ||
    (isAxiosError(identity.error) &&
      (!identity.error.response ||
        [502, 503, 504].includes(identity.error.response.status)));
  const anonymous =
    isAxiosError(identity.error) && identity.error.response?.status === 401;
  const onlinePerson =
    identity.data ||
    (anonymous && (shared !== null || publicVisitor || retainingSnapshot)
      ? visitor
      : undefined);
  useEffect(() => {
    if (shared !== null && anonymous) setPublicVisitor(true);
  }, [shared, anonymous]);
  const places = useQuery({
    queryKey: ["places"],
    queryFn: () => get<Place[]>("/locations"),
    enabled: !networkUnavailable && !!onlinePerson,
  });
  const map = useQuery({
    queryKey: ["map"],
    queryFn: () => get<CampusMap>("/campus-map"),
    enabled: !networkUnavailable && !!onlinePerson,
  });
  const liveMapReady = !!onlinePerson && !!places.data && !!map.data;
  useEffect(() => {
    if (networkUnavailable && saved) {
      setRetainingSnapshot(true);
      setPublicVisitor(true);
    } else if (liveMapReady || !saved) {
      setRetainingSnapshot(false);
    }
  }, [networkUnavailable, saved, liveMapReady]);
  const offline =
    networkUnavailable || (retainingSnapshot && !!saved && !liveMapReady);
  const person = offline ? visitor : onlinePerson;
  function retryConnection() {
    setConnected(navigator.onLine);
    if (!navigator.onLine) return;
    void identity.refetch();
    if (onlinePerson && !networkUnavailable) {
      void places.refetch();
      void map.refetch();
    }
  }
  const favorites = useQuery({
    queryKey: ["favorites", person?.id],
    queryFn: () => get<Place[]>("/users/me/favorites"),
    enabled: !offline && !!person && person.role !== "guest",
  });
  const logout = useMutation({
    mutationFn: () => api.post("/auth/logout"),
    onSuccess: () => {
      setCsrf();
      qc.clear();
      setSelected(null);
      setPublicVisitor(false);
      navigate("/");
      setAuthOverride(false);
    },
    onError: (e) => setToast(errorMessage(e)),
  });
  const saving = useMutation({
    mutationFn: (p: Place) =>
      favorites.data?.some((f) => f.id === p.id)
        ? api.delete(`/users/me/favorites/${p.id}`)
        : api.post(`/users/me/favorites/${p.id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["favorites"] });
      setToast("Saved places updated.");
    },
    onError: (e) => setToast(errorMessage(e)),
  });
  function openPlace(id: number, route?: PathResult) {
    setSelected(id);
    navigate("/map", { state: route ? { assistantRoute: route } : null });
  }
  function onLogin() {
    setAuthOverride(true);
  }
  if (offline && !saved && !savedMap.isPending) {
    return (
      <div className="app-loading">
        <img src={logo} alt="SDU University" />
        <h1>No offline map is saved on this device</h1>
        <p>Reconnect once to download the campus map.</p>
        <Button onClick={retryConnection}>Try connection again</Button>
      </div>
    );
  }
  if ((!offline && identity.isPending) || (offline && savedMap.isPending))
    return (
      <div className="app-loading">
        <img src={logo} alt="SDU University" />
        <StateBox empty="Opening your campus…" />
      </div>
    );
  if (!person || (authOverride && !offline))
    return (
      <Auth
        onSuccess={() => {
          qc.clear();
          setAuthOverride(false);
          if (shared === null) navigate("/map");
        }}
      />
    );
  const currentPlaces = offline ? saved?.places : places.data;
  const currentMap = offline ? saved?.map : map.data;
  const linkedPlace =
    sharedId === null
      ? undefined
      : currentPlaces?.find((p) => p.id === sharedId);
  const props = { person, places: currentPlaces || [], openPlace, onLogin };
  const links = [
    { to: "/map", label: "Campus map", icon: Map },
    { to: "/assistant", label: "Assistant", icon: Sparkles },
    { to: "/saved", label: "Saved places", icon: Bookmark },
    {
      to: "/schedule",
      label: person.role === "teacher" ? "Teaching" : "Timetable",
      icon: CalendarDays,
    },
    { to: "/updates", label: "Campus updates", icon: Megaphone },
    { to: "/profile", label: "Profile", icon: UserRound },
  ];
  return (
    <div className={offline ? "app-shell offline" : "app-shell"}>
      <aside className="sidebar">
        <NavLink
          to="/map"
          className="brand"
          aria-label="SDU Campus Assistant home"
        >
          <img src={logo} alt="SDU University 30th anniversary" />
          <span>
            CAMPUS
            <br />
            <strong>ASSISTANT</strong>
          </span>
        </NavLink>
        <div className="nav-label">YOUR CAMPUS</div>
        <nav aria-label="Main navigation">
          {(offline ? links.slice(0, 2) : links).map(
            ({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                onClick={(event) => {
                  if (offline && to === "/assistant") {
                    event.preventDefault();
                    setToast("The assistant needs a connection.");
                  }
                }}
              >
                <Icon size={20} />
                <span>{label}</span>
                {to === "/saved" && person.role !== "guest" && (
                  <small>{favorites.data?.length || 0}</small>
                )}
              </NavLink>
            ),
          )}
          {person.role === "admin" && (
            <NavLink to="/admin">
              <ShieldCheck size={20} />
              <span>Administration</span>
            </NavLink>
          )}
        </nav>
        <div className="sidebar-bottom">
          <div className="course-note">
            <span className="gold-line" />
            <p>
              Built by students.
              <br />
              For the campus community.
            </p>
            <small>SEMESTER PROJECT</small>
          </div>
          {!offline && (
            <NavLink className="identity-link" to="/profile">
              <div className="avatar">
                {person.role === "guest" ? (
                  <UserRound size={20} />
                ) : (
                  initials(person)
                )}
              </div>
              <span>
                <strong>
                  {person.full_name || person.name || "Campus Visitor"}
                </strong>
                <small>{roleLabel(person.role)}</small>
              </span>
              <ArrowUpRight size={15} />
            </NavLink>
          )}
          {!offline && person.role === "guest" && (
            <button className="guest-sign-in" onClick={onLogin}>
              Sign in to your account ↗
            </button>
          )}
        </div>
      </aside>
      <main className="app-main">
        {!offline && (
          <NavLink to="/profile" className="compact-identity">
            <span>
              SDU <b>Campus Assistant</b>
            </span>
            <span>
              <span>
                <strong>
                  {person.full_name || person.name || "Campus Visitor"}
                </strong>
                <small>{roleLabel(person.role)}</small>
              </span>
              <i className="avatar">{initials(person)}</i>
            </span>
          </NavLink>
        )}
        {(!currentPlaces || !currentMap) &&
        (places.isPending || map.isPending) ? (
          <StateBox />
        ) : !currentPlaces || !currentMap ? (
          <StateBox
            error={places.error || map.error}
            retry={() => {
              places.refetch();
              map.refetch();
            }}
          />
        ) : (
          <Routes>
            <Route
              path="/map"
              element={
                <MapWorkspace
                  person={person}
                  selected={
                    shared === null ? selected : (linkedPlace?.id ?? null)
                  }
                  onSelect={(id) => {
                    setSelected(id);
                    if (shared !== null) navigate("/map", { replace: true });
                  }}
                  sharedDestination={shared !== null}
                  offlineDate={offline ? saved?.savedAt : undefined}
                  onRetryConnection={
                    offline &&
                    connected &&
                    (identity.isError || places.isError || map.isError)
                      ? retryConnection
                      : undefined
                  }
                  offlineControl={
                    <OfflineMapControl
                      saved={saved}
                      offline={offline}
                      onChange={(snapshot) =>
                        qc.setQueryData<SavedMap | null>(
                          ["offline-map"],
                          snapshot,
                        )
                      }
                    />
                  }
                  all={currentPlaces}
                  map={currentMap}
                  favorites={offline ? [] : favorites.data || []}
                  onSave={(p) => saving.mutate(p)}
                  onLogin={onLogin}
                  savePending={saving.isPending}
                />
              }
            />
            {!offline && (
              <>
                <Route
                  path="/assistant"
                  element={<AssistantPage {...props} />}
                />
                <Route
                  path="/saved"
                  element={
                    favorites.isError ? (
                      <StateBox
                        error={favorites.error}
                        retry={() => favorites.refetch()}
                      />
                    ) : (
                      <SavedPage
                        {...props}
                        favorites={favorites.data || []}
                        onSave={(p) => saving.mutate(p)}
                        pending={saving.isPending}
                      />
                    )
                  }
                />
                <Route path="/updates" element={<UpdatesPage {...props} />} />
                <Route path="/schedule" element={<SchedulePage {...props} />} />
                <Route
                  path="/profile"
                  element={
                    <ProfilePage {...props} onLogout={() => logout.mutate()} />
                  }
                />
                <Route
                  path="/admin"
                  element={
                    person.role === "admin" ? (
                      <AdminPage {...props} />
                    ) : (
                      <Navigate to="/map" replace />
                    )
                  }
                />
              </>
            )}
            <Route path="*" element={<Navigate to="/map" replace />} />
          </Routes>
        )}
      </main>
      {toast && (
        <div className="toast" role="status">
          <span>{toast}</span>
          <button
            aria-label="Dismiss notification"
            onClick={() => setToast("")}
          >
            ×
          </button>
        </div>
      )}
    </div>
  );
}
