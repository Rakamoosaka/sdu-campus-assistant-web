import type { CampusMap, MapPlace, PathPart, PathState } from "../lib/api";
import floor1 from "../../../assets/maps/floor-1-background.svg?url";
import floor2 from "../../../assets/maps/floor-2-background.svg?url";

const same = (x: { a: string; b: string }, y: { a: string; b: string }) =>
  (x.a === y.a && x.b === y.b) || (x.a === y.b && x.b === y.a);

export function PathPicker({
  routeParts,
  nearbyParts,
  states,
  map,
  place,
  value,
  onChange,
}: {
  routeParts: PathPart[];
  nearbyParts: PathPart[];
  states: PathState[];
  map: CampusMap;
  place?: MapPlace;
  value: string;
  onChange: (value: string) => void;
}) {
  const all = [...routeParts, ...nearbyParts];
  const selected = all.find((p) => `${p.a}|${p.b}` === value);
  const stateOf = (p: PathPart) => states.find((s) => same(s, p));
  const note = (p: PathPart) => {
    const s = stateOf(p);
    if (s?.state === "closed") return " · already closed";
    if (s?.open_reports) return " · already reported";
    if (s?.state === "not_step_free") return " · marked not step-free";
    return "";
  };
  const option = (p: PathPart) => (
    <option
      key={p.a + p.b}
      value={`${p.a}|${p.b}`}
      disabled={stateOf(p)?.state === "closed"}
    >
      {p.label}
      {note(p)}
    </option>
  );
  const floor = selected?.floor ?? place?.map_floor ?? all[0]?.floor ?? 1;
  const drawn = all.filter((p) => p.floor === floor && p.to_floor === floor);
  const nodes = map.routing.nodes;
  const marker =
    place?.has_position && place.map_floor === floor
      ? [place.x * map.width, place.y * map.height]
      : null;
  const points = [
    ...drawn.flatMap((p) => [nodes[p.a], nodes[p.b]]),
    ...(marker ? [marker] : []),
  ];
  const xs = points.map((p) => p[0]),
    ys = points.map((p) => p[1]);
  const box = points.length
    ? {
        x: Math.min(...xs) - 70,
        y: Math.min(...ys) - 50,
        w: Math.max(...xs) - Math.min(...xs) + 140,
        h: Math.max(...ys) - Math.min(...ys) + 100,
      }
    : null;
  const chosen = selected && stateOf(selected);
  return (
    <div className="path-picker">
      <label>
        Where exactly?
        <select
          required
          value={value}
          onChange={(e) => onChange(e.target.value)}
        >
          <option value="">Choose the closest match…</option>
          {!!routeParts.length && (
            <optgroup label="On your planned route">
              {routeParts.map(option)}
            </optgroup>
          )}
          {!!nearbyParts.length && (
            <optgroup label={`Around ${place?.name || "this place"}`}>
              {nearbyParts.map(option)}
            </optgroup>
          )}
        </select>
      </label>
      {box && (
        <svg
          className="path-preview"
          viewBox={`${box.x} ${box.y} ${box.w} ${box.h}`}
          role="group"
          aria-label={`Map of the paths around ${place?.name || "this place"}, floor ${floor}`}
        >
          {floor !== 3 && (
            <image
              href={floor === 1 ? floor1 : floor2}
              width={map.width}
              height={map.height}
              opacity={0.7}
            />
          )}
          {drawn.map((p) => {
            const a = nodes[p.a],
              b = nodes[p.b];
            const active = p === selected;
            const closed = stateOf(p)?.state === "closed";
            return (
              <g
                key={p.a + p.b}
                className={closed ? "closed" : ""}
                onClick={() => !closed && onChange(`${p.a}|${p.b}`)}
              >
                <title>
                  {p.label}
                  {note(p)}
                </title>
                <line
                  x1={a[0]}
                  y1={a[1]}
                  x2={b[0]}
                  y2={b[1]}
                  stroke="transparent"
                  strokeWidth={22}
                />
                <line
                  x1={a[0]}
                  y1={a[1]}
                  x2={b[0]}
                  y2={b[1]}
                  stroke={active ? "#dc2626" : closed ? "#9aa5b5" : "#2563eb"}
                  strokeWidth={active ? 9 : 5}
                  strokeDasharray={closed ? "6 6" : undefined}
                  strokeLinecap="round"
                />
              </g>
            );
          })}
          {marker && (
            <circle
              cx={marker[0]}
              cy={marker[1]}
              r={9}
              fill="#2662df"
              stroke="#fff"
              strokeWidth={3}
            />
          )}
        </svg>
      )}
      <small className="field-hint">
        {box
          ? "Tap a blue line on the small map or choose from the list. The red line is your choice; the dot is the place you opened."
          : "Choose from the list."}{" "}
        {selected &&
          selected.floor !== selected.to_floor &&
          `${selected.label} connects floors ${selected.floor} and ${selected.to_floor}.`}
      </small>
      {chosen?.open_reports ? (
        <p className="field-hint notice">
          Someone already reported this. Sending yours still helps: you'll get
          the campus team's answer too.
        </p>
      ) : chosen?.state === "not_step_free" ? (
        <p className="field-hint notice">
          This path is already marked as not step-free. Report it if it's now
          fully blocked.
        </p>
      ) : (
        <p className="field-hint">
          If the campus team confirms it, routes will go around this spot until
          it reopens.
        </p>
      )}
    </div>
  );
}
