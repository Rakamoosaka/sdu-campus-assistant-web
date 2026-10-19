import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowUpRight,
  Bookmark,
  CalendarDays,
  Check,
  ChevronRight,
  Clock,
  LogOut,
  MapPin,
  Plus,
  Send,
  ShieldCheck,
  Sparkles,
  UserRound,
  Accessibility,
} from "lucide-react";
import { Button } from "./components/ui/button";
import { Dialog } from "./components/ui/dialog";
import { StateBox } from "./MapWorkspace";
import {
  api,
  get,
  errorMessage,
  localTime,
  type Person,
  type Place,
  type News,
  type Lesson,
  type Answer,
  type Report,
} from "./lib/api";
interface Props {
  person: Person;
  places: Place[];
  openPlace: (id: number) => void;
  onLogin: () => void;
}
export function PageIntro({
  label,
  title,
  children,
}: {
  label: string;
  title: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="page-intro">
      <span className="eyebrow">{label}</span>
      <h1>{title}</h1>
      {children && <p>{children}</p>}
    </div>
  );
}
export function PlaceActions({
  place,
  openPlace,
}: {
  place: Place;
  openPlace: (id: number) => void;
}) {
  return (
    <Button variant="outline" size="sm" onClick={() => openPlace(place.id)}>
      <MapPin size={14} /> {place.name}
      <ArrowUpRight size={14} />
    </Button>
  );
}
export function AssistantPage({ person, openPlace }: Props) {
  const [text, setText] = useState(""),
    [messages, setMessages] = useState<{ user?: string; reply?: Answer }[]>([]);
  const send = useMutation({
    mutationFn: (body: {
      question?: string;
      context_id?: string;
      selection_id?: number;
    }) => api.post<Answer>("/assistant/query", body).then((r) => r.data),
    onSuccess: (data) => setMessages((m) => [...m, { reply: data }]),
  });
  function ask(question: string) {
    if (!question.trim()) return;
    setMessages((m) => [...m, { user: question }]);
    setText("");
    send.mutate({ question });
  }
  return (
    <div className="content-page assistant-page">
      <PageIntro
        label="A LITTLE LOCAL KNOWLEDGE"
        title="A hand finding your way."
      >
        Ask about rooms, campus services or your next class.
      </PageIntro>
      <div className="assistant-layout">
        <section className="chat-panel">
          <div className="assistant-welcome">
            <span className="assistant-emblem">
              <Sparkles size={26} />
            </span>
            <h2>
              Hi{" "}
              {person.role === "guest"
                ? "there"
                : person.full_name?.split(" ")[0] || person.name}
              . Where can I help you go?
            </h2>
            <p>
              I use the campus catalogue and schematic map. If something is
              unconfirmed, I’ll say so.
            </p>
            <div className="prompt-chips">
              {[
                "Where is D201?",
                "I feel sick",
                "Where can I print?",
                "Where is my next class?",
              ].map((q) => (
                <button
                  key={q}
                  onClick={() => ask(q)}
                  disabled={send.isPending}
                >
                  {q}
                  <ArrowUpRight size={14} />
                </button>
              ))}
            </div>
          </div>
          <div className="messages" aria-live="polite">
            {messages.map((message, i) =>
              message.user ? (
                <div className="user-message" key={i}>
                  {message.user}
                </div>
              ) : (
                <div className="assistant-message" key={i}>
                  <span className="mini-spark">
                    <Sparkles size={16} />
                  </span>
                  <div>
                    <p>{message.reply?.answer}</p>
                    {message.reply?.location && (
                      <PlaceActions
                        place={message.reply.location}
                        openPlace={openPlace}
                      />
                    )}
                    <div className="choice-list">
                      {message.reply?.choices.map((p) => (
                        <Button
                          key={p.id}
                          variant="outline"
                          size="sm"
                          disabled={send.isPending}
                          onClick={() => {
                            setMessages((m) => [
                              ...m,
                              { user: p.name + " · " + p.floor },
                            ]);
                            send.mutate({
                              context_id: message.reply?.context_id,
                              selection_id: p.id,
                            });
                          }}
                        >
                          {p.name} · {p.floor}
                          <ChevronRight size={13} />
                        </Button>
                      ))}
                    </div>
                  </div>
                </div>
              ),
            )}
            {send.isPending && (
              <StateBox empty="Checking the campus catalogue…" />
            )}
            {send.isError && (
              <StateBox error={send.error} retry={() => send.reset()} />
            )}
          </div>
          <form
            className="chat-input"
            onSubmit={(e) => {
              e.preventDefault();
              ask(text);
            }}
          >
            <input
              aria-label="Ask the campus assistant"
              value={text}
              onChange={(e) => setText(e.target.value)}
              maxLength={500}
              placeholder="Ask a campus question…"
            />
            <Button
              size="icon"
              type="submit"
              aria-label="Send question"
              disabled={send.isPending || !text.trim()}
            >
              <Send size={18} />
            </Button>
          </form>
        </section>
        <aside className="context-card">
          <span className="eyebrow">GOOD TO KNOW</span>
          <h3>Grounded in campus data.</h3>
          <p>
            No external AI account needed. This assistant finds real catalogue
            matches and helps you choose when a request is ambiguous.
          </p>
          <hr />
          <p>
            Room layouts and routes are schematic. Hours, contacts and
            accessibility may be unconfirmed.
          </p>
        </aside>
      </div>
    </div>
  );
}
export function SavedPage({
  person,
  openPlace,
  onLogin,
  favorites,
  onSave,
  pending,
}: {
  person: Person;
  openPlace: (id: number) => void;
  onLogin: () => void;
  favorites: Place[];
  onSave: (p: Place) => void;
  pending: boolean;
}) {
  return (
    <div className="content-page">
      <PageIntro label="YOUR SHORTCUTS" title="A few familiar places.">
        {person.role === "guest"
          ? "Log in to keep your own collection of campus places."
          : `${favorites.length} of 5 places saved to your account. Remove a place to make room for another.`}
      </PageIntro>
      {person.role === "guest" ? (
        <LoginPrompt onLogin={onLogin} />
      ) : favorites.length === 0 ? (
        <div className="empty-card">
          <Bookmark size={32} />
          <h2>Your campus shortcuts start here.</h2>
          <p>Explore the map and save up to five places you visit often.</p>
          <Button onClick={() => openPlace(1)}>
            Explore campus <ArrowUpRight size={16} />
          </Button>
        </div>
      ) : (
        <div className="cards-grid">
          {favorites.map((p) => (
            <article className="place-card" key={p.id}>
              <span className="location-icon">
                <MapPin size={23} />
              </span>
              <span className="category-tag">{p.category}</span>
              <h2>{p.name}</h2>
              <p>
                {p.block} · {p.floor}
              </p>
              <div className="card-actions">
                <Button variant="outline" onClick={() => openPlace(p.id)}>
                  Open on map
                  <ArrowUpRight size={15} />
                </Button>
                <Button
                  variant="ghost"
                  disabled={pending}
                  onClick={() => onSave(p)}
                >
                  Remove
                </Button>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
export function LoginPrompt({ onLogin }: { onLogin: () => void }) {
  return (
    <div className="empty-card">
      <UserRound size={30} />
      <h2>Make campus yours.</h2>
      <p>
        Sign in for saved places, personal schedules and account preferences.
      </p>
      <Button onClick={onLogin}>
        Log in or create an account
        <ArrowUpRight size={16} />
      </Button>
    </div>
  );
}
export function UpdatesPage({ openPlace, person }: Props) {
  const news = useQuery({
    queryKey: ["news"],
    queryFn: () => get<News[]>("/announcements"),
  });
  return (
    <div className="content-page">
      <PageIntro label="AROUND THE CAMPUS" title="Stay in the loop.">
        Announcements and events from the campus catalogue. Seeded presentation
        content is sample data.
      </PageIntro>
      {news.isPending ? (
        <StateBox />
      ) : news.isError ? (
        <StateBox error={news.error} retry={() => news.refetch()} />
      ) : !news.data.length ? (
        <StateBox empty="No campus updates have been published yet." />
      ) : (
        <div className="news-grid">
          {news.data.map((n, i) => (
            <article
              className={"news-card " + (i === 0 ? "featured" : "")}
              key={n.id}
            >
              <div className="news-meta">
                <span>{i === 0 ? "LATEST UPDATE" : "CAMPUS UPDATE"}</span>
                <span>{localTime(n.published_at)}</span>
              </div>
              <h2>{n.title}</h2>
              <p>{n.body}</p>
              {n.location_id && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => openPlace(n.location_id!)}
                >
                  View location
                  <ArrowUpRight size={15} />
                </Button>
              )}
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
export function SchedulePage({ person, onLogin, openPlace, places }: Props) {
  const qc = useQueryClient();
  const [editing, setEditing] = useState<Lesson | null | undefined>(undefined);
  const save = useMutation({
    mutationFn: (body: unknown) =>
      editing
        ? api.put(`/students/me/timetable/${editing.id}`, body)
        : api.post("/students/me/timetable", body),
    onSuccess: () => {
      setEditing(undefined);
      qc.invalidateQueries({ queryKey: ["schedule"] });
      qc.invalidateQueries({ queryKey: ["next-class"] });
    },
  });
  const schedule = useQuery({
    queryKey: ["schedule", person.id],
    queryFn: () =>
      get<Lesson[]>(
        person.role === "teacher"
          ? "/teachers/me/schedule"
          : "/students/me/timetable",
      ),
    enabled: person.role !== "guest",
  });
  const next = useQuery({
    queryKey: ["next-class", person.id],
    queryFn: () => get<Lesson | null>("/students/me/next-class"),
    enabled: person.role !== "guest",
  });
  return (
    <div className="content-page">
      <PageIntro
        label="YOUR DAY, AT A GLANCE"
        title={
          person.role === "teacher"
            ? "Your teaching schedule."
            : "One class at a time."
        }
      >
        Stored sample schedule · All times in Asia/Almaty (UTC+5).
      </PageIntro>
      {person.role === "guest" ? (
        <LoginPrompt onLogin={onLogin} />
      ) : (
        <>
          <Button
            className="mb-5"
            variant="outline"
            onClick={() => {
              setEditing(null);
              save.reset();
            }}
          >
            <Plus size={16} /> Add sample lesson
          </Button>
          {next.data && (
            <div className="next-class">
              <div>
                <span className="eyebrow gold">UP NEXT · SAMPLE LESSON</span>
                <h2>{next.data.course}</h2>
                <p>
                  {localTime(next.data.starts_at)} · {next.data.room}
                </p>
              </div>
              {next.data.location_id &&
              places.some((p) => p.id === next.data?.location_id) ? (
                <Button
                  variant="outline"
                  onClick={() => openPlace(next.data!.location_id!)}
                >
                  Find classroom <ArrowUpRight size={16} />
                </Button>
              ) : (
                <span>Room is not in the mapped catalogue</span>
              )}
            </div>
          )}
          {schedule.isPending ? (
            <StateBox />
          ) : schedule.isError ? (
            <StateBox error={schedule.error} retry={() => schedule.refetch()} />
          ) : !schedule.data.length ? (
            <StateBox empty="No lessons are stored for this account. No upcoming class is available." />
          ) : (
            <section className="schedule-list">
              {schedule.data.map((lesson) => (
                <article key={lesson.id}>
                  <span className="schedule-icon">
                    <CalendarDays size={20} />
                  </span>
                  <div>
                    <small>{localTime(lesson.starts_at)}</small>
                    <h3>{lesson.course}</h3>
                    <p>
                      {lesson.room} · Sample{" "}
                      {lesson.kind === "teacher"
                        ? "teaching schedule"
                        : "lesson"}
                    </p>
                  </div>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => {
                      setEditing(lesson);
                      save.reset();
                    }}
                  >
                    Edit
                  </Button>
                  {lesson.location_id &&
                  places.some((p) => p.id === lesson.location_id) ? (
                    <Button
                      variant="ghost"
                      onClick={() => openPlace(lesson.location_id!)}
                    >
                      Map
                      <ArrowUpRight size={15} />
                    </Button>
                  ) : (
                    <span className="muted">Unmapped room</span>
                  )}
                </article>
              ))}
            </section>
          )}
        </>
      )}
      <Dialog
        open={editing !== undefined}
        onOpenChange={(open) => {
          if (!open) setEditing(undefined);
        }}
        title={editing ? "Edit sample lesson" : "Add sample lesson"}
        description="All entered dates and times are in Asia/Almaty (UTC+5). This is your editable course-project timetable."
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const values = Object.fromEntries(new FormData(e.currentTarget));
            save.mutate({
              ...values,
              starts_at: values.starts_at + ":00+05:00",
              location_id: values.location_id
                ? Number(values.location_id)
                : null,
            });
          }}
        >
          <label>
            Course
            <input name="course" required defaultValue={editing?.course} />
          </label>
          <label>
            Date and time · Asia/Almaty
            <input
              name="starts_at"
              type="datetime-local"
              required
              defaultValue={
                editing
                  ? new Date(
                      new Date(
                        /Z$|[+-]\d\d:\d\d$/.test(editing.starts_at)
                          ? editing.starts_at
                          : editing.starts_at + "Z",
                      ).getTime() +
                        5 * 3600000,
                    )
                      .toISOString()
                      .slice(0, 16)
                  : ""
              }
            />
          </label>
          <label>
            Room label
            <input
              name="room"
              required
              defaultValue={editing?.room}
              placeholder="e.g. D201"
            />
          </label>
          <label>
            Link to campus location
            <select
              name="location_id"
              defaultValue={editing?.location_id || ""}
            >
              <option value="">Unmapped room</option>
              {places
                .filter((p) => p.category === "Classroom")
                .map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} · {p.floor}
                  </option>
                ))}
            </select>
          </label>
          {save.isError && <StateBox error={save.error} />}
          <Button type="submit" disabled={save.isPending}>
            Save lesson
          </Button>
        </form>
      </Dialog>
    </div>
  );
}
export function ProfilePage({
  person,
  onLogin,
  onLogout,
}: Props & { onLogout: () => void }) {
  const qc = useQueryClient();
  const [draftPref, setDraftPref] = useState<boolean | null>(null);
  const pref = useQuery({
    queryKey: ["preferences"],
    queryFn: () => get<{ accessible_routes: boolean }>("/users/me/preferences"),
    enabled: person.role !== "guest",
  });
  const save = useMutation({
    mutationFn: (value: boolean) =>
      api.put("/users/me/preferences", { accessible_routes: value }),
    onSettled: async () => {
      await qc.invalidateQueries({ queryKey: ["preferences"] });
      setDraftPref(null);
    },
  });
  return (
    <div className="content-page">
      <PageIntro label="A CAMPUS THAT FITS YOU" title="Your profile." />
      {person.role === "guest" ? (
        <LoginPrompt onLogin={onLogin} />
      ) : (
        <div className="profile-grid">
          <section className="profile-card">
            <div className="large-avatar">{initials(person)}</div>
            <h2>{person.full_name || person.name}</h2>
            <p>{person.sdu_id}</p>
            <span className="role-badge">{roleLabel(person.role)}</span>
            <hr />
            <p>
              SDU Campus Assistant account
              <br />
              <small>A course project · No university integration</small>
            </p>
            <Button variant="outline" onClick={onLogout}>
              <LogOut size={16} /> Log out
            </Button>
          </section>
          <section className="preferences-card">
            <span className="eyebrow">NAVIGATION PREFERENCES</span>
            <h2>Find a route that suits you.</h2>
            <div className="preference-row">
              <span className="location-icon">
                <Accessibility size={22} />
              </span>
              <label htmlFor="stairs-pref">
                <strong>Avoid stairs and use lifts</strong>
                <p>Applies to every route you plan while signed in.</p>
              </label>
              <input
                id="stairs-pref"
                type="checkbox"
                role="switch"
                checked={draftPref ?? pref.data?.accessible_routes ?? false}
                disabled={pref.isPending || pref.isError || save.isPending}
                onChange={(e) => {
                  setDraftPref(e.target.checked);
                  save.mutate(e.target.checked);
                }}
              />
            </div>
            {pref.isError && (
              <StateBox error={pref.error} retry={() => pref.refetch()} />
            )}
            {save.isError && <StateBox error={save.error} />}
            {save.isSuccess && !save.isPending && (
              <p className="success-text">
                <Check size={15} /> Preference saved to your account
              </p>
            )}
            <div className="info-note">
              <ShieldCheck size={19} />
              <p>
                Routes use mapped lift connections where available. Approaches
                and lift operation remain unverified. A connected step-free
                route may not be available.
              </p>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
export function initials(person: Person) {
  return (person.full_name || person.name || "Guest")
    .split(" ")
    .slice(0, 2)
    .map((x) => x[0])
    .join("")
    .toUpperCase();
}
export function roleLabel(role: string) {
  return (
    (
      {
        admin: "Administrator",
        student: "Student",
        teacher: "Teacher",
        guest: "Guest",
      } as Record<string, string>
    )[role] || role
  );
}

export function AdminPage({ places }: Props) {
  const qc = useQueryClient();
  const [tab, setTab] = useState("Locations"),
    [editing, setEditing] = useState<Place | null | undefined>(undefined),
    [newsEdit, setNewsEdit] = useState<News | null | undefined>(undefined),
    [message, setMessage] = useState(""),
    [filter, setFilter] = useState("");
  const analytics = useQuery({
    queryKey: ["analytics"],
    queryFn: () =>
      get<{ query: string; count: number }[]>(
        "/admin/analytics/popular-searches",
      ),
  });
  const reports = useQuery({
    queryKey: ["reports"],
    queryFn: () => get<Report[]>("/admin/reports"),
  });
  const users = useQuery({
    queryKey: ["users"],
    queryFn: () => get<Person[]>("/admin/users"),
  });
  const news = useQuery({
    queryKey: ["news"],
    queryFn: () => get<News[]>("/announcements"),
  });
  const update = useMutation({
    mutationFn: ({
      url,
      data,
      method = "put",
    }: {
      url: string;
      data: unknown;
      method?: "put" | "post";
    }) => api[method](url, data),
    onSuccess: () => {
      setEditing(undefined);
      setNewsEdit(undefined);
      setMessage("Changes saved to the database.");
      qc.invalidateQueries();
    },
    onError: () => setMessage(""),
  });
  function saveLocation(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const values = Object.fromEntries(form);
    const body = {
      ...values,
      x: Number(values.x),
      y: Number(values.y),
      accessible: editing?.accessible || false,
    };
    update.mutate({
      url: editing ? `/admin/locations/${editing.id}` : "/admin/locations",
      data: body,
      method: editing ? "put" : "post",
    });
  }
  function saveNews(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const values = Object.fromEntries(new FormData(e.currentTarget));
    update.mutate({
      url: newsEdit
        ? `/admin/announcements/${newsEdit.id}`
        : "/admin/announcements",
      method: newsEdit ? "put" : "post",
      data: {
        ...values,
        location_id: values.location_id ? Number(values.location_id) : null,
      },
    });
  }
  return (
    <div className="content-page">
      <PageIntro label="CAMPUS ADMINISTRATION" title="Keep campus connected.">
        Manage real catalogue data, published updates and submitted corrections.
      </PageIntro>
      <div className="admin-stats">
        <div>
          <span>Catalogue locations</span>
          <strong>{places.length}</strong>
        </div>
        <div>
          <span>Submitted reports</span>
          <strong>{reports.data?.length ?? "—"}</strong>
        </div>
        <div>
          <span>Registered accounts</span>
          <strong>{users.data?.length ?? "—"}</strong>
        </div>
        <div>
          <span>Logged searches</span>
          <strong>
            {analytics.data?.reduce((total, a) => total + a.count, 0) ?? "—"}
          </strong>
        </div>
      </div>
      <div className="admin-tabs">
        {["Locations", "Updates", "Reports", "Search analytics", "Roles"].map(
          (t) => (
            <button
              className={tab === t ? "selected" : ""}
              key={t}
              onClick={() => {
                setTab(t);
                setMessage("");
                update.reset();
              }}
            >
              {t}
            </button>
          ),
        )}
      </div>
      {message && (
        <p role="status" className="success-text">
          <Check size={16} />
          {message}
        </p>
      )}
      {update.isError && <StateBox error={update.error} />}
      {tab === "Locations" && (
        <section className="admin-section">
          <div className="admin-toolbar">
            <input
              placeholder="Filter locations…"
              aria-label="Filter admin locations"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            />
            <Button
              onClick={() => {
                setEditing(null);
                update.reset();
              }}
            >
              <Plus size={16} /> Add location
            </Button>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Location</th>
                  <th>Category</th>
                  <th>Position</th>
                  <th>Hours</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {places
                  .filter((p) =>
                    (p.name + " " + p.block)
                      .toLowerCase()
                      .includes(filter.toLowerCase()),
                  )
                  .map((p) => (
                    <tr key={p.id}>
                      <td>
                        <strong>{p.name}</strong>
                        <small>{p.block}</small>
                      </td>
                      <td>{p.category}</td>
                      <td>{p.floor}</td>
                      <td>{p.opening_hours}</td>
                      <td>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            setEditing(p);
                            update.reset();
                          }}
                        >
                          Edit <ArrowUpRight size={13} />
                        </Button>
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
      {tab === "Updates" && (
        <section className="admin-section">
          <Button
            onClick={() => {
              setNewsEdit(null);
              update.reset();
            }}
          >
            <Plus size={16} /> Publish update
          </Button>
          {news.isError ? (
            <StateBox error={news.error} retry={() => news.refetch()} />
          ) : news.isPending ? (
            <StateBox />
          ) : !news.data.length ? (
            <StateBox empty="No updates yet." />
          ) : (
            news.data.map((n) => (
              <div className="admin-list-row" key={n.id}>
                <div>
                  <h3>{n.title}</h3>
                  <p>{n.body}</p>
                  <small>{localTime(n.published_at)}</small>
                </div>
                <Button
                  variant="outline"
                  onClick={() => {
                    setNewsEdit(n);
                    update.reset();
                  }}
                >
                  Edit
                </Button>
              </div>
            ))
          )}
        </section>
      )}
      {tab === "Reports" && (
        <section className="admin-section">
          {reports.isError ? (
            <StateBox error={reports.error} retry={() => reports.refetch()} />
          ) : reports.isPending ? (
            <StateBox />
          ) : !reports.data.length ? (
            <StateBox empty="No inaccuracies have been submitted." />
          ) : (
            reports.data.map((r) => (
              <div className="admin-list-row" key={r.id}>
                <div>
                  <h3>
                    {r.location_id
                      ? places.find((p) => p.id === r.location_id)?.name ||
                        `Location ${r.location_id}`
                      : "Campus report"}
                  </h3>
                  <p>{r.message}</p>
                  <small>Submitted by {r.author}</small>
                </div>
                <select
                  aria-label={`Report ${r.id} status`}
                  value={r.status}
                  disabled={update.isPending}
                  onChange={(e) =>
                    update.mutate({
                      url: `/admin/reports/${r.id}`,
                      data: { status: e.target.value },
                    })
                  }
                >
                  {["new", "reviewing", "resolved", "rejected"].map((s) => (
                    <option key={s}>{s}</option>
                  ))}
                </select>
              </div>
            ))
          )}
        </section>
      )}
      {tab === "Search analytics" && (
        <section className="admin-section">
          <h2>What people are looking for</h2>
          <p className="muted">
            Counts are aggregated from actual database search logs.
          </p>
          {analytics.isError ? (
            <StateBox
              error={analytics.error}
              retry={() => analytics.refetch()}
            />
          ) : analytics.isPending ? (
            <StateBox />
          ) : !analytics.data.length ? (
            <StateBox empty="No searches have been logged yet." />
          ) : (
            analytics.data.map((a) => (
              <div className="analytics-row" key={a.query}>
                <span>{a.query}</span>
                <div
                  style={{
                    width:
                      Math.max(
                        1,
                        (a.count /
                          Math.max(...analytics.data.map((x) => x.count))) *
                          50,
                      ) + "%",
                  }}
                />
                <strong>{a.count}</strong>
              </div>
            ))
          )}
        </section>
      )}
      {tab === "Roles" && (
        <section className="admin-section">
          <p className="muted">
            Roles are enforced by the server on every request, including
            existing sessions.
          </p>
          {users.isError ? (
            <StateBox error={users.error} retry={() => users.refetch()} />
          ) : users.isPending ? (
            <StateBox />
          ) : (
            users.data.map((u) => (
              <div className="admin-list-row" key={u.id}>
                <div>
                  <h3>{u.full_name}</h3>
                  <small>Account #{u.id}</small>
                </div>
                <select
                  aria-label={`${u.full_name} role`}
                  value={u.role}
                  disabled={update.isPending}
                  onChange={(e) =>
                    update.mutate({
                      url: `/admin/users/${u.id}/roles`,
                      data: { role: e.target.value },
                    })
                  }
                >
                  {["student", "teacher", "admin"].map((r) => (
                    <option value={r} key={r}>
                      {roleLabel(r)}
                    </option>
                  ))}
                </select>
              </div>
            ))
          )}
        </section>
      )}
      <Dialog
        open={editing !== undefined}
        onOpenChange={(open) => {
          if (!open) setEditing(undefined);
        }}
        title={editing ? "Edit campus location" : "Add catalogue location"}
        description="Preserve known positions. Adding a record does not create a mapped route or verify its doorway."
      >
        <form onSubmit={saveLocation} className="admin-form">
          <label>
            Name
            <input name="name" required defaultValue={editing?.name} />
          </label>
          <div className="form-grid">
            <label>
              Category
              <input
                name="category"
                required
                defaultValue={editing?.category || "Service"}
              />
            </label>
            <label>
              Block
              <input
                name="block"
                required
                defaultValue={editing?.block || "Campus spine"}
              />
            </label>
            <label>
              Floor
              <input
                name="floor"
                required
                defaultValue={editing?.floor || "Floor unknown"}
              />
            </label>
            <label>
              Aliases
              <input name="aliases" defaultValue={editing?.aliases || ""} />
            </label>
          </div>
          <label>
            Opening hours
            <input
              name="opening_hours"
              required
              defaultValue={editing?.opening_hours || "Not confirmed"}
            />
          </label>
          <label>
            Contact
            <input
              name="contact"
              required
              defaultValue={editing?.contact || "Not confirmed"}
            />
          </label>
          <details>
            <summary>Schematic coordinates (0–1)</summary>
            <div className="form-grid">
              <label>
                X
                <input
                  type="number"
                  min="0"
                  max="1"
                  step="any"
                  name="x"
                  required
                  defaultValue={editing?.x || 0}
                />
              </label>
              <label>
                Y
                <input
                  type="number"
                  min="0"
                  max="1"
                  step="any"
                  name="y"
                  required
                  defaultValue={editing?.y || 0}
                />
              </label>
            </div>
          </details>
          {update.isError && <StateBox error={update.error} />}
          <Button type="submit" disabled={update.isPending}>
            Save location
          </Button>
        </form>
      </Dialog>
      <Dialog
        open={newsEdit !== undefined}
        onOpenChange={(open) => {
          if (!open) setNewsEdit(undefined);
        }}
        title={newsEdit ? "Edit update" : "Publish campus update"}
      >
        <form onSubmit={saveNews}>
          <label>
            Title
            <input name="title" required defaultValue={newsEdit?.title} />
          </label>
          <label>
            Message
            <textarea name="body" required defaultValue={newsEdit?.body} />
          </label>
          <label>
            Associated location
            <select
              name="location_id"
              defaultValue={newsEdit?.location_id || ""}
            >
              <option value="">No location</option>
              {places.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
          {update.isError && <StateBox error={update.error} />}
          <Button type="submit" disabled={update.isPending}>
            Save update
          </Button>
        </form>
      </Dialog>
    </div>
  );
}
