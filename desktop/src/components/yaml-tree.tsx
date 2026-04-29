import { ChevronDown, ChevronRight } from "lucide-react";
import { useState } from "react";

import { cn } from "@/lib/cn";

type Json =
  | string
  | number
  | boolean
  | null
  | Json[]
  | { [key: string]: Json };

type Props = {
  data: unknown;
  /** Initial open depth — rows at depth ≤ this are expanded by default. */
  defaultOpenDepth?: number;
};

/**
 * Generic YAML/JSON tree renderer. Takes an arbitrary plain-JSON value
 * and renders objects/arrays as expandable nodes with chevron carets,
 * scalars as monospace leaves. The CLI's "extract-style" output and any
 * other deeply-nested config blob can use this directly without a
 * bespoke component.
 */
export function YamlTree({ data, defaultOpenDepth = 1 }: Props) {
  return (
    <div className="font-mono text-xs">
      <Node value={data as Json} depth={0} defaultOpenDepth={defaultOpenDepth} />
    </div>
  );
}

function Node({
  name,
  value,
  depth,
  defaultOpenDepth,
}: {
  name?: string;
  value: Json;
  depth: number;
  defaultOpenDepth: number;
}) {
  if (isScalar(value)) {
    return (
      <Row depth={depth}>
        {name !== undefined && <KeyLabel name={name} />}
        <ScalarValue value={value} />
      </Row>
    );
  }
  return (
    <CollapsibleNode
      name={name}
      value={value}
      depth={depth}
      defaultOpenDepth={defaultOpenDepth}
    />
  );
}

function CollapsibleNode({
  name,
  value,
  depth,
  defaultOpenDepth,
}: {
  name?: string;
  value: Exclude<Json, string | number | boolean | null>;
  depth: number;
  defaultOpenDepth: number;
}) {
  const [open, setOpen] = useState(depth < defaultOpenDepth);
  const entries = toEntries(value);
  const isEmpty = entries.length === 0;
  const summary = isEmpty
    ? Array.isArray(value)
      ? "[]"
      : "{}"
    : Array.isArray(value)
      ? `[${entries.length}]`
      : `{${entries.length}}`;
  return (
    <div>
      <Row
        depth={depth}
        clickable={!isEmpty}
        onClick={() => !isEmpty && setOpen((v) => !v)}
      >
        {!isEmpty ? (
          open ? (
            <ChevronDown className="h-3 w-3 text-fg-faint shrink-0" />
          ) : (
            <ChevronRight className="h-3 w-3 text-fg-faint shrink-0" />
          )
        ) : (
          <span className="w-3 shrink-0" />
        )}
        {name !== undefined ? (
          <KeyLabel name={name} />
        ) : (
          <span />
        )}
        <span className="text-fg-faint">{summary}</span>
      </Row>
      {open && !isEmpty && (
        <div>
          {entries.map(([childName, childValue]) => (
            <Node
              key={childName}
              name={childName}
              value={childValue}
              depth={depth + 1}
              defaultOpenDepth={defaultOpenDepth}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function Row({
  depth,
  children,
  clickable,
  onClick,
}: {
  depth: number;
  children: React.ReactNode;
  clickable?: boolean;
  onClick?: () => void;
}) {
  return (
    <div
      onClick={onClick}
      role={clickable ? "button" : undefined}
      className={cn(
        "flex items-center gap-1.5 py-0.5 pr-2 leading-relaxed",
        clickable && "cursor-pointer hover:bg-bg-raised",
      )}
      style={{ paddingLeft: `${depth * 14 + 4}px` }}
    >
      {children}
    </div>
  );
}

function KeyLabel({ name }: { name: string }) {
  return <span className="text-accent">{name}:</span>;
}

function ScalarValue({ value }: { value: string | number | boolean | null }) {
  if (value === null) {
    return <span className="text-fg-faint italic">null</span>;
  }
  if (typeof value === "boolean") {
    return <span className="text-warning">{String(value)}</span>;
  }
  if (typeof value === "number") {
    return <span className="text-success tabular-nums">{value}</span>;
  }
  // String — render hex colors with a swatch chip.
  if (/^#[0-9a-fA-F]{3,8}$/.test(value)) {
    return (
      <span className="inline-flex items-center gap-1.5">
        <span
          className="inline-block h-3 w-3 rounded-sm border border-border"
          style={{ backgroundColor: value }}
        />
        <span className="text-fg">{value}</span>
      </span>
    );
  }
  return <span className="text-fg break-all">{value}</span>;
}

function isScalar(
  value: Json,
): value is string | number | boolean | null {
  return (
    value === null ||
    typeof value === "string" ||
    typeof value === "number" ||
    typeof value === "boolean"
  );
}

function toEntries(value: Json[] | { [key: string]: Json }): [string, Json][] {
  if (Array.isArray(value)) {
    return value.map((v, i) => [String(i), v]);
  }
  return Object.entries(value);
}
