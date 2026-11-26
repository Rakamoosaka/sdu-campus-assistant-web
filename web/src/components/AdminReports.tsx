import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Ban,
  CheckCircle2,
  Clock,
  Construction,
  Info,
  Link2,
  MapPin,
  MessageSquareText,
  RotateCcw,
} from "lucide-react";
import { Button } from "./ui/button";
import { StateBox } from "../MapWorkspace";
import {
  api,
  localTime,
  reportStatusLabel,
  type PathClosure,
  type Place,
  type Report,
} from "../lib/api";

const OPEN = ["new", "reviewing"];

const reporter = (author: string) =>
  /^\d{9}$/.test(author) ? `SDU ID ${author}` : "Guest visitor";

function ago(date: string) {
  const ms =
    Date.now() -
    new Date(/Z$|[+-]\d\d:\d\d$/.test(date) ? date : date + "Z").getTime();
  const minutes = Math.round(ms / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.round(hours / 24);
  return `${days} day${days > 1 ? "s" : ""} ago`;
}

// Reports about the same place or path are listed next to each other; fixing
// the problem resolves all of them on the server.
const problemKey = (r: Report) =>
  r.kind === "path"
    ? `path:${[r.edge_a, r.edge_b].sort().join("|")}`
    : `place:${r.location_id}`;

export function AdminReports({
  reports,
  closures,
  places,
  onFix,
  onSaved,
}: {
  reports: Report[];
  closures: PathClosure[];
  places: Place[];
  onFix: (report: Report, place: Place) => void;
  onSaved: (message: string) => void;
}) {
  const qc = useQueryClient();
  const [view, setView] = useState("todo"),
    [replying, setReplying] = useState<number | null>(null),
    [reply, setReply] = useState(""),
    [timing, setTiming] = useState<number | null>(null),
    [reopenAt, setReopenAt] = useState("");
  const act = useMutation({
    mutationFn: async (calls: (() => Promise<unknown>)[]) => {
      for (const call of calls) await call();
    },
    onSuccess: () => {
      setReplying(null);
      setReply("");
      setTiming(null);
      setReopenAt("");
      qc.invalidateQueries();
    },
  });
  function run(message: string, calls: (() => Promise<unknown>)[]) {
    act.mutate(calls, { onSuccess: () => onSaved(message) });
  }

  const open = reports.filter((r) => OPEN.includes(r.status));
  const groups: Report[][] = [];
  for (const r of [...open].reverse()) {
    const group = groups.find((g) => problemKey(g[0]) === problemKey(r));
    if (group) group.push(r);
    else groups.push([r]);
  }
  const counts = {
    todo: open.length,
    resolved: reports.filter((r) => r.status === "resolved").length,
    rejected: reports.filter((r) => r.status === "rejected").length,
    withdrawn: reports.filter((r) => r.status === "withdrawn").length,
    all: reports.length,
  };
  const views: [keyof typeof counts, string][] = [
    ["todo", "To do"],
    ["resolved", "Resolved"],
    ["rejected", "Declined"],
    ["withdrawn", "Withdrawn"],
    ["all", "All"],
  ];

  return (
    <section className="admin-section reports-admin">
      <div className="reports-intro">
        <Info size={18} />
        <p>
          Students and visitors report wrong place details and blocked paths.
          Fix the problem here and every person who reported it is told
          automatically in their <strong>My reports</strong> page.
        </p>
      </div>
      <div className="reports-summary">
        <div className={counts.todo ? "attention" : ""}>
          <span>Waiting for you</span>
          <strong>{counts.todo}</strong>
          <small>
            {open.length} report{open.length === 1 ? "" : "s"} about{" "}
            {groups.length} problem{groups.length === 1 ? "" : "s"}
          </small>
        </div>
        <div>
          <span>Paths closed now</span>
          <strong>{closures.length}</strong>
          <small>Routes currently avoid them</small>
        </div>
        <div>
          <span>Resolved so far</span>
          <strong>{counts.resolved}</strong>
          <small>Reporters have been told</small>
        </div>
      </div>

      {closures.length > 0 && (
        <div className="closed-paths">
          <h2>Closed paths right now</h2>
          {closures.map((c) => (
            <div className="closed-path" key={c.id}>
              <Ban size={16} />
              <div>
                <strong>{c.label}</strong>
                <small>
                  {c.state === "closed"
                    ? "Closed: every route goes around it"
                    : "Not step-free: only step-free routes avoid it"}
                  {c.reopens_at
                    ? ` · reopens by itself ${localTime(c.reopens_at)}`
                    : " · stays closed until you reopen it"}
                </small>
              </div>
              <Button
                size="sm"
                variant="outline"
                disabled={act.isPending}
                onClick={() =>
                  run("Path reopened. Routes can use it again.", [
                    () => api.delete(`/admin/path-status/${c.id}`),
                  ])
                }
              >
                <RotateCcw size={14} /> Reopen now
              </Button>
            </div>
          ))}
        </div>
      )}

      <div className="filter-chips" role="group" aria-label="Filter reports">
        {views.map(([value, label]) => (
          <button
            key={value}
            aria-pressed={view === value}
            onClick={() => setView(value)}
          >
            {label} <span>{counts[value]}</span>
          </button>
        ))}
      </div>
      {act.isError && <StateBox error={act.error} />}

      {view === "todo" ? (
        !open.length ? (
          <div className="reports-empty">
            <CheckCircle2 size={28} />
            <strong>Nothing to do</strong>
            <span>New reports from students and visitors will appear here.</span>
          </div>
        ) : (
          groups.flatMap((group) =>
            group.map((r) => {
              const key = problemKey(r);
              const isPath = r.kind === "path";
              const place = places.find((p) => p.id === r.location_id);
              const others = group.filter((o) => o.id !== r.id);
              const alsoResolves = others.length
                ? ` Also resolves the ${others.length === 1 ? "other report" : `${others.length} other reports`} about this ${isPath ? "path" : "place"}.`
                : "";
              const answer = (status: string, note: string) => [
                () =>
                  api.put(`/admin/reports/${r.id}`, {
                    status,
                    resolution_note: note,
                  }),
              ];
              const closePath = (state: string) =>
                run(
                  (state === "closed"
                    ? "Path closed. Routes now go around it, and "
                    : "Path marked not step-free, and ") +
                    (group.length === 1
                      ? "the reporter was told."
                      : `all ${group.length} reporters were told.`),
                  [
                    () =>
                      api.post("/admin/path-status", {
                        edge_a: r.edge_a,
                        edge_b: r.edge_b,
                        state,
                        report_id: r.id,
                        reopens_at:
                          timing === r.id && reopenAt
                            ? reopenAt + ":00+05:00"
                            : null,
                      }),
                  ],
                );
              const reviewing = r.status === "reviewing";
              return (
                <article
                  className={"admin-report" + (others.length ? " related" : "")}
                  key={r.id}
                  data-problem={key}
                >
                  <header>
                    <span className={"kind-badge " + r.kind}>
                      {isPath ? <Construction size={14} /> : <MapPin size={14} />}
                      {isPath ? "Blocked path" : "Wrong place information"}
                    </span>
                    <span className={"report-status " + (reviewing ? "reviewing" : "new")}>
                      {reviewing ? "Under review" : "New"}
                    </span>
                  </header>
                  <h3>
                    {(isPath ? r.connection_label : r.location_name) || "Campus"}
                  </h3>
                  <p className="group-meta">
                    <Clock size={13} /> {reporter(r.author)} · {ago(r.created_at)}{" "}
                    · #{r.id}
                    {r.route && ` · on the route ${r.route}`}
                  </p>
                  <blockquote className="report-message">
                    <MessageSquareText size={15} />
                    <q>{r.message}</q>
                  </blockquote>
                  {!!others.length && (
                    <p className="report-related">
                      <Link2 size={13} /> Same {isPath ? "path" : "place"} also
                      reported in {others.map((o) => `#${o.id}`).join(", ")}
                    </p>
                  )}
                  <div className="report-decide">
                    <span className="decide-label">What do you want to do?</span>
                    {isPath ? (
                      <div className="decide-options">
                        <button
                          className="decide-option primary"
                          disabled={act.isPending}
                          onClick={() => closePath("closed")}
                        >
                          <strong>Close this path</strong>
                          <span>Every route goes around it.{alsoResolves}</span>
                        </button>
                        <button
                          className="decide-option"
                          disabled={act.isPending}
                          onClick={() => closePath("not_step_free")}
                        >
                          <strong>Mark not step-free</strong>
                          <span>
                            Only routes that avoid stairs go around it.
                            {alsoResolves}
                          </span>
                        </button>
                      </div>
                    ) : (
                      <div className="decide-options">
                        <button
                          className="decide-option primary"
                          disabled={act.isPending || !place}
                          onClick={() => place && onFix(r, place)}
                        >
                          <strong>Fix the details</strong>
                          <span>
                            Opens {r.location_name}. Saving resolves this
                            report.{alsoResolves}
                          </span>
                        </button>
                      </div>
                    )}
                    {isPath &&
                      (timing === r.id ? (
                        <label className="reopen-field">
                          Reopen automatically on (Asia/Almaty time)
                          <input
                            type="datetime-local"
                            value={reopenAt}
                            onChange={(e) => setReopenAt(e.target.value)}
                          />
                        </label>
                      ) : (
                        <button
                          className="link-button"
                          onClick={() => {
                            setTiming(r.id);
                            setReopenAt("");
                          }}
                        >
                          + Reopen it automatically at a set time
                        </button>
                      ))}
                    {replying === r.id ? (
                      <div className="reply-box">
                        <label>
                          Message to the reporter
                          <textarea
                            maxLength={1000}
                            value={reply}
                            placeholder="e.g. We checked, and the hours shown are correct."
                            onChange={(e) => setReply(e.target.value)}
                          />
                        </label>
                        <div className="row-actions start">
                          <Button
                            size="sm"
                            variant="destructive"
                            disabled={act.isPending || !reply.trim()}
                            onClick={() =>
                              run(
                                "Report declined, and the reporter was told why.",
                                answer("rejected", reply),
                              )
                            }
                          >
                            Decline with this message
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={act.isPending || !reply.trim()}
                            onClick={() =>
                              run(
                                "Message sent. The report stays open.",
                                answer("reviewing", reply),
                              )
                            }
                          >
                            Send and keep open
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => setReplying(null)}
                          >
                            Cancel
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <div className="secondary-actions">
                        {!reviewing && (
                          <button
                            className="link-button"
                            disabled={act.isPending}
                            onClick={() =>
                              run(
                                "Marked as under review. The reporter can see it.",
                                answer("reviewing", r.resolution_note),
                              )
                            }
                          >
                            Mark as under review
                          </button>
                        )}
                        <button
                          className="link-button"
                          onClick={() => {
                            setReplying(r.id);
                            setReply("");
                          }}
                        >
                          Reply or decline…
                        </button>
                      </div>
                    )}
                  </div>
                </article>
              );
            }),
          )
        )
      ) : (
        (() => {
          const shown = reports.filter(
            (r) => view === "all" || r.status === view,
          );
          if (!shown.length)
            return (
              <div className="reports-empty">
                <strong>No reports here</strong>
              </div>
            );
          return shown.map((r) => (
            <article className="admin-report done" key={r.id}>
              <header>
                <span className={"kind-badge " + r.kind}>
                  {r.kind === "path" ? <Construction size={14} /> : <MapPin size={14} />}
                  {r.kind === "path" ? "Blocked path" : "Wrong place information"}
                </span>
                <span className={"report-status " + r.status}>
                  {r.status === "rejected" ? "Declined" : reportStatusLabel(r.status)}
                </span>
              </header>
              <h3>
                {(r.kind === "path" ? r.connection_label : r.location_name) || "Campus"}
              </h3>
              <ul className="report-quotes">
                <li>
                  <MessageSquareText size={14} />
                  <div>
                    <q>{r.message}</q>
                    <small>
                      {reporter(r.author)} · {localTime(r.created_at)} · #{r.id}
                    </small>
                  </div>
                </li>
              </ul>
              {r.resolution_note && (
                <p className="report-note">
                  <strong>Your answer:</strong> {r.resolution_note}
                </p>
              )}
              {r.status === "withdrawn" && (
                <p className="muted text-xs">The reporter withdrew this report.</p>
              )}
              {r.path_status && (
                <p className="muted text-xs">
                  {r.path_status.state === "closed"
                    ? "This path is closed right now."
                    : "This path is marked not step-free right now."}{" "}
                  Reopen it from “Closed paths right now” above.
                </p>
              )}
            </article>
          ));
        })()
      )}
    </section>
  );
}
