import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  NavLink,
  Navigate,
  Route,
  Routes,
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
import {
  api,
  get,
  setCsrf,
  errorMessage,
  type Person,
  type Place,
  type CampusMap,
} from "./lib/api";
import logo from "../../assets/images/sdu_30_logo.png";
export default function App() {
  const qc = useQueryClient(),
    navigate = useNavigate();
  const [selected, setSelected] = useState<number | null>(null),
    [toast, setToast] = useState(""),
    [authOverride, setAuthOverride] = useState(false);
  const identity = useQuery({
    queryKey: ["identity"],
    queryFn: () => get<Person>("/users/me"),
    retry: false,
  });
  const person = identity.data;
  const places = useQuery({
    queryKey: ["places"],
    queryFn: () => get<Place[]>("/locations"),
    enabled: !!person,
  });
  const map = useQuery({
    queryKey: ["map"],
    queryFn: () => get<CampusMap>("/campus-map"),
    enabled: !!person,
  });
  const favorites = useQuery({
    queryKey: ["favorites", person?.id],
    queryFn: () => get<Place[]>("/users/me/favorites"),
    enabled: !!person && person.role !== "guest",
  });
  const logout = useMutation({
    mutationFn: () => api.post("/auth/logout"),
    onSuccess: () => {
      setCsrf();
      qc.clear();
      setSelected(null);
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
  function openPlace(id: number) {
    setSelected(id);
    navigate("/map");
  }
  function onLogin() {
    setAuthOverride(true);
  }
  if (identity.isPending)
    return (
      <div className="app-loading">
        <img src={logo} alt="SDU University" />
        <StateBox empty="Opening your campus…" />
      </div>
    );
  if (!person || authOverride)
    return (
      <Auth
        onSuccess={() => {
          qc.clear();
          setAuthOverride(false);
          navigate("/map");
        }}
      />
    );
  const props = { person, places: places.data || [], openPlace, onLogin };
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
    <div className="app-shell">
      <aside className="sidebar">
        <a href="/map" className="brand" aria-label="SDU Campus Assistant home">
          <img src={logo} alt="SDU University 30th anniversary" />
          <span>
            CAMPUS
            <br />
            <strong>ASSISTANT</strong>
          </span>
        </a>
        <div className="nav-label">YOUR CAMPUS</div>
        <nav aria-label="Main navigation">
          {links.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to}>
              <Icon size={20} />
              <span>{label}</span>
              {to === "/saved" && person.role !== "guest" && (
                <small>{favorites.data?.length || 0}</small>
              )}
            </NavLink>
          ))}
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
          {person.role === "guest" && (
            <button className="guest-sign-in" onClick={onLogin}>
              Sign in to your account ↗
            </button>
          )}
        </div>
      </aside>
      <main className="app-main">
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
        {places.isPending || map.isPending ? (
          <StateBox />
        ) : places.isError || map.isError ? (
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
                  selected={selected}
                  onSelect={setSelected}
                  all={places.data!}
                  map={map.data!}
                  favorites={favorites.data || []}
                  onSave={(p) => saving.mutate(p)}
                  onLogin={onLogin}
                  savePending={saving.isPending}
                />
              }
            />
            <Route path="/assistant" element={<AssistantPage {...props} />} />
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
