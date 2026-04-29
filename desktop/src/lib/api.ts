/**
 * Localhost HTTP client for the lucky-resume-server sidecar.
 *
 * The Tauri shell launches the sidecar on a fixed port (7421 by
 * default — see `src-tauri/tauri.conf.json`). All routes are
 * single-host so no CORS dance is needed in production; dev mode
 * (Vite's localhost:1420) hits the same loopback port.
 */

import { useMutation, useQuery, type UseMutationOptions } from "@tanstack/react-query";

import type { TaskSnapshot } from "./events";

const SERVER_PORT = Number(import.meta.env.VITE_SERVER_PORT ?? 7421);
const SERVER_BASE = `http://127.0.0.1:${SERVER_PORT}`;

export function serverHttpUrl(path: string): string {
  return `${SERVER_BASE}${path}`;
}

export function serverWsUrl(path: string): string {
  return `ws://127.0.0.1:${SERVER_PORT}${path}`;
}

class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public detail?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function request<T>(
  path: string,
  init?: RequestInit & { json?: unknown },
): Promise<T> {
  const headers = new Headers(init?.headers);
  let body = init?.body;
  if (init?.json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(init.json);
  }
  const resp = await fetch(serverHttpUrl(path), { ...init, headers, body });
  const text = await resp.text();
  let parsed: unknown = undefined;
  if (text) {
    try {
      parsed = JSON.parse(text);
    } catch {
      parsed = text;
    }
  }
  if (!resp.ok) {
    const detail =
      parsed && typeof parsed === "object" && "detail" in parsed
        ? (parsed as { detail: unknown }).detail
        : parsed;
    throw new ApiError(
      typeof detail === "string" ? detail : `HTTP ${resp.status}`,
      resp.status,
      detail,
    );
  }
  return parsed as T;
}

// --- Health -----------------------------------------------------------------

export type HealthResponse = {
  status: "ok";
  llm_provider: string;
  llm_model: string;
};

export function useHealth() {
  return useQuery<HealthResponse>({
    queryKey: ["health"],
    queryFn: () => request<HealthResponse>("/health"),
    refetchInterval: 5_000,
    retry: false, // sidecar boot can be slow; let the UI render its own retry
  });
}

// --- Settings ---------------------------------------------------------------

export type SettingsPayload = {
  llm_provider: string;
  llm_model: string;
  openai_api_key: string;
  anthropic_api_key: string;
  google_api_key: string;
  openrouter_api_key: string;
  log_level: string;
  ats_skip_threshold: number;
  resume_template: string;
  resume_style_path: string;
  enrich_threshold: number;
  resume_max_iterations: number;
  ats_weight_hard: number;
  ats_weight_soft: number;
  ats_weight_structural: number;
  ats_weight_title: number;
  ats_weight_measurable: number;
  ats_weight_tone: number;
  env_file_path: string;
};

export type SettingsUpdate = Partial<SettingsPayload>;

export function useSettings() {
  return useQuery<SettingsPayload>({
    queryKey: ["settings"],
    queryFn: () => request<SettingsPayload>("/api/settings"),
  });
}

export function useUpdateSettings(
  options?: UseMutationOptions<SettingsPayload, ApiError, SettingsUpdate>,
) {
  return useMutation<SettingsPayload, ApiError, SettingsUpdate>({
    mutationFn: (payload) =>
      request<SettingsPayload>("/api/settings", {
        method: "PUT",
        json: payload,
      }),
    ...options,
  });
}

// --- Score ------------------------------------------------------------------

export type ContactCheck = {
  email_present: boolean;
  phone_present: boolean;
  address_present: boolean;
};

export type SectionCheck = {
  summary: boolean;
  experience: boolean;
  education: boolean;
  skills: boolean;
};

export type JobTitleMatch = {
  exact_match: boolean;
  partial_match: boolean;
  jd_title: string;
  resume_titles: string[];
};

export type SkillCountRow = {
  name: string;
  resume_count: number;
  jd_count: number;
};

export type ToneFlag = {
  phrase: string;
  line: string;
  suggestion: string;
};

export type ATSReport = {
  score: number;
  reasoning: string;
  contact: ContactCheck;
  sections: SectionCheck;
  job_title: JobTitleMatch;
  measurable_results_count: number;
  word_count: number;
  word_count_ok: boolean;
  hard_skills: SkillCountRow[];
  soft_skills: SkillCountRow[];
  tone_flags: ToneFlag[];
  level_match_reasoning: string;
  keyword_matches: string[];
  keyword_gaps: string[];
};

export type Link = {
  label: string;
  url: string;
};

export type ExperienceBullet = {
  id: string;
  text: string;
};

export type ExperienceEntry = {
  id: string;
  role: string;
  company: string;
  location: string;
  start_date: string;
  end_date: string;
  bullets: ExperienceBullet[];
  tech: string[];
};

export type EducationEntry = {
  id: string;
  degree: string;
  school: string;
  location: string;
  start_date: string;
  end_date: string;
  details: string;
};

export type SkillGroup = {
  category: string;
  items: string[];
};

export type MasterView = {
  name: string;
  headline: string;
  email: string;
  phone: string;
  location: string;
  links: Link[];
  summary: string;
  experience: ExperienceEntry[];
  education: EducationEntry[];
  skills: string[];
  skill_groups: SkillGroup[];
};

