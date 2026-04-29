import { Check, Minus, X } from "lucide-react";
import { Fragment } from "react";

import type { ATSReport } from "@/lib/api";
import { cn } from "@/lib/cn";

function scoreColor(s: number): string {
  if (s >= 0.7) return "text-success";
  if (s >= 0.4) return "text-warning";
  return "text-danger";
}

function pct(n: number): string {
  return `${Math.round(n * 100)}%`;
}

function Glyph({
  state,
}: {
  state: "ok" | "warn" | "fail";
}) {
  if (state === "ok")
    return <Check className="h-3.5 w-3.5 text-success" />;
  if (state === "warn")
    return <Minus className="h-3.5 w-3.5 text-warning" />;
  return <X className="h-3.5 w-3.5 text-danger" />;
}

/**
 * The full multi-dim ATSReport (#81) rendered as a compact dashboard:
 * composite score → structural checks → hard/soft skill tables → tone
 * flags → keyword gaps. Mirrors the CLI's `_display_ats_report` output
 * but in a denser two-column layout.
 */
export function AtsReport({ report }: { report: ATSReport }) {
  const composite = report.score;
  const titleState =
    report.job_title.exact_match
      ? "ok"
      : report.job_title.partial_match
        ? "warn"
        : "fail";
  return (
    <div className="space-y-4">
      <section className="panel p-4">
        <div className="flex items-baseline justify-between">
          <h2 className="text-xs uppercase tracking-wider text-fg-muted">
            Composite
          </h2>
          <div className="flex items-baseline gap-2">
            <span className={cn("text-3xl font-bold", scoreColor(composite))}>
              {pct(composite)}
            </span>
          </div>
        </div>
        {report.reasoning && (
          <p className="mt-2 text-xs text-fg-dim leading-relaxed">
            {report.reasoning}
          </p>
        )}
      </section>

      <section className="panel">
        <SectionHeading>Structural</SectionHeading>
        <table className="w-full text-sm">
          <tbody>
            <Row
              state={
                report.contact.email_present &&
                report.contact.phone_present &&
                report.contact.address_present
                  ? "ok"
                  : "warn"
              }
              label="Contact info"
              detail={contactDetail(report.contact)}
            />
            <Row
              state={
                report.sections.summary &&
                report.sections.experience &&
                report.sections.education &&
                report.sections.skills
                  ? "ok"
                  : "warn"
              }
              label="Sections"
              detail={sectionsDetail(report.sections)}
            />
            <Row
              state={titleState}
              label="Job title match"
              detail={titleDetail(report.job_title)}
            />
            <Row
              state={report.measurable_results_count >= 5 ? "ok" : "warn"}
              label="Measurable results"
              detail={`${report.measurable_results_count} quantified lines`}
            />
            <Row
              state={report.word_count_ok ? "ok" : "warn"}
              label="Word count"
              detail={`${report.word_count} words (target 400-1000)`}
            />
          </tbody>
        </table>
      </section>

      {(report.hard_skills.length > 0 || report.soft_skills.length > 0) && (
        <section className="grid grid-cols-2 gap-4">
          <SkillTable title="Hard skills" rows={report.hard_skills} />
          <SkillTable title="Soft skills" rows={report.soft_skills} />
        </section>
      )}

      {report.tone_flags.length > 0 && (
        <section className="panel">
          <SectionHeading>Tone flags</SectionHeading>
          <ul className="divide-y divide-border-subtle">
            {report.tone_flags.map((flag, i) => (
              <li key={i} className="px-3 py-2 text-sm">
                <p className="text-fg">
                  &ldquo;
                  <span className="text-warning">{flag.phrase}</span>&rdquo;
                </p>
                <p className="mt-1 text-xs text-fg-dim leading-relaxed">
                  {flag.suggestion}
                </p>
              </li>
            ))}
          </ul>
        </section>
      )}

      {report.keyword_gaps.length > 0 && (
        <section className="panel">
          <SectionHeading>Keyword gaps</SectionHeading>
          <ul className="flex flex-wrap gap-1.5 px-3 pb-3">
            {Array.from(new Set(report.keyword_gaps)).map((gap) => (
              <li
                key={gap}
                className="rounded-sm border border-border bg-bg-raised px-1.5 py-0.5 text-xs text-fg-muted"
              >
                {gap}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="border-b border-border-subtle px-3 py-2 text-xs uppercase tracking-wider text-fg-muted">
      {children}
    </h3>
  );
}

function Row({
  state,
  label,
  detail,
}: {
  state: "ok" | "warn" | "fail";
  label: string;
  detail: string;
}) {
  return (
    <tr className="border-b border-border-subtle last:border-b-0">
      <td className="w-6 pl-3 py-1.5 align-middle">
        <Glyph state={state} />
      </td>
      <td className="py-1.5 pr-3 align-middle text-fg">{label}</td>
      <td className="py-1.5 pr-3 align-middle text-right text-xs text-fg-dim">
        {detail}
      </td>
    </tr>
  );
}

function SkillTable({
  title,
  rows,
}: {
  title: string;
  rows: { name: string; resume_count: number; jd_count: number }[];
}) {
  if (rows.length === 0) return null;
  return (
    <div className="panel">
      <SectionHeading>{title}</SectionHeading>
      <div className="max-h-72 overflow-auto">
        <table className="w-full text-sm">
          <thead className="text-xs text-fg-faint">
            <tr>
              <th className="px-3 py-1 text-left font-normal">Skill</th>
              <th className="px-3 py-1 text-right font-normal">Resume</th>
              <th className="px-3 py-1 text-right font-normal">JD</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <Fragment key={i}>
                <tr className="border-t border-border-subtle">
                  <td className="px-3 py-1 text-fg">{r.name}</td>
                  <td
                    className={cn(
                      "px-3 py-1 text-right tabular-nums",
                      r.resume_count > 0 ? "text-fg" : "text-fg-faint",
                    )}
                  >
                    {r.resume_count}
                  </td>
                  <td
                    className={cn(
                      "px-3 py-1 text-right tabular-nums",
                      r.jd_count > 0 ? "text-fg" : "text-fg-faint",
                    )}
                  >
                    {r.jd_count}
                  </td>
                </tr>
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function contactDetail(c: {
  email_present: boolean;
  phone_present: boolean;
  address_present: boolean;
}): string {
  const missing: string[] = [];
  if (!c.email_present) missing.push("email");
  if (!c.phone_present) missing.push("phone");
  if (!c.address_present) missing.push("address");
  return missing.length === 0 ? "all present" : `missing: ${missing.join(", ")}`;
}

function sectionsDetail(s: {
  summary: boolean;
  experience: boolean;
  education: boolean;
  skills: boolean;
}): string {
  const missing = (Object.keys(s) as (keyof typeof s)[]).filter((k) => !s[k]);
  return missing.length === 0
    ? "all present"
    : `missing: ${missing.join(", ")}`;
}

function titleDetail(t: {
  exact_match: boolean;
  partial_match: boolean;
  jd_title: string;
}): string {
  if (!t.jd_title) return "no JD title detected";
  if (t.exact_match) return `'${t.jd_title}' exact match`;
  if (t.partial_match) return `'${t.jd_title}' partial match`;
  return `'${t.jd_title}' not found on resume`;
}
