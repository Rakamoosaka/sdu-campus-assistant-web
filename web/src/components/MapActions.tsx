import { useRef, useState } from "react";
import { Download, Share2 } from "lucide-react";
import { Dialog } from "./ui/dialog";
import { Button } from "./ui/button";
import { errorMessage, type Place } from "../lib/api";
import {
  downloadMap,
  offlineSupported,
  removeSavedMap,
  type SavedMap,
} from "../lib/offlineMap";

export function ShareDestination({
  place,
  compact = false,
}: {
  place: Place;
  compact?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState("");
  const trigger = useRef<HTMLButtonElement>(null);
  const url = new URL("/map", window.location.origin);
  url.searchParams.set("place", String(place.id));
  const shareData = { title: place.name, url: url.href };

  async function share() {
    setStatus("");
    if (
      navigator.share &&
      (!navigator.canShare || navigator.canShare(shareData))
    ) {
      try {
        await navigator.share(shareData);
        return;
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError")
          return;
      }
    }
    setOpen(true);
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(url.href);
      setStatus("Link copied");
    } catch {
      setStatus("Copy the link manually from the field above.");
    }
  }

  return (
    <>
      <Button
        ref={trigger}
        variant="outline"
        onClick={share}
        aria-label={compact ? "Share destination" : undefined}
      >
        <Share2 size={16} /> {compact ? "Share" : "Share destination"}
      </Button>
      <Dialog
        open={open}
        onOpenChange={setOpen}
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          trigger.current?.focus();
        }}
        title={`Share ${place.name}`}
        description="Anyone who can reach this app can open this destination."
      >
        <label className="map-link-field">
          Destination link
          <input
            readOnly
            value={url.href}
            onFocus={(event) => event.target.select()}
          />
        </label>
        <Button className="mt-4" onClick={copy}>
          Copy link
        </Button>
        <p className="muted mt-2" role="status">
          {status}
        </p>
      </Dialog>
    </>
  );
}

export function OfflineMapControl({
  saved,
  offline,
  onChange,
}: {
  saved: SavedMap | null;
  offline: boolean;
  onChange: (saved: SavedMap | null) => void;
}) {
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const [confirmRemoval, setConfirmRemoval] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const controller = useRef<AbortController | null>(null);
  const trigger = useRef<HTMLButtonElement>(null);

  async function download() {
    if (controller.current) return;
    const task = new AbortController();
    controller.current = task;
    setPending(true);
    setError("");
    setStatus("");
    try {
      onChange(await downloadMap(task.signal));
      setStatus("Ready offline");
    } catch (error) {
      if (!task.signal.aborted) {
        setError(
          error instanceof DOMException && error.name === "QuotaExceededError"
            ? "This browser is out of storage. Free some space and try again."
            : errorMessage(error),
        );
      }
    } finally {
      controller.current = null;
      setPending(false);
    }
  }

  async function remove() {
    setPending(true);
    setError("");
    try {
      await removeSavedMap();
      onChange(null);
      setConfirmRemoval(false);
      setStatus("Download removed");
      setOpen(false);
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setPending(false);
    }
  }

  return (
    <>
      <Button
        ref={trigger}
        size="sm"
        variant="outline"
        onClick={() => {
          setError("");
          setStatus("");
          setConfirmRemoval(false);
          setOpen(true);
        }}
      >
        <Download size={16} /> Offline map
      </Button>
      <Dialog
        open={open}
        onOpenChange={(next) => {
          if (!pending) setOpen(next);
        }}
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          trigger.current?.focus();
        }}
        title="Offline map"
        description="Save the floor plans, markers, and public place details to search and browse without a connection."
      >
        {saved && (
          <p className="mb-4">
            <strong>Ready offline</strong>
            <span className="muted">
              {" "}
              · Saved {new Date(saved.savedAt).toLocaleDateString()}
            </span>
          </p>
        )}
        {!offlineSupported ? (
          <p>
            Offline maps need a supported browser and the built campus app on
            HTTPS or localhost.
          </p>
        ) : confirmRemoval ? (
          <>
            <p className="mb-4">
              Remove the saved campus map from this browser?
            </p>
            <div className="flex flex-wrap gap-2">
              <Button disabled={pending} onClick={remove}>
                Remove download
              </Button>
              <Button
                variant="outline"
                disabled={pending}
                onClick={() => setConfirmRemoval(false)}
              >
                Keep download
              </Button>
            </div>
          </>
        ) : (
          <div className="flex flex-wrap gap-2">
            <Button disabled={offline || pending} onClick={download}>
              {pending
                ? "Downloading…"
                : error
                  ? "Retry"
                  : saved
                    ? "Update download"
                    : "Download campus map"}
            </Button>
            {pending && (
              <Button
                variant="outline"
                onClick={() => controller.current?.abort()}
              >
                Cancel download
              </Button>
            )}
            {saved && !pending && (
              <Button variant="outline" onClick={() => setConfirmRemoval(true)}>
                Remove download
              </Button>
            )}
          </div>
        )}
        {offline && (
          <p className="muted mt-3">Reconnect to download or update the map.</p>
        )}
        {error && (
          <p className="error-box mt-3" role="alert">
            {error}
          </p>
        )}
        <p className="muted mt-3" role="status">
          {status}
        </p>
      </Dialog>
    </>
  );
}
