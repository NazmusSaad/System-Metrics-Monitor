import { useState, useEffect, useCallback, useRef } from "react";
import {
    LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend, Area, AreaChart,
} from "recharts";
import { fetchLatest, fetchRange, fetchSummary } from "./api";
import type { LatestResponse, MetricsSample, SummaryResponse } from "./types";

/* ── helpers ─────────────────────────────────────── */

function formatBytes(b: number): string {
    if (b < 1024) return `${b} B`;
    if (b < 1024 ** 2) return `${(b / 1024).toFixed(1)} KB`;
    if (b < 1024 ** 3) return `${(b / 1024 ** 2).toFixed(1)} MB`;
    return `${(b / 1024 ** 3).toFixed(2)} GB`;
}

function formatUptime(s: number | null): string {
    if (s == null) return "—";
    const d = Math.floor(s / 86400);
    const h = Math.floor((s % 86400) / 3600);
    const m = Math.floor((s % 3600) / 60);
    return d > 0 ? `${d}d ${h}h ${m}m` : `${h}h ${m}m`;
}

function shortTime(iso: string): string {
    return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

const TIME_RANGES = [
    { label: "15m", minutes: 15 },
    { label: "1h", minutes: 60 },
    { label: "6h", minutes: 360 },
    { label: "24h", minutes: 1440 },
] as const;

function stepForRange(minutes: number): number {
    if (minutes <= 15) return 2;
    if (minutes <= 60) return 10;
    if (minutes <= 360) return 60;
    return 300;
}

/* ── badge colors ────────────────────────────────── */
const badgeColors: Record<string, string> = {
    OK: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
    WARN: "bg-amber-500/20 text-amber-400 border-amber-500/30",
    CRIT: "bg-red-500/20 text-red-400 border-red-500/30",
};

/* ── chart colors ────────────────────────────────── */
const CHART_COLORS = {
    cpu: "#818cf8",
    mem: "#34d399",
    disk: "#fbbf24",
    rx: "#38bdf8",
    tx: "#f472b6",
};

/* ── tooltip ─────────────────────────────────────── */
function ChartTooltip({ active, payload, label }: any) {
    if (!active || !payload?.length) return null;
    return (
        <div className="bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-xs shadow-xl">
            <p className="text-slate-400 mb-1">{shortTime(label)}</p>
            {payload.map((p: any) => (
                <p key={p.dataKey} style={{ color: p.color }}>
                    {p.name}: {typeof p.value === "number" ? p.value.toFixed(2) : p.value}
                </p>
            ))}
        </div>
    );
}

/* ── summary card ────────────────────────────────── */
function SummaryCard({ title, value, sub, icon }: { title: string; value: string; sub: string; icon: string }) {
    return (
        <div className="bg-slate-800/60 backdrop-blur border border-slate-700/50 rounded-xl p-4 flex flex-col gap-1">
            <div className="flex items-center gap-2 text-slate-400 text-xs font-medium uppercase tracking-wide">
                <span>{icon}</span> {title}
            </div>
            <div className="text-2xl font-bold text-white">{value}</div>
            <div className="text-xs text-slate-400">{sub}</div>
        </div>
    );
}

/* ── main component ──────────────────────────────── */
export default function App() {
    const [latest, setLatest] = useState<LatestResponse | null>(null);
    const [history, setHistory] = useState<MetricsSample[]>([]);
    const [summary, setSummary] = useState<SummaryResponse | null>(null);
    const [range, setRange] = useState(60);
    const [live, setLive] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const liveRef = useRef(live);
    liveRef.current = live;

    // Fetch latest
    const loadLatest = useCallback(async () => {
        try {
            const d = await fetchLatest();
            setLatest(d);
            setError(null);
        } catch (e: any) {
            setError(e.message);
        }
    }, []);

    // Fetch history
    const loadHistory = useCallback(async () => {
        try {
            const now = new Date();
            const from = new Date(now.getTime() - range * 60_000);
            const data = await fetchRange(from.toISOString(), now.toISOString(), stepForRange(range));
            setHistory(data.points);
        } catch { }
    }, [range]);

    // Fetch summary
    const loadSummary = useCallback(async () => {
        try {
            const d = await fetchSummary(range);
            setSummary(d);
        } catch { }
    }, [range]);

    // Initial + range change
    useEffect(() => {
        loadLatest();
        loadHistory();
        loadSummary();
    }, [loadLatest, loadHistory, loadSummary]);

    // Live polling
    useEffect(() => {
        if (!live) return;
        const id = setInterval(() => {
            if (liveRef.current) {
                loadLatest();
                loadHistory();
            }
        }, 2000);
        return () => clearInterval(id);
    }, [live, loadLatest, loadHistory]);

    const machineName = latest ? "System Metrics Monitor" : "System Metrics Monitor";
    const health = latest?.health;

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
            {/* header */}
            <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-10">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 py-4 flex flex-wrap items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-lg">
                            📊
                        </div>
                        <div>
                            <h1 className="text-lg font-bold text-white leading-tight">{machineName}</h1>
                            <p className="text-xs text-slate-400">Real-time host monitoring</p>
                        </div>
                    </div>

                    <div className="flex items-center gap-3">
                        {/* health badge */}
                        {health && (
                            <span className={`px-3 py-1 rounded-full text-xs font-semibold border ${badgeColors[health.overall]}`}>
                                {health.overall}
                            </span>
                        )}

                        {/* time range selector */}
                        <div className="flex bg-slate-800 rounded-lg p-0.5">
                            {TIME_RANGES.map((r) => (
                                <button
                                    key={r.label}
                                    onClick={() => setRange(r.minutes)}
                                    className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all ${range === r.minutes
                                            ? "bg-indigo-600 text-white shadow-lg shadow-indigo-500/20"
                                            : "text-slate-400 hover:text-white"
                                        }`}
                                >
                                    {r.label}
                                </button>
                            ))}
                        </div>

                        {/* live toggle */}
                        <button
                            onClick={() => setLive((v) => !v)}
                            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all border ${live
                                    ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                                    : "bg-slate-800 text-slate-400 border-slate-700"
                                }`}
                        >
                            <span className={`w-2 h-2 rounded-full ${live ? "bg-emerald-400 animate-pulse" : "bg-slate-500"}`} />
                            {live ? "Live" : "Paused"}
                        </button>
                    </div>
                </div>
            </header>

            <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6 space-y-6">
                {error && (
                    <div className="bg-red-500/10 border border-red-500/30 text-red-300 rounded-lg px-4 py-3 text-sm">
                        ⚠️ {error}
                    </div>
                )}

                {/* summary cards */}
                {latest && (
                    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
                        <SummaryCard icon="🖥️" title="CPU" value={`${latest.cpu_percent.toFixed(1)}%`} sub={health?.cpu ?? ""} />
                        <SummaryCard
                            icon="🧠"
                            title="Memory"
                            value={`${latest.mem_percent.toFixed(1)}%`}
                            sub={`${formatBytes(latest.mem_used_bytes)} / ${formatBytes(latest.mem_total_bytes)}`}
                        />
                        <SummaryCard
                            icon="💾"
                            title="Disk"
                            value={`${latest.disk_percent.toFixed(1)}%`}
                            sub={`${formatBytes(latest.disk_used_bytes)} / ${formatBytes(latest.disk_total_bytes)}`}
                        />
                        <SummaryCard icon="🌐" title="Net RX" value={`${formatBytes(latest.net_rx_bps)}/s`} sub="Inbound" />
                        <SummaryCard icon="⏱️" title="Uptime" value={formatUptime(latest.uptime_seconds)} sub="System uptime" />
                    </div>
                )}

                {/* charts */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    {/* CPU Chart */}
                    <div className="bg-slate-800/40 backdrop-blur border border-slate-700/50 rounded-xl p-5">
                        <h2 className="text-sm font-semibold text-slate-300 mb-4">CPU Usage (%)</h2>
                        <ResponsiveContainer width="100%" height={220}>
                            <AreaChart data={history}>
                                <defs>
                                    <linearGradient id="cpuGrad" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor={CHART_COLORS.cpu} stopOpacity={0.3} />
                                        <stop offset="95%" stopColor={CHART_COLORS.cpu} stopOpacity={0} />
                                    </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                                <XAxis dataKey="ts_utc" tickFormatter={shortTime} tick={{ fontSize: 10, fill: "#94a3b8" }} />
                                <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: "#94a3b8" }} />
                                <Tooltip content={<ChartTooltip />} />
                                <Area type="monotone" dataKey="cpu_percent" name="CPU %" stroke={CHART_COLORS.cpu} fill="url(#cpuGrad)" strokeWidth={2} dot={false} />
                            </AreaChart>
                        </ResponsiveContainer>
                    </div>

                    {/* Memory Chart */}
                    <div className="bg-slate-800/40 backdrop-blur border border-slate-700/50 rounded-xl p-5">
                        <h2 className="text-sm font-semibold text-slate-300 mb-4">Memory Usage (%)</h2>
                        <ResponsiveContainer width="100%" height={220}>
                            <AreaChart data={history}>
                                <defs>
                                    <linearGradient id="memGrad" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor={CHART_COLORS.mem} stopOpacity={0.3} />
                                        <stop offset="95%" stopColor={CHART_COLORS.mem} stopOpacity={0} />
                                    </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                                <XAxis dataKey="ts_utc" tickFormatter={shortTime} tick={{ fontSize: 10, fill: "#94a3b8" }} />
                                <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: "#94a3b8" }} />
                                <Tooltip content={<ChartTooltip />} />
                                <Area type="monotone" dataKey="mem_percent" name="Mem %" stroke={CHART_COLORS.mem} fill="url(#memGrad)" strokeWidth={2} dot={false} />
                            </AreaChart>
                        </ResponsiveContainer>
                    </div>

                    {/* Disk Chart */}
                    <div className="bg-slate-800/40 backdrop-blur border border-slate-700/50 rounded-xl p-5">
                        <h2 className="text-sm font-semibold text-slate-300 mb-4">Disk Usage (%)</h2>
                        <ResponsiveContainer width="100%" height={220}>
                            <AreaChart data={history}>
                                <defs>
                                    <linearGradient id="diskGrad" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor={CHART_COLORS.disk} stopOpacity={0.3} />
                                        <stop offset="95%" stopColor={CHART_COLORS.disk} stopOpacity={0} />
                                    </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                                <XAxis dataKey="ts_utc" tickFormatter={shortTime} tick={{ fontSize: 10, fill: "#94a3b8" }} />
                                <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: "#94a3b8" }} />
                                <Tooltip content={<ChartTooltip />} />
                                <Area type="monotone" dataKey="disk_percent" name="Disk %" stroke={CHART_COLORS.disk} fill="url(#diskGrad)" strokeWidth={2} dot={false} />
                            </AreaChart>
                        </ResponsiveContainer>
                    </div>

                    {/* Network Chart */}
                    <div className="bg-slate-800/40 backdrop-blur border border-slate-700/50 rounded-xl p-5">
                        <h2 className="text-sm font-semibold text-slate-300 mb-4">Network (bytes/sec)</h2>
                        <ResponsiveContainer width="100%" height={220}>
                            <LineChart data={history}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                                <XAxis dataKey="ts_utc" tickFormatter={shortTime} tick={{ fontSize: 10, fill: "#94a3b8" }} />
                                <YAxis tick={{ fontSize: 10, fill: "#94a3b8" }} tickFormatter={(v: number) => formatBytes(v)} />
                                <Tooltip content={<ChartTooltip />} />
                                <Legend wrapperStyle={{ fontSize: "12px" }} />
                                <Line type="monotone" dataKey="net_rx_bps" name="RX" stroke={CHART_COLORS.rx} strokeWidth={2} dot={false} />
                                <Line type="monotone" dataKey="net_tx_bps" name="TX" stroke={CHART_COLORS.tx} strokeWidth={2} dot={false} />
                            </LineChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                {/* summary stats */}
                {summary && (
                    <div className="bg-slate-800/40 backdrop-blur border border-slate-700/50 rounded-xl p-5">
                        <h2 className="text-sm font-semibold text-slate-300 mb-4">Summary — last {range} minutes</h2>
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="text-slate-400 text-xs uppercase tracking-wide">
                                        <th className="text-left py-2 pr-4">Metric</th>
                                        <th className="text-right py-2 px-4">Min</th>
                                        <th className="text-right py-2 px-4">Avg</th>
                                        <th className="text-right py-2 px-4">Max</th>
                                    </tr>
                                </thead>
                                <tbody className="text-slate-200">
                                    {[
                                        { name: "CPU %", f: summary.cpu_percent },
                                        { name: "Mem %", f: summary.mem_percent },
                                        { name: "Disk %", f: summary.disk_percent },
                                        { name: "Net RX (B/s)", f: summary.net_rx_bps },
                                        { name: "Net TX (B/s)", f: summary.net_tx_bps },
                                    ].map((r) => (
                                        <tr key={r.name} className="border-t border-slate-700/50">
                                            <td className="py-2 pr-4 font-medium">{r.name}</td>
                                            <td className="text-right py-2 px-4">{r.f.min.toFixed(2)}</td>
                                            <td className="text-right py-2 px-4">{r.f.avg.toFixed(2)}</td>
                                            <td className="text-right py-2 px-4">{r.f.max.toFixed(2)}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}
            </main>

            <footer className="border-t border-slate-800 py-4 text-center text-xs text-slate-500">
                System Metrics Monitor V1
            </footer>
        </div>
    );
}
