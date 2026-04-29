/**
 * Localhost HTTP client for the resume-operator-server sidecar.
 *
 * The Tauri shell launches the sidecar on a fixed port (7421 by
 * default — see `src-tauri/tauri.conf.json`). All routes are
 * single-host so no CORS dance is needed in production; dev mode
 * (Vite's localhost:1420) hits the same loopback port.
 */

import { useMutation, useQuery, type UseMutationOptions } from "@tanstack/react-query";

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

async function request<T>(
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

export type ScoreResponse = {
  ats_score: ATSReport;
  errors: string[];
};

export type ScoreRequest = {
  master?: string;
  resume?: string;
  job: string;
};

export function useScore(
  options?: UseMutationOptions<ScoreResponse, ApiError, ScoreRequest>,
) {
  return useMutation<ScoreResponse, ApiError, ScoreRequest>({
    mutationFn: (payload) =>
      request<ScoreResponse>("/api/score", {
        method: "POST",
        json: payload,
      }),
    ...options,
  });
}

// --- Parse Resume -----------------------------------------------------------

export type ResumeData = {
  name: string;
  email: string;
  phone: string;
  summary: string;
  skills: string[];
  experience: unknown[];
  education: unknown[];
  certifications: string[];
  raw_text: string;
};

export type ParseResumeResponse = {
  resume: ResumeData;
  errors: string[];
};

export function useParseResume(
  options?: UseMutationOptions<ParseResumeResponse, ApiError, { resume: string }>,
) {
  return useMutation<ParseResumeResponse, ApiError, { resume: string }>({
    mutationFn: (payload) =>
      request<ParseResumeResponse>("/api/parse-resume", {
        method: "POST",
        json: payload,
      }),
    ...options,
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

export { ApiError };
