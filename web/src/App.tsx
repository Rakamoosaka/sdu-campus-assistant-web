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
  Flag,
  ChevronUp,
} from "lucide-react";
import { Auth } from "./Auth";
import { MapWorkspace, StateBox } from "./MapWorkspace";
import {
  AdminPage,
  AssistantPage,
  SavedPage,
  AnnouncementsPage,
  SchedulePage,
  MyReportsPage,
  initials,
  roleLabel,
} from "./Pages";
import { Button } from "./components/ui/button";
import { OfflineMapControl } from "./components/MapActions";
import { AccountMenu } from "./components/AccountMenu";
import { features } from "./features";
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
  type Report,
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
    [authOverride, setAuthOverride] = useState(false),
    [accountOpen, setAccountOpen] = useState(false);
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
  const myReports = useQuery({
    queryKey: ["my-reports"],
    queryFn: () => get<Report[]>("/reports/me"),
    enabled: !offline && !!person,
    refetchInterval: 60000,
  });
  const unreadReports =
    myReports.data?.filter((r) => r.reporter_unread).length || 0;
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
      on: features.timetable,
    },
    {
      to: "/announcements",
      label: "Announcements",
      icon: Megaphone,
      on: features.announcements,
    },
    { to: "/reports", label: "My reports", icon: Flag },
  ].filter((link) => link.on !== false);
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
                {to === "/reports" && unreadReports > 0 && (
                  <small
                    className="nav-badge-new"
                    aria-label={`${unreadReports} new report updates`}
                  >
                    {unreadReports}
                  </small>
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
          {!offline && (
            <button
              className="identity-link"
              aria-haspopup="dialog"
              aria-expanded={accountOpen}
              aria-label="Your account"
              onClick={() => setAccountOpen(!accountOpen)}
            >
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
              <ChevronUp size={15} />
            </button>
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
          <button
            className="compact-identity"
            aria-haspopup="dialog"
            aria-expanded={accountOpen}
            aria-label="Your account"
            onClick={() => setAccountOpen(!accountOpen)}
          >
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
          </button>
        )}
        {!offline && accountOpen && (
          <AccountMenu
            person={person}
            name={person.full_name || person.name || "Campus Visitor"}
            role={roleLabel(person.role)}
            initials={initials(person)}
            onClose={() => setAccountOpen(false)}
            onLogin={() => {
              setAccountOpen(false);
              onLogin();
            }}
            onLogout={() => {
              setAccountOpen(false);
              logout.mutate();
            }}
          />
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
                <Route
                  path="/announcements"
                  element={
                    features.announcements ? (
                      <AnnouncementsPage {...props} />
                    ) : (
                      <Navigate to="/map" replace />
                    )
                  }
                />
                <Route
                  path="/updates"
                  element={<Navigate to="/announcements" replace />}
                />
                <Route
                  path="/schedule"
                  element={
                    features.timetable ? (
                      <SchedulePage {...props} />
                    ) : (
                      <Navigate to="/map" replace />
                    )
                  }
                />
                <Route path="/reports" element={<MyReportsPage {...props} />} />
                <Route
                  path="/profile"
                  element={<Navigate to="/reports" replace />}
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
