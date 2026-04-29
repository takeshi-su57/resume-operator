import { Check, ChevronDown, ChevronRight, Minus, X } from "lucide-react";
import { Fragment, useState } from "react";

import type {
  ATSReport,
  EducationEntry,
  ExperienceEntry,
  JobTitleMatch,
  MasterView,
} from "@/lib/api";
import { cn } from "@/lib/cn";

function scoreColor(s: number): string {
  if (s >= 0.7) return "text-success";
  if (s >= 0.4) return "text-warning";
  return "text-danger";
}

function pct(n: number): string {
  return `${Math.round(n * 100)}%`;
}

function Glyph({ state }: { state: "ok" | "warn" | "fail" }) {
  if (state === "ok") return <Check className="h-3.5 w-3.5 text-success" />;
  if (state === "warn") return <Minus className="h-3.5 w-3.5 text-warning" />;
  return <X className="h-3.5 w-3.5 text-danger" />;
}

/**
 * The full multi-dim ATSReport (#81) rendered as a compact dashboard:
 * composite score → structural checks → hard/soft skill tables → tone
 * flags → keyword gaps. Mirrors the CLI's `_display_ats_report` output
 * but in a denser two-column layout.
 *
 * Structural rows are expandable: clicking one drops down the actual
 * data behind the present/missing summary (contact values, full
 * summary/experience/education for Sections, JD title vs resume titles
 * for Job title match). Powered by `master_view` from the same response;
 * when missing (legacy resume PDF input), the rows stay collapsed-only.
 */
export function AtsReport({
  report,
  master,
}: {
  report: ATSReport;
  master: MasterView | null;
}) {
  const composite = report.score;
  const titleState = report.job_title.exact_match
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
        <div className="divide-y divide-border-subtle">
          <ExpandableRow
            state={
              report.contact.email_present &&
              report.contact.phone_present &&
              report.contact.address_present
                ? "ok"
                : "warn"
            }
            label="Contact info"
            detail={contactDetail(report.contact)}
            expanded={master ? <ContactDetail master={master} /> : null}
          />
          <ExpandableRow
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
            expanded={master ? <SectionsDetail master={master} /> : null}
          />
          <ExpandableRow
            state={titleState}
            label="Job title match"
            labelTooltip="Compares the JD's target title against every role title on your resume — exact wins, partial = substring or close match, otherwise no match."
            detail={titleDetail(report.job_title)}
            expanded={<JobTitleDetail jt={report.job_title} />}
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
        </div>
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
    <div className="grid grid-cols-[24px_1fr_auto] items-center gap-2 px-3 py-1.5 text-sm">
      <Glyph state={state} />
      <span className="text-fg">{label}</span>
      <span className="text-xs text-fg-dim text-right">{detail}</span>
    </div>
  );
}

function ExpandableRow({
  state,
  label,
  labelTooltip,
  detail,
  expanded,
}: {
  state: "ok" | "warn" | "fail";
  label: string;
  labelTooltip?: string;
  detail: string;
  expanded: React.ReactNode | null;
}) {
  const [open, setOpen] = useState(false);
  const canExpand = expanded !== null;
  return (
    <div>
      <button
        type="button"
        onClick={() => canExpand && setOpen((v) => !v)}
        disabled={!canExpand}
        className={cn(
          "grid w-full grid-cols-[16px_24px_1fr_auto] items-center gap-2 px-3 py-1.5 text-sm text-left",
          canExpand && "hover:bg-bg-raised cursor-pointer",
          !canExpand && "cursor-default",
        )}
        title={labelTooltip}
      >
        {canExpand ? (
          open ? (
            <ChevronDown className="h-3.5 w-3.5 text-fg-faint" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5 text-fg-faint" />
          )
        ) : (
          <span />
        )}
        <Glyph state={state} />
        <span className="text-fg">{label}</span>
        <span className="text-xs text-fg-dim text-right">{detail}</span>
      </button>
      {open && expanded && (
        <div className="border-t border-border-subtle bg-bg-subtle px-3 py-3">
          {expanded}
        </div>
      )}
    </div>
  );
}

function ContactDetail({ master }: { master: MasterView }) {
  return (
    <dl className="grid grid-cols-[120px_1fr] gap-y-1 text-xs">
      <ContactField label="Name" value={master.name} />
      <ContactField label="Email" value={master.email} />
      <ContactField label="Phone" value={master.phone} />
      <ContactField label="Address" value={master.location} />
      {master.headline && (
        <ContactField label="Headline" value={master.headline} />
      )}
      {master.links.length > 0 && (
        <>
          <dt className="text-fg-muted uppercase tracking-wider">Links</dt>
          <dd>
            <ul className="space-y-0.5">
              {master.links.map((link) => (
                <li key={link.url} className="font-mono text-fg">
                  <span className="text-fg-muted">{link.label}: </span>
                  {link.url}
                </li>
              ))}
            </ul>
          </dd>
        </>
      )}
    </dl>
  );
}

