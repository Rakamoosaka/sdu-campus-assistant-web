import { Check } from "lucide-react";

// Where a report stands: Received -> Under review -> Resolved (or Not changed).
export function ReportProgress({ status }: { status: string }) {
  if (status === "withdrawn") return null;
  const steps = [
    "Received",
    "Under review",
    status === "rejected" ? "Not changed" : "Resolved",
  ];
  const current =
    status === "resolved" || status === "rejected"
      ? 2
      : status === "reviewing"
        ? 1
        : 0;
  return (
    <ol
      className={"report-progress" + (status === "rejected" ? " declined" : "")}
      aria-label="Report progress"
    >
      {steps.map((label, i) => (
        <li
          key={label}
          className={i < current ? "done" : i === current ? "current" : ""}
          aria-current={i === current ? "step" : undefined}
        >
          <span className="report-progress-dot" aria-hidden>
            {i <= current && <Check size={11} strokeWidth={3} />}
          </span>
          {label}
        </li>
      ))}
    </ol>
  );
}
