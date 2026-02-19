import type { LatestResponse, MetricsRangeResponse, SummaryResponse } from "./types";

const BASE = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");

async function get<T>(url: string): Promise<T> {
    const res = await fetch(`${BASE}${url}`);
    if (!res.ok) {
        throw new Error(`API ${url}: ${res.status}`);
    }
    return res.json();
}

export function fetchLatest(): Promise<LatestResponse> {
    return get<LatestResponse>("/api/metrics/latest");
}

export function fetchRange(from: string, to: string, step?: number): Promise<MetricsRangeResponse> {
    let url = `/api/metrics?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`;
    if (step) url += `&step=${step}`;
    return get<MetricsRangeResponse>(url);
}

export function fetchSummary(window: number): Promise<SummaryResponse> {
    return get<SummaryResponse>(`/api/summary?window=${window}`);
}
