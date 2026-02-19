export interface MetricsSample {
    id: number;
    ts_utc: string;
    cpu_percent: number;
    load_avg_1: number | null;
    mem_used_bytes: number;
    mem_total_bytes: number;
    mem_percent: number;
    disk_used_bytes: number;
    disk_total_bytes: number;
    disk_percent: number;
    net_rx_bps: number;
    net_tx_bps: number;
    uptime_seconds: number | null;
}

export interface HealthBadge {
    overall: "OK" | "WARN" | "CRIT";
    cpu: string;
    mem: string;
    disk: string;
}

export interface LatestResponse extends MetricsSample {
    health: HealthBadge;
}

export interface MetricsRangeResponse {
    points: MetricsSample[];
    step_seconds: number;
    note: string | null;
}

export interface SummaryField {
    min: number;
    avg: number;
    max: number;
}

export interface SummaryResponse {
    window_minutes: number;
    cpu_percent: SummaryField;
    mem_percent: SummaryField;
    disk_percent: SummaryField;
    net_rx_bps: SummaryField;
    net_tx_bps: SummaryField;
}

export interface Host {
    id: number;
    host_key: string;
    display_name: string;
    created_at: string;
    last_seen_at: string;
}
