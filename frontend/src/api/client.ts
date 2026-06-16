/**
 * Typed fetch-based client for the cueing-engine backend.
 *
 * Mirrors `shared/api_contract.md`. Every method returns a typed model from
 * `../types`. The base URL defaults to the Vite env var `VITE_API_BASE_URL`,
 * else `http://localhost:8000` (the FastAPI dev server, mock mode by default).
 *
 * Conventions: coords `[lon, lat]` EPSG:4326; times are ISO-8601 UTC strings.
 * A `BBox` is `[min_lon, min_lat, max_lon, max_lat]` and is serialized to the
 * comma-separated `bbox=` query param the backend expects.
 */

import type {
  BBox,
  CueRecommendation,
  CriticalityGrid,
  CuesResponse,
  GeoResponse,
  HealthResponse,
  Incident,
  IncidentsResponse,
  Scenario,
  ScenariosResponse,
  ScoredVessel,
  ScoresResponse,
  VesselTrack,
  VesselsResponse,
} from "../types/models";

/** A time instant or window value: a `Date` or an ISO-8601 string. */
export type TimeLike = Date | string;

function isoOf(t: TimeLike | undefined): string | undefined {
  if (t === undefined) return undefined;
  return typeof t === "string" ? t : t.toISOString();
}

function bboxParam(b: BBox | undefined): string | undefined {
  return b ? b.join(",") : undefined;
}

function buildQuery(params: Record<string, string | number | undefined>): string {
  const usp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") usp.set(k, String(v));
  }
  const s = usp.toString();
  return s ? `?${s}` : "";
}

export interface VesselsQuery {
  bbox?: BBox;
  start?: TimeLike;
  end?: TimeLike;
  limit?: number;
}

export interface InstantQuery {
  t?: TimeLike;
  bbox?: BBox;
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly statusText: string,
    public readonly body: unknown,
    public readonly url: string,
  ) {
    super(`API ${status} ${statusText} for ${url}`);
    this.name = "ApiError";
  }
}

export class CueingApiClient {
  readonly baseUrl: string;

  constructor(baseUrl?: string) {
    const fromEnv =
      typeof import.meta !== "undefined"
        ? (import.meta as { env?: Record<string, string> }).env?.VITE_API_BASE_URL
        : undefined;
    this.baseUrl = (baseUrl ?? fromEnv ?? "http://localhost:8000").replace(/\/$/, "");
  }

  private async get<T>(path: string, signal?: AbortSignal): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const res = await fetch(url, {
      method: "GET",
      headers: { Accept: "application/json" },
      signal,
    });
    if (!res.ok) {
      let body: unknown = undefined;
      try {
        body = await res.json();
      } catch {
        /* non-JSON error body */
      }
      throw new ApiError(res.status, res.statusText, body, url);
    }
    return (await res.json()) as T;
  }

  /** Liveness + which data source the backend is using. */
  health(signal?: AbortSignal): Promise<HealthResponse> {
    return this.get<HealthResponse>("/health", signal);
  }

  /** The shared display encoding the backend is serving (for drift checks). */
  encoding(signal?: AbortSignal): Promise<unknown> {
    return this.get<unknown>("/encoding", signal);
  }

  /** Vessel tracks within a bbox + time window. */
  async vessels(q: VesselsQuery = {}, signal?: AbortSignal): Promise<VesselTrack[]> {
    const query = buildQuery({
      bbox: bboxParam(q.bbox),
      start: isoOf(q.start),
      end: isoOf(q.end),
      limit: q.limit,
    });
    const data = await this.get<VesselsResponse>(`/vessels${query}`, signal);
    return data.vessels;
  }

  /** Per-vessel suspicion at an instant (sorted hottest-first by the backend). */
  async scores(q: InstantQuery = {}, signal?: AbortSignal): Promise<ScoredVessel[]> {
    const query = buildQuery({ t: isoOf(q.t), bbox: bboxParam(q.bbox) });
    const data = await this.get<ScoresResponse>(`/scores${query}`, signal);
    return data.scores;
  }

  /** Top-N ranked task-next recommendations at an instant. */
  async cues(
    q: InstantQuery & { top?: number } = {},
    signal?: AbortSignal,
  ): Promise<CueRecommendation[]> {
    const query = buildQuery({ t: isoOf(q.t), bbox: bboxParam(q.bbox), top: q.top });
    const data = await this.get<CuesResponse>(`/cues${query}`, signal);
    return data.cues;
  }

  /** Criticality + cueing grid at an instant. */
  async criticality(q: InstantQuery = {}, signal?: AbortSignal): Promise<CriticalityGrid> {
    const query = buildQuery({ t: isoOf(q.t), bbox: bboxParam(q.bbox) });
    const data = await this.get<GeoResponse>(`/geo/criticality${query}`, signal);
    return data.grid;
  }

  /** Named demo scenarios. */
  async scenarios(signal?: AbortSignal): Promise<Scenario[]> {
    const data = await this.get<ScenariosResponse>("/scenarios", signal);
    return data.scenarios;
  }

  /** A single scenario by id (throws ApiError(404) if unknown). */
  scenario(id: string, signal?: AbortSignal): Promise<Scenario> {
    return this.get<Scenario>(`/scenarios/${encodeURIComponent(id)}`, signal);
  }

  /** The ground-truth incident catalogue. */
  async incidents(signal?: AbortSignal): Promise<Incident[]> {
    const data = await this.get<IncidentsResponse>("/incidents", signal);
    return data.incidents;
  }
}

/** A ready-to-use default client (env / localhost). */
export const api = new CueingApiClient();
