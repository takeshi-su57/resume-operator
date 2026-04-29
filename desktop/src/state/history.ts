/**
 * Per-page run history backed by the sidecar's `config.json`.
 *
 * Each successful Bootstrap / Extract Style run pushes a
 * (source, output, timestamp) triple here. The store is a thin
 * facade over `GET / PATCH /api/config`: hydration is React Query,
 * mutations are optimistic so the UI doesn't wait on the round-trip
 * before the new entry appears.
 *
 * Why server-side instead of `localStorage`: the prior implementation
 * lived in the Tauri webview's localStorage, which gets wiped on
 * every reinstall (and isn't reachable from the CLI). The JSON file
 * lives at `<env_dir>/config.json` next to `.env`, so all user-scoped
 * state survives an MSI reinstall and is one folder away from any
 * external editor.
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationOptions,
} from "@tanstack/react-query";

import { request, type ApiError } from "@/lib/api";

export type HistoryPage = "bootstrap" | "extract-style";

export type HistoryEntry = {
  source: string;
  output: string;
  at: number;
};

type HistoryByPage = Partial<Record<HistoryPage, HistoryEntry[]>>;

type UserConfigResponse = {
  config: { history?: HistoryByPage } & Record<string, unknown>;
  config_file_path: string;
};

type UserConfigPatch = {
  data: { history?: HistoryByPage } & Record<string, unknown>;
};

const MAX_ENTRIES = 10;
const QUERY_KEY = ["user-config"] as const;

function fetchUserConfig(): Promise<UserConfigResponse> {
  return request<UserConfigResponse>("/api/config");
}

function patchUserConfig(payload: UserConfigPatch): Promise<UserConfigResponse> {
  return request<UserConfigResponse>("/api/config", {
    method: "PATCH",
    json: payload,
  });
}

/**
 * React Query hook for the full user config. Most callers want
 * `useHistoryEntries(page)` — this is the underlying source of truth
 * other hooks layer on top of.
 */
export function useUserConfig() {
  return useQuery<UserConfigResponse>({
    queryKey: QUERY_KEY,
    queryFn: fetchUserConfig,
    // Config is only ever changed from this client, so freshness is
    // implicit — refetch only on explicit invalidate (after a PATCH).
    staleTime: Infinity,
  });
}

function usePatchUserConfig(
  options?: UseMutationOptions<UserConfigResponse, ApiError, UserConfigPatch>,
) {
  const qc = useQueryClient();
  return useMutation<UserConfigResponse, ApiError, UserConfigPatch>({
    mutationFn: patchUserConfig,
    onSuccess: (next) => {
      qc.setQueryData(QUERY_KEY, next);
    },
    ...options,
  });
}

/**
 * Read the recent-runs list for a given page. Returns the empty array
 * while the initial GET is in flight or if the field is missing.
 */
export function useHistoryEntries(page: HistoryPage): HistoryEntry[] {
  const { data } = useUserConfig();
  return data?.config.history?.[page] ?? [];
}

/**
 * Returns mutators for the recent-runs list. Each mutator computes the
 * new array from the cache and PATCHes the full slice — server-side
 * deep-merge replaces the array atomically.
 */
export function useHistoryActions() {
  const qc = useQueryClient();
  const patch = usePatchUserConfig();

  const currentEntries = (page: HistoryPage): HistoryEntry[] => {
    const cache = qc.getQueryData<UserConfigResponse>(QUERY_KEY);
    return cache?.config.history?.[page] ?? [];
  };

  const submit = (page: HistoryPage, next: HistoryEntry[]): void => {
    // Optimistic UI: paint the new state into the cache before the
    // round-trip resolves. The mutation's onSuccess will overwrite
    // with the server's authoritative shape.
    const cache = qc.getQueryData<UserConfigResponse>(QUERY_KEY);
    if (cache) {
      qc.setQueryData<UserConfigResponse>(QUERY_KEY, {
        ...cache,
        config: {
          ...cache.config,
          history: { ...cache.config.history, [page]: next },
        },
      });
    }
    patch.mutate({ data: { history: { [page]: next } } });
  };

  const push = (page: HistoryPage, entry: HistoryEntry): void => {
    const filtered = currentEntries(page).filter(
      (e) => !(e.source === entry.source && e.output === entry.output),
    );
    submit(page, [entry, ...filtered].slice(0, MAX_ENTRIES));
  };

  const remove = (page: HistoryPage, at: number): void => {
    submit(
      page,
      currentEntries(page).filter((e) => e.at !== at),
    );
  };

  const clear = (page: HistoryPage): void => {
    submit(page, []);
  };

  return { push, remove, clear };
}
