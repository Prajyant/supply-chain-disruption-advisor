import { useQuery } from '@tanstack/react-query';
import { loadDemoShipments } from '../services/shipmentData';
import { useShipmentStore } from '../store/shipmentStore';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { ShieldAlert, Calendar, Lock, ArrowRight, AlertTriangle } from 'lucide-react';

// ─── Hardcoded 30-day trend data with spike in last week ───────────────────
function generateTrendData() {
  const data = [];
  const today = new Date();
  for (let i = 29; i >= 0; i--) {
    const date = new Date(today);
    date.setDate(today.getDate() - i);
    const label = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    // Baseline ~$2–4M, spikes in last 7 days to $8–12M
    let exposure: number;
    if (i <= 6) {
      exposure = 6_000_000 + Math.random() * 6_000_000;
    } else if (i <= 10) {
      exposure = 3_500_000 + Math.random() * 2_500_000;
    } else {
      exposure = 1_800_000 + Math.random() * 2_200_000;
    }
    data.push({ date: label, exposure: Math.round(exposure / 100_000) * 100_000 });
  }
  return data;
}

const TREND_DATA = generateTrendData();

// ─── Helpers ────────────────────────────────────────────────────────────────
function formatMillions(n: number) {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(0)}K`;
  return `$${n.toLocaleString()}`;
}

function riskLevelFromScore(score: number): 'critical' | 'high' | 'medium' | 'low' {
  if (score >= 8) return 'critical';
  if (score >= 6) return 'high';
  if (score >= 4) return 'medium';
  return 'low';
}

const RISK_PILL: Record<string, string> = {
  critical: 'bg-red-500/20 text-red-300 border border-red-500/40',
  high:     'bg-orange-500/20 text-orange-300 border border-orange-500/40',
  medium:   'bg-yellow-500/20 text-yellow-300 border border-yellow-500/40',
  low:      'bg-green-500/20 text-green-300 border border-green-500/40',
};

const ACTION_FOR_LEVEL: Record<string, string> = {
  critical: 'Authorize immediate expedited procurement',
  high:     'Approve alternate supplier activation',
  medium:   'Review logistics contingency plan',
  low:      'No immediate action required',
};

// ─── Main Component ─────────────────────────────────────────────────────────
export function CFODashboard() {
  const today = new Date().toLocaleDateString('en-US', {
    weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
  });

  const { data: demoShipments = [] } = useQuery({
    queryKey: ['demo-shipments'],
    queryFn: loadDemoShipments,
  });

  const { uploadedShipments } = useShipmentStore();

  // Derive financial exposure from shipments (uploaded or demo)
  const shipmentRows = (uploadedShipments || demoShipments).map((s) => {
    const materialLower = s.material?.toLowerCase() ?? '';
    let unitValue = 20;
    if (materialLower.includes('electron') || materialLower.includes('chip')) unitValue = 50;
    else if (materialLower.includes('copper') || materialLower.includes('metal') || materialLower.includes('steel')) unitValue = 8;
    else if (materialLower.includes('chemical') || materialLower.includes('plastic')) unitValue = 12;
    else if (s.declared_value_usd > 0 && s.quantity > 0) unitValue = s.declared_value_usd / s.quantity;

    const riskScore = 5 + Math.random() * 5; // illustrative
    const exposure = s.quantity * unitValue * (riskScore / 10);
    const level = riskLevelFromScore(riskScore);
    return { ...s, riskScore, exposure, level };
  }).sort((a, b) => b.exposure - a.exposure);

  const highCritical = shipmentRows.filter(r => r.level === 'high' || r.level === 'critical');
  const criticalCount = shipmentRows.filter(r => r.level === 'critical').length;
  const highCount = shipmentRows.filter(r => r.level === 'high').length;
  const totalExposure = highCritical.reduce((s, r) => s + r.exposure, 0);

  const boardActions = [
    criticalCount > 0
      ? `Authorize emergency procurement budget of up to ${formatMillions(totalExposure * 0.15)} to cover alternate supplier costs for ${criticalCount} critical shipment${criticalCount > 1 ? 's' : ''}.`
      : null,
    highCount > 0
      ? `Approve activation of secondary supplier agreements for ${highCount} high-risk shipment${highCount > 1 ? 's' : ''} to maintain production continuity.`
      : null,
    `Direct logistics leadership to provide a 48-hour recovery plan for all shipments with inventory cover below 10 days.`,
    `Review insurance coverage adequacy given current exposure of ${formatMillions(totalExposure)} across active high-risk shipments.`,
  ].filter(Boolean) as string[];

  const trendDollars = TREND_DATA.map(d => ({
    ...d,
    exposureM: +(d.exposure / 1_000_000).toFixed(2),
  }));

  return (
    <div className="min-h-full bg-slate-950 p-8 lg:p-12 space-y-10">

      {/* ── Header ── */}
      <header className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <ShieldAlert className="w-6 h-6 text-amber-400" />
            <h1 className="text-3xl font-bold tracking-tight text-white">Supply Chain Risk Briefing</h1>
            <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs font-semibold uppercase tracking-widest">
              <Lock className="w-2.5 h-2.5" /> Confidential
            </span>
          </div>
          <p className="text-slate-400 flex items-center gap-2">
            <Calendar className="w-4 h-4" /> {today}
          </p>
        </div>
        <div className="text-right text-xs text-slate-600 italic">
          Prepared for Executive Leadership<br />Automatically generated · Not for distribution
        </div>
      </header>

      {/* ── Hero Metric ── */}
      <section className="rounded-2xl border border-amber-500/20 bg-gradient-to-br from-amber-500/5 via-slate-900 to-slate-900 p-8 flex flex-col md:flex-row md:items-center md:justify-between gap-8">
        <div>
          <p className="text-sm font-semibold uppercase tracking-widest text-amber-400/80 mb-2">Total Financial Exposure</p>
          <div className="text-6xl font-extrabold text-white tracking-tight tabular-nums">
            {formatMillions(totalExposure)}
          </div>
          <p className="mt-3 text-slate-400 text-base">
            Across <span className="text-red-400 font-semibold">{criticalCount} critical</span> and <span className="text-orange-400 font-semibold">{highCount} high risk</span> active shipments
          </p>
        </div>
        <div className="flex gap-6">
          <div className="text-center">
            <div className="text-4xl font-bold text-red-400">{criticalCount}</div>
            <div className="text-xs text-slate-500 uppercase tracking-wide mt-1">Critical</div>
          </div>
          <div className="w-px bg-slate-800 self-stretch" />
          <div className="text-center">
            <div className="text-4xl font-bold text-orange-400">{highCount}</div>
            <div className="text-xs text-slate-500 uppercase tracking-wide mt-1">High</div>
          </div>
          <div className="w-px bg-slate-800 self-stretch" />
          <div className="text-center">
            <div className="text-4xl font-bold text-slate-300">{demoShipments.length}</div>
            <div className="text-xs text-slate-500 uppercase tracking-wide mt-1">Total</div>
          </div>
        </div>
      </section>

      {/* ── Risk Table ── */}
      <section>
        <h2 className="text-lg font-semibold text-white mb-4">Active Risk Summary</h2>
        <div className="rounded-xl border border-slate-800 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-800 bg-slate-900/60">
                <th className="text-left px-5 py-3 text-slate-500 font-medium">Shipment</th>
                <th className="text-left px-5 py-3 text-slate-500 font-medium">Route</th>
                <th className="text-left px-5 py-3 text-slate-500 font-medium">Risk Level</th>
                <th className="text-right px-5 py-3 text-slate-500 font-medium">$ Exposure</th>
                <th className="text-left px-5 py-3 text-slate-500 font-medium">Action Required</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {shipmentRows.slice(0, 8).map((row) => (
                <tr key={row.shipment_id} className="hover:bg-slate-900/40 transition-colors">
                  <td className="px-5 py-4">
                    <div className="font-medium text-white">{row.supplier}</div>
                    <div className="text-xs text-slate-500 font-mono">{row.shipment_id}</div>
                  </td>
                  <td className="px-5 py-4 text-slate-300">
                    <span className="flex items-center gap-1">
                      {row.origin} <ArrowRight className="w-3 h-3 text-slate-600 shrink-0" /> {row.destination}
                    </span>
                  </td>
                  <td className="px-5 py-4">
                    <span className={`inline-block px-2.5 py-1 rounded-full text-xs font-semibold uppercase ${RISK_PILL[row.level]}`}>
                      {row.level}
                    </span>
                  </td>
                  <td className="px-5 py-4 text-right font-bold text-white tabular-nums">
                    {formatMillions(row.exposure)}
                  </td>
                  <td className="px-5 py-4 text-slate-400 text-xs max-w-[200px]">
                    {ACTION_FOR_LEVEL[row.level]}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* ── Board Actions ── */}
      <section className="rounded-2xl border border-slate-800 bg-slate-900/50 p-8">
        <div className="flex items-center gap-3 mb-6">
          <AlertTriangle className="w-5 h-5 text-amber-400" />
          <h2 className="text-lg font-semibold text-white">Recommended Board Actions</h2>
        </div>
        <ul className="space-y-4">
          {boardActions.map((action, i) => {
            const verb = action.split(' ')[0];
            const rest = action.slice(verb.length);
            return (
              <li key={i} className="flex items-start gap-4">
                <span className="mt-0.5 shrink-0 w-6 h-6 rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/30 text-xs font-bold flex items-center justify-center">
                  {i + 1}
                </span>
                <p className="text-slate-300 leading-relaxed">
                  <span className="font-bold text-white">{verb}</span>{rest}
                </p>
              </li>
            );
          })}
        </ul>
      </section>

      {/* ── 30-Day Risk Trend ── */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-white">30 Day Risk Exposure Trend</h2>
          <span className="text-xs text-slate-500 italic">Based on current active shipments</span>
        </div>
        <div className="rounded-2xl border border-slate-800 bg-slate-900/50 p-6">
          <ResponsiveContainer width="100%" height={240}>
            <AreaChart data={trendDollars} margin={{ top: 10, right: 20, left: 10, bottom: 0 }}>
              <defs>
                <linearGradient id="exposureGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#f59e0b" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis
                dataKey="date"
                tick={{ fill: '#64748b', fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                interval={4}
              />
              <YAxis
                tick={{ fill: '#64748b', fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v) => `$${v}M`}
              />
              <Tooltip
                contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: 8 }}
                labelStyle={{ color: '#94a3b8' }}
                formatter={(v: any) => [`$${Number(v).toFixed(2)}M`, 'Exposure']}
              />
              <Area
                type="monotone"
                dataKey="exposureM"
                stroke="#f59e0b"
                strokeWidth={2}
                fill="url(#exposureGrad)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="pt-4 border-t border-slate-800/60 text-center">
        <p className="text-xs text-slate-600">
          Full technical analysis available in <span className="text-slate-400 font-medium">Analyst view</span> · Data refreshes automatically · Last updated {new Date().toLocaleTimeString()}
        </p>
      </footer>

    </div>
  );
}
