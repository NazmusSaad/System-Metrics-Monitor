import type { LatestResponse, MetricsRangeResponse, SummaryResponse, Host } from "./types";

const BASE = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");

async function get<T>(url: string): Promise<T> {
    const res = await fetch(`${BASE}${url}`);
    if (!res.ok) {
        throw new Error(`API ${url}: ${res.status}`);
    }
    return res.json();
}

function hostParam(hostKey: string | null): string {
    return hostKey ? `&host_key=${encodeURIComponent(hostKey)}` : "";
}

export function fetchHosts(): Promise<Host[]> {
    return get<Host[]>("/api/hosts");
}

export function fetchLatest(hostKey: string | null): Promise<LatestResponse> {
    const q = hostKey ? `?host_key=${encodeURIComponent(hostKey)}` : "";
    return get<LatestResponse>(`/api/metrics/latest${q}`);
}

export function fetchRange(from: string, to: string, step: number | undefined, hostKey: string | null): Promise<MetricsRangeResponse> {
    let url = `/api/metrics?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`;
    if (step) url += `&step=${step}`;
    url += hostParam(hostKey);
    return get<MetricsRangeResponse>(url);
}

export function fetchSummary(window: number, hostKey: string | null): Promise<SummaryResponse> {
    return get<SummaryResponse>(`/api/summary?window=${window}${hostParam(hostKey)}`);
}
