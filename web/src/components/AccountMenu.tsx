import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Accessibility, LogIn, LogOut, X } from "lucide-react";
import { Button } from "./ui/button";
import { api, get, errorMessage, type Person } from "../lib/api";
import { features } from "../features";

export function AccountMenu({
  person,
  name,
  role,
  initials,
  onClose,
  onLogin,
  onLogout,
}: {
  person: Person;
  name: string;
  role: string;
  initials: string;
  onClose: () => void;
  onLogin: () => void;
  onLogout: () => void;
}) {
  const qc = useQueryClient();
  const guest = person.role === "guest";
  const [draft, setDraft] = useState<boolean | null>(null);
  const pref = useQuery({
    queryKey: ["preferences"],
    queryFn: () => get<{ accessible_routes: boolean }>("/users/me/preferences"),
  });
  const save = useMutation({
    mutationFn: (value: boolean) =>
      api.put("/users/me/preferences", { accessible_routes: value }),
    onSettled: async () => {
      await qc.invalidateQueries({ queryKey: ["preferences"] });
      setDraft(null);
    },
  });
  useEffect(() => {
    const close = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [onClose]);
  return (
    <>
      <button
        className="account-backdrop"
        aria-label="Close account menu"
        onClick={onClose}
      />
      <section className="account-menu" role="dialog" aria-label="Your account">
        <header>
          <i className="avatar">{initials}</i>
          <span>
            <strong>{name}</strong>
            <small>
              {role}
              {person.sdu_id && ` · ${person.sdu_id}`}
            </small>
          </span>
          <button aria-label="Close" onClick={onClose}>
            <X size={16} />
          </button>
        </header>
        <label className="account-switch">
          <Accessibility size={18} />
          <span>
            <strong>Avoid stairs</strong>
            <small>
              Routes use corridors and lifts only. Saved to your{" "}
              {guest ? "guest session" : "account"}.
            </small>
          </span>
          <input
            type="checkbox"
            role="switch"
            checked={draft ?? pref.data?.accessible_routes ?? false}
            disabled={pref.isPending || pref.isError || save.isPending}
            onChange={(e) => {
              setDraft(e.target.checked);
              save.mutate(e.target.checked);
            }}
          />
        </label>
        {(pref.isError || save.isError) && (
          <p className="error-box" role="alert">
            {errorMessage(pref.error || save.error)}
          </p>
        )}
        {guest ? (
          <>
            <p className="muted text-xs">
              Sign in for saved places
              {features.timetable && ", your timetable"} and an account that
              keeps your reports.
            </p>
            <Button onClick={onLogin}>
              <LogIn size={16} /> Log in or create an account
            </Button>
            <Button variant="ghost" onClick={onLogout}>
              Leave guest mode
            </Button>
          </>
        ) : (
          <Button variant="outline" onClick={onLogout}>
            <LogOut size={16} /> Log out
          </Button>
        )}
      </section>
    </>
  );
}