export type ScoreResponse = {
  ats_score: ATSReport;
  errors: string[];
  master_view: MasterView | null;
};

export type ScoreRequest = {
  master?: string;
  resume?: string;
  job: string;
};

// --- Tasks (Phase 2 registry) ----------------------------------------------

export type RunRequest = {
  master?: string;
  resume?: string;
  facts?: string;
  job: string;
  output?: string;
  style?: string;
  no_enrich?: boolean;
  no_approve?: boolean;
  max_iter?: number;
};

export type StartedTask = { task_id: string };

export function listTasks(): Promise<TaskSnapshot[]> {
  return request<TaskSnapshot[]>("/api/tasks");
}

export function getTask(taskId: string): Promise<TaskSnapshot> {
  return request<TaskSnapshot>(`/api/tasks/${encodeURIComponent(taskId)}`);
}

export function deleteTask(taskId: string): Promise<{ deleted: boolean }> {
  return request<{ deleted: boolean }>(
    `/api/tasks/${encodeURIComponent(taskId)}`,
    { method: "DELETE" },
  );
}

export function cancelTask(taskId: string): Promise<{ cancelled: boolean }> {
  return request<{ cancelled: boolean }>(
    `/api/tasks/${encodeURIComponent(taskId)}/cancel`,
    { method: "POST" },
  );
}

export function startRun(payload: RunRequest): Promise<StartedTask> {
  return request<StartedTask>("/api/tasks/run", {
    method: "POST",
    json: payload,
  });
}

export function startScore(payload: ScoreRequest): Promise<StartedTask> {
  return request<StartedTask>("/api/tasks/score", {
    method: "POST",
    json: payload,
  });
}

export function replyTask(
  taskId: string,
  promptSeq: number,
  value: string | boolean | number,
): Promise<{ accepted: boolean }> {
  return request<{ accepted: boolean }>(
    `/api/tasks/${encodeURIComponent(taskId)}/reply`,
    {
      method: "POST",
      json: { prompt_seq: promptSeq, value },
    },
  );
}

export function useTasks() {
  return useQuery<TaskSnapshot[]>({
    queryKey: ["tasks"],
    queryFn: listTasks,
    // Snapshot freshness is driven by the live WS attach; the list query
    // is a fallback for the initial hydrate + after destructive ops.
    staleTime: 2_000,
  });
}

// --- Extract Style ----------------------------------------------------------

export type StyleMargins = {
  top: number;
  bottom: number;
  side: number;
};

export type StyleSizing = {
  size: number;
};

export type StyleTemplate = {
  font_family: string;
  margins: StyleMargins;
  name_style: StyleSizing;
  section: StyleSizing;
  body: StyleSizing;
};

export type ExtractStyleRequest = {
  source: string;
  output?: string;
};

export type ExtractStyleResponse = {
  style: StyleTemplate;
  written_to: string | null;
};

export function useExtractStyle(
  options?: UseMutationOptions<ExtractStyleResponse, ApiError, ExtractStyleRequest>,
) {
  return useMutation<ExtractStyleResponse, ApiError, ExtractStyleRequest>({
    mutationFn: (payload) =>
      request<ExtractStyleResponse>("/api/extract-style", {
        method: "POST",
        json: payload,
      }),
    ...options,
  });
}

// --- YAML preview -----------------------------------------------------------

export type YamlPreview = {
  path: string;
  content: unknown;
};

/**
 * Reads + parses a YAML file via the sidecar so the GUI can render its
 * contents in `<YamlTree>` without a Tauri filesystem permission. Only
 * fires when `path` is non-empty (and `enabled` not turned off), so
 * components can mount the dialog without a path locked in.
 */
export function useYamlFile(path: string, options?: { enabled?: boolean }) {
  return useQuery<YamlPreview>({
    queryKey: ["yaml", path],
    queryFn: () =>
      request<YamlPreview>(
        `/api/yaml?path=${encodeURIComponent(path)}`,
      ),
    enabled: !!path && (options?.enabled ?? true),
    // Cache aggressively — the user controls when to refetch via the
    // dialog's mount/unmount cycle, and YAMLs they're previewing
    // rarely change underneath them within a session.
    staleTime: 60_000,
  });
}

// --- Built-in styles --------------------------------------------------------

export type BuiltinStyle = {
  name: string;
  label: string;
  description: string;
  template: StyleTemplate;
};

export type BuiltinStylesResponse = {
  styles: BuiltinStyle[];
};

/**
 * Read-only catalog of bundled style presets. Names like `default` /
 * `consolas` are sent back to the run/extract endpoints as
 * `builtin:<name>` to apply the preset without the user managing files.
 */
export function useBuiltinStyles() {
  return useQuery<BuiltinStylesResponse>({
    queryKey: ["styles", "builtin"],
    queryFn: () => request<BuiltinStylesResponse>("/api/styles/builtin"),
    // Bundled presets never change at runtime — once we have them, keep
    // them indefinitely (cuts repeated round-trips on every screen
    // mount).
    staleTime: Infinity,
  });
}

export const BUILTIN_PREFIX = "builtin:";

export function isBuiltinIdentifier(value: string | undefined | null): boolean {
  return !!value && value.startsWith(BUILTIN_PREFIX);
}

export { ApiError };
