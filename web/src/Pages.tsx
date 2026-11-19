import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowUpRight,
  Bookmark,
  CalendarDays,
  Check,
  ChevronRight,
  Clock,
  MapPin,
  Plus,
  Send,
  Sparkles,
  UserRound,
} from "lucide-react";
import { Button } from "./components/ui/button";
import { Dialog } from "./components/ui/dialog";
import { StateBox } from "./MapWorkspace";
import { features } from "./features";
import { AdminReports } from "./components/AdminReports";
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
  type PathResult,
  type PathClosure,
  STEP_FREE_STATES,
  almatyInputValue,
  reportStatusLabel,
} from "./lib/api";
interface Props {
  person: Person;
  places: Place[];
  openPlace: (id: number, route?: PathResult) => void;
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
  openPlace: (id: number, route?: PathResult) => void;
}) {
  return (
    <Button variant="outline" size="sm" onClick={() => openPlace(place.id)}>
      <MapPin size={14} /> {place.name}
      <ArrowUpRight size={14} />
    </Button>
  );
}
export function AssistantPage({ person, openPlace }: Props) {
  const [conversationId, setConversationId] = useState<string | undefined>();
  const status = useQuery({
    queryKey: ["assistant-status"],
    queryFn: () =>
      get<{ configured: boolean; model: string | null }>("/assistant/status"),
  });
  const [text, setText] = useState(""),
    [messages, setMessages] = useState<{ user?: string; reply?: Answer }[]>([]);
  const send = useMutation({
    mutationFn: (body: {
      question?: string;
      context_id?: string;
      selection_id?: number;
    }) =>
      api
        .post<Answer>(
          "/assistant/query",
          { ...body, conversation_id: conversationId },
          { timeout: 95000 },
        )
        .then((r) => r.data),
    onSuccess: (data) => {
      setConversationId(data.conversation_id);
      setMessages((m) => [...m, { reply: data }]);
    },
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
        Ask about rooms and campus services
        {features.timetable && " or your next class"}.
      </PageIntro>
      <div className="assistant-toolbar">
        <Button
          variant="ghost"
          size="sm"
          disabled={send.isPending}
          onClick={() => {
            setConversationId(undefined);
            setMessages([]);
            setText("");
            send.reset();
          }}
        >
          New chat
        </Button>
      </div>
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
            <div className="prompt-chips">
              {[
                "Where is D201?",
                "I feel sick",
                "Where can I print?",
                ...(features.timetable ? ["Where is my next class?"] : []),
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
                    <small className="answer-source">
                      {message.reply?.engine === "openrouter"
                        ? "DeepSeek · grounded campus tools"
                        : "Campus catalogue"}
                      {message.reply?.fallback_reason
                        ? " · AI unavailable; basic fallback used"
                        : ""}
                    </small>
                    {message.reply?.route && message.reply.location ? (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() =>
                          openPlace(
                            message.reply!.location!.id,
                            message.reply!.route,
                          )
                        }
                      >
                        Open route on map <ArrowUpRight size={14} />
                      </Button>
                    ) : (
                      message.reply?.location && (
                        <PlaceActions
                          place={message.reply.location}
                          openPlace={openPlace}
                        />
                      )
                    )}
                    {message.reply?.locations
                      ?.filter((p) => p.id !== message.reply?.location?.id)
                      .map((p) => (
                        <PlaceActions
                          key={p.id}
                          place={p}
                          openPlace={openPlace}
                        />
                      ))}
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
              <StateBox
                empty={
                  status.data?.configured
                    ? "Checking campus data with DeepSeek…"
                    : "Checking the campus catalogue…"
                }
              />
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
            {status.data?.configured
              ? `DeepSeek interprets your question using your stored profile, saved places, preferences, ${features.timetable ? "sample timetable, " : ""}reports and campus tools. Basic assistance remains available if AI is unavailable.`
              : "This assistant finds catalogue matches and helps you choose when a request is ambiguous. No AI key is configured on this server."}
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
  openPlace: (id: number, route?: PathResult) => void;
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
        Sign in for saved places
        {features.timetable && ", personal schedules"} and account preferences.
      </p>
      <Button onClick={onLogin}>
        Log in or create an account
        <ArrowUpRight size={16} />
      </Button>
    </div>
  );
}
export function AnnouncementsPage({ openPlace }: Props) {
  const news = useQuery({
    queryKey: ["news"],
    queryFn: () => get<News[]>("/announcements"),
  });
  return (
    <div className="content-page">
      <PageIntro label="AROUND THE CAMPUS" title="Stay in the loop.">
        News, events and service changes on campus. Seeded presentation content
        is sample data.
      </PageIntro>
      {news.isPending ? (
        <StateBox />
      ) : news.isError ? (
        <StateBox error={news.error} retry={() => news.refetch()} />
      ) : !news.data.length ? (
        <StateBox empty="There are no announcements right now." />
      ) : (
        <div className="news-grid">
          {news.data.map((n, i) => (
            <article
              className={"news-card " + (i === 0 ? "featured" : "")}
              key={n.id}
            >
              <div className="news-meta">
                <span>{i === 0 ? "LATEST" : "ANNOUNCEMENT"}</span>
                <span>{localTime(n.starts_at || n.published_at)}</span>
              </div>
              <h2>{n.title}</h2>
              <p>{n.body}</p>
              {n.ends_at && (
                <p className="muted text-xs">Until {localTime(n.ends_at)}</p>
              )}
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
        description="All entered dates and times are in Asia/Almaty (UTC+5). This is your editable timetable."
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
export function MyReportsPage({ person }: Props) {
  const qc = useQueryClient();
  const [fresh, setFresh] = useState<number[] | null>(null),
    [confirmWithdraw, setConfirmWithdraw] = useState<number | null>(null);
  const myReports = useQuery({
    queryKey: ["my-reports"],
    queryFn: () => get<Report[]>("/reports/me"),
  });
  useEffect(() => {
    // Remember which reports were new on arrival, then clear the sidebar badge.
    if (!myReports.data || fresh !== null) return;
    const unread = myReports.data.filter((r) => r.reporter_unread);
    setFresh(unread.map((r) => r.id));
    if (unread.length)
      api.post("/reports/me/seen").then(() =>
        qc.setQueryData<Report[]>(["my-reports"], (rows) =>
          rows?.map((r) => ({ ...r, reporter_unread: false })),
        ),
      );
  }, [myReports.data]);
  const withdraw = useMutation({
    mutationFn: (id: number) => api.post(`/reports/${id}/withdraw`),
    onSuccess: () => {
      setConfirmWithdraw(null);
      qc.invalidateQueries({ queryKey: ["my-reports"] });
      qc.invalidateQueries({ queryKey: ["path-states"] });
    },
  });
  return (
    <div className="content-page">
      <PageIntro label="YOUR REPORTS" title="Problems you reported.">
        Follow what the campus team did about each report. To report something
        new, open a place on the map and choose Report a problem.
      </PageIntro>
      <section className="report-list" aria-label="Your reports">
        {withdraw.isError && <StateBox error={withdraw.error} />}
        {myReports.isError ? (
          <StateBox
            error={myReports.error}
            retry={() => myReports.refetch()}
          />
        ) : myReports.isPending ? (
          <StateBox />
        ) : !myReports.data.length ? (
          <StateBox empty="No reports yet. Open any place on the map and choose Report a problem." />
        ) : (
          myReports.data.map((r) => (
            <article
              className={"report-card " + (fresh?.includes(r.id) ? "fresh" : "")}
              key={r.id}
            >
              <header>
                <strong>
                  #{r.id} ·{" "}
                  {r.kind === "path" ? "Blocked path" : "Location information"}
                  {fresh?.includes(r.id) && (
                    <span className="new-tag">New update</span>
                  )}
                </strong>
                <span className={"report-status " + r.status}>
                  {reportStatusLabel(r.status)}
                </span>
              </header>
              <small className="muted">
                {(r.kind === "path" ? r.connection_label : r.location_name) ||
                  "Campus"}{" "}
                · Sent {localTime(r.created_at)}
                {r.updated_at && ` · Updated ${localTime(r.updated_at)}`}
              </small>
              <p>{r.message}</p>
              {r.path_status && (
                <p className="muted">
                  {r.path_status.state === "closed"
                    ? "Routes currently go around this path"
                    : "Step-free routes currently avoid this path"}
                  {r.path_status.reopens_at
                    ? ` until ${localTime(r.path_status.reopens_at)}.`
                    : "."}
                </p>
              )}
              {r.resolution_note && (
                <p className="report-note">
                  <strong>Campus team:</strong> {r.resolution_note}
                </p>
              )}
              {["new", "reviewing"].includes(r.status) &&
                (confirmWithdraw === r.id ? (
                  <div className="row-actions start">
                    <Button
                      size="sm"
                      variant="destructive"
                      disabled={withdraw.isPending}
                      onClick={() => withdraw.mutate(r.id)}
                    >
                      Withdraw report
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setConfirmWithdraw(null)}
                    >
                      Keep it
                    </Button>
                  </div>
                ) : (
                  <div className="row-actions start">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setConfirmWithdraw(r.id)}
                    >
                      Withdraw
                    </Button>
                  </div>
                ))}
            </article>
          ))
        )}
        {person.role === "guest" && (
          <p className="muted text-xs">
            You're using guest mode. Sign in on this device and these reports
            move to your account, so you can keep following them.
          </p>
        )}
      </section>
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
    [editing, setEditing] = useState<Place | null>(null),
    [newsEdit, setNewsEdit] = useState<News | null | undefined>(undefined),
    [message, setMessage] = useState(""),
    [filter, setFilter] = useState(""),
    [confirmDelete, setConfirmDelete] = useState<number | null>(null),
    [fixing, setFixing] = useState<Report | null>(null);
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
  const closures = useQuery({
    queryKey: ["path-status"],
    queryFn: () => get<PathClosure[]>("/admin/path-status"),
  });
  const users = useQuery({
    queryKey: ["users"],
    queryFn: () => get<Person[]>("/admin/users"),
  });
  const news = useQuery({
    queryKey: ["admin-news"],
    queryFn: () => get<News[]>("/admin/announcements"),
    enabled: features.announcements,
  });
  const update = useMutation({
    mutationFn: ({
      url,
      data,
      method = "put",
    }: {
      url: string;
      data?: unknown;
      method?: "put" | "post" | "delete";
    }) => (method === "delete" ? api.delete(url) : api[method](url, data)),
    onSuccess: () => {
      setEditing(null);
      setFixing(null);
      setNewsEdit(undefined);
      setConfirmDelete(null);
      setMessage(
        fixing
          ? "Details saved. The report is resolved and the reporter was told."
          : "Changes saved to the database.",
      );
      qc.invalidateQueries();
    },
    onError: () => setMessage(""),
  });
  function saveLocation(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!editing) return;
    update.mutate({
      url: `/admin/locations/${editing.id}`,
      data: {
        ...Object.fromEntries(new FormData(e.currentTarget)),
        report_id: fixing?.id ?? null,
      },
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
        starts_at: values.starts_at ? values.starts_at + ":00+05:00" : null,
        ends_at: values.ends_at ? values.ends_at + ":00+05:00" : null,
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
        {[
          "Locations",
          ...(features.announcements ? ["Announcements"] : []),
          "Reports",
          "Search analytics",
          "Roles",
        ].map(
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
          </div>
          <p className="muted">
            Edit the details people see for each place. Places, their
            categories, map positions and route connections come from the
            campus map file and can't be changed here.
          </p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Location</th>
                  <th>Category</th>
                  <th>Position</th>
                  <th>Hours</th>
                  <th>Step-free</th>
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
                      <td>{p.step_free_access || "Not verified"}</td>
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
      {tab === "Announcements" && (
        <section className="admin-section">
          <Button
            onClick={() => {
              setNewsEdit(null);
              update.reset();
            }}
          >
            <Plus size={16} /> New announcement
          </Button>
          {news.isError ? (
            <StateBox error={news.error} retry={() => news.refetch()} />
          ) : news.isPending ? (
            <StateBox />
          ) : !news.data.length ? (
            <StateBox empty="No announcements yet." />
          ) : (
            news.data.map((n) => (
              <div className="admin-list-row" key={n.id}>
                <div>
                  <span className={"window-state " + n.state}>
                    {n.state === "scheduled"
                      ? "Scheduled"
                      : n.state === "expired"
                        ? "Ended"
                        : "Showing"}
                  </span>
                  <h3>{n.title}</h3>
                  <p>{n.body}</p>
                  <small>
                    {n.starts_at
                      ? `From ${localTime(n.starts_at)}`
                      : `Published ${localTime(n.published_at)}`}
                    {n.ends_at
                      ? ` · until ${localTime(n.ends_at)}`
                      : " · no end date"}
                    {n.location_id &&
                      ` · ${places.find((p) => p.id === n.location_id)?.name || "Linked place"}`}
                  </small>
                </div>
                <div className="row-actions">
                  <Button
                    variant="outline"
                    onClick={() => {
                      setNewsEdit(n);
                      setConfirmDelete(null);
                      update.reset();
                    }}
                  >
                    Edit
                  </Button>
                  {confirmDelete === n.id ? (
                    <>
                      <Button
                        variant="destructive"
                        disabled={update.isPending}
                        onClick={() =>
                          update.mutate({
                            url: `/admin/announcements/${n.id}`,
                            method: "delete",
                          })
                        }
                      >
                        Delete permanently
                      </Button>
                      <Button
                        variant="ghost"
                        onClick={() => setConfirmDelete(null)}
                      >
                        Cancel
                      </Button>
                    </>
                  ) : (
                    <Button
                      variant="ghost"
                      onClick={() => setConfirmDelete(n.id)}
                    >
                      Delete
                    </Button>
                  )}
                </div>
              </div>
            ))
          )}
        </section>
      )}
      {tab === "Reports" &&
        (reports.isError || closures.isError ? (
          <StateBox
            error={reports.error || closures.error}
            retry={() => {
              reports.refetch();
              closures.refetch();
            }}
          />
        ) : reports.isPending || closures.isPending ? (
          <StateBox />
        ) : (
          <AdminReports
            reports={reports.data}
            closures={closures.data}
            places={places}
            onFix={(report, place) => {
              setFixing(report);
              setEditing(place);
              setMessage("");
              update.reset();
            }}
            onSaved={setMessage}
          />
        ))}
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
        open={editing !== null}
        onOpenChange={(open) => {
          if (!open) {
            setEditing(null);
            setFixing(null);
          }
        }}
        title={fixing ? `Fix the details of ${editing?.name}` : "Edit location details"}
        description={
          editing
            ? `${editing.category} · ${editing.floor}. Category, map position and route connections come from the campus map file.`
            : undefined
        }
      >
        {editing && (
          <form
            key={editing.id}
            onSubmit={saveLocation}
            className="admin-form"
          >
            {fixing && (
              <p className="report-note">
                <strong>Reported (#{fixing.id}):</strong> {fixing.message}
              </p>
            )}
            <label>
              Name
              <input name="name" required defaultValue={editing.name} />
            </label>
            <div className="form-grid">
              <label>
                Block
                <input name="block" required defaultValue={editing.block} />
              </label>
              <label>
                Floor label
                <input name="floor" required defaultValue={editing.floor} />
              </label>
              <label>
                Step-free access
                <select
                  name="step_free_access"
                  defaultValue={editing.step_free_access || "Not verified"}
                >
                  {STEP_FREE_STATES.map((state) => (
                    <option key={state}>{state}</option>
                  ))}
                </select>
              </label>
              <label>
                Search aliases
                <input
                  name="aliases"
                  placeholder="Comma-separated, e.g. books, reading room"
                  defaultValue={editing.aliases
                    .split(",")
                    .filter((alias) => !alias.startsWith("["))
                    .join(", ")}
                />
              </label>
            </div>
            <label>
              Opening hours
              <input
                name="opening_hours"
                required
                defaultValue={editing.opening_hours}
              />
            </label>
            <label>
              Contact
              <input name="contact" required defaultValue={editing.contact} />
            </label>
            {fixing && (
              <>
                <label>
                  Message to the reporter
                  <textarea
                    name="resolution_note"
                    maxLength={1000}
                    defaultValue={`We updated the details for ${editing.name}. Thanks for reporting it!`}
                  />
                </label>
              </>
            )}
            {update.isError && <StateBox error={update.error} />}
            <Button type="submit" disabled={update.isPending}>
              {fixing ? "Save and resolve report" : "Save details"}
            </Button>
          </form>
        )}
      </Dialog>
      <Dialog
        open={newsEdit !== undefined}
        onOpenChange={(open) => {
          if (!open) setNewsEdit(undefined);
        }}
        title={newsEdit ? "Edit announcement" : "New announcement"}
        description="Times are in Asia/Almaty (UTC+5). Leave both empty to show it now, with no end date."
      >
        <form key={newsEdit?.id ?? "new"} onSubmit={saveNews}>
          <label>
            Title
            <input name="title" required defaultValue={newsEdit?.title} />
          </label>
          <label>
            Message
            <textarea name="body" required defaultValue={newsEdit?.body} />
          </label>
          <div className="form-grid">
            <label>
              Show from
              <input
                name="starts_at"
                type="datetime-local"
                defaultValue={almatyInputValue(newsEdit?.starts_at ?? null)}
              />
            </label>
            <label>
              Show until
              <input
                name="ends_at"
                type="datetime-local"
                defaultValue={almatyInputValue(newsEdit?.ends_at ?? null)}
              />
            </label>
          </div>
          <label>
            Place it's about
            <select
              name="location_id"
              defaultValue={newsEdit?.location_id || ""}
            >
              <option value="">No specific place</option>
              {places.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
          {update.isError && <StateBox error={update.error} />}
          <Button type="submit" disabled={update.isPending}>
            {newsEdit ? "Save announcement" : "Publish announcement"}
          </Button>
        </form>
      </Dialog>
    </div>
  );
}