function ContactField({ label, value }: { label: string; value: string }) {
  return (
    <>
      <dt className="text-fg-muted uppercase tracking-wider">{label}</dt>
      <dd
        className={cn(
          "font-mono",
          value ? "text-fg" : "text-fg-faint italic",
        )}
      >
        {value || "(missing)"}
      </dd>
    </>
  );
}

function SectionsDetail({ master }: { master: MasterView }) {
  return (
    <div className="space-y-4 text-xs">
      <SectionBlock label="Summary">
        {master.summary ? (
          <p className="text-fg leading-relaxed whitespace-pre-wrap">
            {master.summary}
          </p>
        ) : (
          <Empty>No summary on file.</Empty>
        )}
      </SectionBlock>
      <SectionBlock label="Experience">
        {master.experience.length > 0 ? (
          <ul className="space-y-3">
            {master.experience.map((entry) => (
              <ExperienceItem key={entry.id} entry={entry} />
            ))}
          </ul>
        ) : (
          <Empty>No experience entries.</Empty>
        )}
      </SectionBlock>
      <SectionBlock label="Education">
        {master.education.length > 0 ? (
          <ul className="space-y-2">
            {master.education.map((entry) => (
              <EducationItem key={entry.id} entry={entry} />
            ))}
          </ul>
        ) : (
          <Empty>No education entries.</Empty>
        )}
      </SectionBlock>
      <SectionBlock label="Skills">
        {master.skill_groups.length > 0 ? (
          <ul className="space-y-1">
            {master.skill_groups.map((group) => (
              <li key={group.category}>
                <span className="text-fg-muted">{group.category}: </span>
                <span className="text-fg">{group.items.join(", ")}</span>
              </li>
            ))}
          </ul>
        ) : master.skills.length > 0 ? (
          <p className="text-fg">{master.skills.join(", ")}</p>
        ) : (
          <Empty>No skills on file.</Empty>
        )}
      </SectionBlock>
    </div>
  );
}

function SectionBlock({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <h4 className="mb-1.5 text-xs uppercase tracking-wider text-fg-muted">
        {label}
      </h4>
      {children}
    </div>
  );
}

function ExperienceItem({ entry }: { entry: ExperienceEntry }) {
  const dateRange = [entry.start_date, entry.end_date]
    .filter(Boolean)
    .join(" – ");
  return (
    <li className="space-y-1">
      <div className="flex items-baseline justify-between gap-2">
        <p className="text-fg">
          <span className="font-bold">{entry.role || "(no role)"}</span>
          {entry.company && (
            <span className="text-fg-muted"> · {entry.company}</span>
          )}
        </p>
        {dateRange && (
          <span className="text-fg-faint shrink-0">{dateRange}</span>
        )}
      </div>
      {entry.bullets.length > 0 && (
        <ul className="ml-4 list-disc space-y-0.5 text-fg-muted">
          {entry.bullets.map((bullet) => (
            <li key={bullet.id}>{bullet.text}</li>
          ))}
        </ul>
      )}
      {entry.tech.length > 0 && (
        <p className="text-fg-faint">
          <span className="text-fg-muted">Tech: </span>
          {entry.tech.join(", ")}
        </p>
      )}
    </li>
  );
}

function EducationItem({ entry }: { entry: EducationEntry }) {
  const dateRange = [entry.start_date, entry.end_date]
    .filter(Boolean)
    .join(" – ");
  return (
    <li className="flex items-baseline justify-between gap-2">
      <span className="text-fg">
        <span className="font-bold">{entry.degree || "(no degree)"}</span>
        {entry.school && (
          <span className="text-fg-muted"> · {entry.school}</span>
        )}
      </span>
      {dateRange && (
        <span className="text-fg-faint shrink-0">{dateRange}</span>
      )}
    </li>
  );
}

function JobTitleDetail({ jt }: { jt: JobTitleMatch }) {
  return (
    <div className="space-y-2 text-xs">
      <div>
        <span className="text-fg-muted uppercase tracking-wider mr-2">
          JD title
        </span>
        <span className="font-mono text-fg">
          {jt.jd_title || "(none detected)"}
        </span>
      </div>
      <div>
        <p className="text-fg-muted uppercase tracking-wider mb-1">
          Resume titles
        </p>
        {jt.resume_titles.length === 0 ? (
          <Empty>No titles found on resume.</Empty>
        ) : (
          <ul className="space-y-0.5">
            {jt.resume_titles.map((title, i) => (
              <li key={i} className="flex items-center gap-2">
                <Glyph state={titleRowState(title, jt)} />
                <span className="font-mono text-fg">{title}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function titleRowState(
  title: string,
  jt: JobTitleMatch,
): "ok" | "warn" | "fail" {
  if (!jt.jd_title) return "warn";
  const norm = (s: string) => s.trim().toLowerCase();
  if (norm(title) === norm(jt.jd_title)) return "ok";
  if (
    norm(title).includes(norm(jt.jd_title)) ||
    norm(jt.jd_title).includes(norm(title))
  ) {
    return "warn";
  }
  return "fail";
}

function Empty({ children }: { children: React.ReactNode }) {
  return <p className="text-fg-faint italic">{children}</p>;
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

