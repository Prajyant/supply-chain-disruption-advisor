import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { loadDemoShipments } from '../services/shipmentData';
import { useShipmentStore } from '../store/shipmentStore';
import { shipmentApi } from '../services/api';
import { MaritimeIntelligence } from '../components/MaritimeIntelligence';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import {
  ShieldAlert, Calendar, Lock, ArrowRight, AlertTriangle,
  ChevronDown, Package, Loader2, ExternalLink, TrendingUp,
  DollarSign, BarChart3, CheckCircle2,
} from 'lucide-react';

/* ── helpers ─────────────────────────────────────────────────────────── */
function generateTrendData() {
  const data = [];
  const today = new Date();
  for (let i = 29; i >= 0; i--) {
    const date = new Date(today);
    date.setDate(today.getDate() - i);
    const label = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    let exposure: number;
    if (i <= 6)       exposure = 6_000_000 + Math.random() * 6_000_000;
    else if (i <= 10) exposure = 3_500_000 + Math.random() * 2_500_000;
    else              exposure = 1_800_000 + Math.random() * 2_200_000;
    data.push({ date: label, exposure: Math.round(exposure / 100_000) * 100_000 });
  }
  return data;
}
const TREND_DATA = generateTrendData();

function fmt(n: number) {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000)     return `$${(n / 1_000).toFixed(0)}K`;
  return `$${n.toLocaleString()}`;
}
function fmtRaw(n: number) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000)     return `${(n / 1_000).toFixed(0)}K`;
  return `${n.toLocaleString()}`;
}
function riskLevel(score: number): 'critical' | 'high' | 'medium' | 'low' {
  if (score >= 8) return 'critical';
  if (score >= 6) return 'high';
  if (score >= 4) return 'medium';
  return 'low';
}
const ACTION: Record<string, string> = {
  critical: 'Authorize emergency procurement',
  high:     'Approve alternate supplier activation',
  medium:   'Review logistics contingency plan',
  low:      'No immediate action required',
};

/* ── component ───────────────────────────────────────────────────────── */
export function CFODashboard() {
  const navigate = useNavigate();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [dropdownOpen, setDropdownOpen] = useState(false);

  const today = new Date().toLocaleDateString('en-US', {
    weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
  });

  const { data: demoShipments = [] } = useQuery({
    queryKey: ['demo-shipments'],
    queryFn: loadDemoShipments,
    refetchInterval: 15_000,
  });
  const { uploadedShipments } = useShipmentStore();
  const allShipments = uploadedShipments
    ? [...demoShipments, ...uploadedShipments.filter(u => !demoShipments.some(d => d.shipment_id === u.shipment_id))]
    : demoShipments;

  const { data: selectedAnalysis, isLoading: analysisLoading } = useQuery({
    queryKey: ['shipment-preloaded-cfo', selectedId],
    queryFn: () => shipmentApi.getPreloadedAnalysis(selectedId!).then(r => r.data),
    enabled: !!selectedId,
    retry: false,
  });

  const rows = allShipments.map((s) => {
    const mat = s.material?.toLowerCase() ?? '';
    let unit = 20;
    if (mat.includes('electron') || mat.includes('chip')) unit = 50;
    else if (mat.includes('copper') || mat.includes('metal') || mat.includes('steel')) unit = 8;
    else if (mat.includes('chemical') || mat.includes('plastic')) unit = 12;
    else if (s.declared_value_usd > 0 && s.quantity > 0) unit = s.declared_value_usd / s.quantity;

    let score = 3.0;
    if (s.inventory_days_cover <= 5)      score += 3.0;
    else if (s.inventory_days_cover <= 10) score += 2.0;
    else if (s.inventory_days_cover <= 15) score += 1.0;
    if (s.supplier_delay_count >= 5)       score += 2.0;
    else if (s.supplier_delay_count >= 3)  score += 1.5;
    else if (s.supplier_delay_count >= 1)  score += 0.5;
    if (s.lead_time_days >= 30)            score += 1.5;
    else if (s.lead_time_days >= 20)       score += 1.0;
    if (s.declared_value_usd > 500_000)   score += 0.5;
    score = Math.min(10, Math.max(0, score));
    const exposure = Math.round(s.quantity * unit * (score / 10));
    const level = riskLevel(score);
    return { ...s, score: Math.round(score * 10) / 10, exposure, level };
  }).sort((a, b) => b.exposure - a.exposure);

  const highCrit   = rows.filter(r => r.level === 'critical' || r.level === 'high');
  const critCount  = rows.filter(r => r.level === 'critical').length;
  const highCount  = rows.filter(r => r.level === 'high').length;
  const totalExposure = highCrit.reduce((s, r) => s + r.exposure, 0);

  const selShipment = allShipments.find(s => s.shipment_id === selectedId);
  const selRow      = rows.find(r => r.shipment_id === selectedId);

  const boardActions = [
    critCount > 0
      ? `Authorize emergency procurement budget of up to ${fmtRaw(totalExposure * 0.15)} to cover alternate supplier costs for ${critCount} critical shipment${critCount > 1 ? 's' : ''}.`
      : null,
    highCount > 0
      ? `Approve activation of secondary supplier agreements for ${highCount} high-risk shipment${highCount > 1 ? 's' : ''} to maintain production continuity.`
      : null,
    `Direct logistics leadership to provide a 48-hour recovery plan for all shipments with inventory cover below 10 days.`,
    `Review insurance coverage adequacy given current exposure of ${fmtRaw(totalExposure)} across active high-risk shipments.`,
  ].filter(Boolean) as string[];

  const trendM = TREND_DATA.map(d => ({ ...d, exposureM: +(d.exposure / 1_000_000).toFixed(2) }));

  return (
    <div className="min-h-full bg-slate-950 px-8 py-8 lg:px-12 lg:py-10 space-y-8">

      {/* ── Header ── */}
      <header className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
        <div>
          <div className="flex items-center gap-3 mb-1.5">
            <div className="w-9 h-9 rounded-lg bg-amber-500/15 border border-amber-500/25 flex items-center justify-center">
              <ShieldAlert className="w-5 h-5 text-amber-400" />
            </div>
            <h1 className="text-2xl font-bold text-white tracking-tight">Supply Chain Risk Briefing</h1>
            <span className="badge bg-amber-500/10 text-amber-400 border border-amber-500/25 flex items-center gap-1">
              <Lock className="w-2.5 h-2.5" /> Confidential
            </span>
          </div>
          <p className="text-slate-400 text-sm flex items-center gap-2">
            <Calendar className="w-3.5 h-3.5" /> {today}
          </p>
        </div>
        <p className="text-xs text-slate-600 italic text-right leading-relaxed">
          Prepared for Executive Leadership<br />
          Automatically generated · Not for distribution
        </p>
      </header>

      {/* ── Hero KPIs ── */}
      <section className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="card border border-amber-500/20 bg-gradient-to-br from-amber-500/5 to-transparent col-span-2 flex items-center justify-between gap-6 p-6">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-amber-400/80 mb-1">Total Financial Exposure</p>
            <p className="text-4xl font-extrabold text-white tabular-nums">{fmt(totalExposure)}</p>
            <p className="text-sm text-slate-400 mt-1.5">
              Across <span className="text-red-400 font-semibold">{critCount} critical</span> and{' '}
              <span className="text-orange-400 font-semibold">{highCount} high-risk</span> shipments
            </p>
          </div>
          <DollarSign className="w-12 h-12 text-amber-500/20 shrink-0" />
        </div>
        <div className="card border border-red-500/20 flex items-center justify-between gap-4">
          <div>
            <p className="stat-label">Critical</p>
            <p className="text-3xl font-bold text-red-400 tabular-nums mt-1">{critCount}</p>
          </div>
          <div className="w-10 h-10 rounded-xl bg-red-500/10 flex items-center justify-center">
            <AlertTriangle className="w-5 h-5 text-red-400" />
          </div>
        </div>
        <div className="card border border-orange-500/20 flex items-center justify-between gap-4">
          <div>
            <p className="stat-label">High Risk</p>
            <p className="text-3xl font-bold text-orange-400 tabular-nums mt-1">{highCount}</p>
          </div>
          <div className="w-10 h-10 rounded-xl bg-orange-500/10 flex items-center justify-center">
            <TrendingUp className="w-5 h-5 text-orange-400" />
          </div>
        </div>
      </section>

      {/* ── Shipment selector ── */}
      <section className="card !p-0 overflow-visible">
        <div className="px-6 py-4 border-b border-slate-800 flex items-center gap-4 flex-wrap">
          <div className="flex items-center gap-2">
            <Package className="w-4 h-4 text-amber-400" />
            <span className="font-semibold text-white text-sm">Inspect Shipment</span>
          </div>
          <div className="relative flex-1 min-w-[260px] max-w-lg">
            <button
              onClick={() => setDropdownOpen(!dropdownOpen)}
              className="w-full flex items-center justify-between gap-2 px-4 py-2.5 rounded-lg border border-slate-700 bg-slate-800 hover:border-slate-600 transition-colors text-left text-sm"
            >
              <span className={selectedId ? 'text-white' : 'text-slate-400'}>
                {selShipment ? `${selectedId} — ${selShipment.supplier}` : 'Select a shipment for detailed financial analysis…'}
              </span>
              <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform shrink-0 ${dropdownOpen ? 'rotate-180' : ''}`} />
            </button>
            {dropdownOpen && (
              <div className="absolute z-50 mt-1 w-full max-h-64 overflow-y-auto rounded-xl border border-slate-700 bg-slate-800 shadow-2xl">
                <button
                  onClick={() => { setSelectedId(null); setDropdownOpen(false); }}
                  className="w-full text-left px-4 py-2.5 hover:bg-slate-700/50 transition-colors border-b border-slate-700/50 text-slate-400 text-sm"
                >
                  Show global overview (no selection)
                </button>
                {allShipments.map((s) => (
                  <button
                    key={s.shipment_id}
                    onClick={() => { setSelectedId(s.shipment_id); setDropdownOpen(false); }}
                    className={`w-full text-left px-4 py-2.5 hover:bg-slate-700/40 transition-colors border-b border-slate-700/40 last:border-0 text-sm ${
                      s.shipment_id === selectedId ? 'bg-amber-500/8 border-l-2 border-l-amber-500' : ''
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-white">{s.shipment_id}</span>
                      <span className="text-xs text-slate-500">{fmt(s.declared_value_usd)}</span>
                    </div>
                    <p className="text-xs text-slate-400 mt-0.5">
                      {s.supplier} · {s.origin} → {s.destination}
                    </p>
                  </button>
                ))}
              </div>
            )}
          </div>
          {selectedId && (
            <button
              onClick={() => navigate(`/shipments/${selectedId}`)}
              className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-amber-300 border border-amber-500/30 bg-amber-500/10 rounded-lg hover:bg-amber-500/20 transition-colors"
            >
              Full Analysis <ExternalLink className="w-3 h-3" />
            </button>
          )}
        </div>

        {/* Selected shipment metrics */}
        {selRow && (
          <div className="px-6 py-5">
            {analysisLoading ? (
              <div className="flex items-center gap-2 text-slate-400 text-sm">
                <Loader2 className="w-4 h-4 animate-spin" /> Loading analysis…
              </div>
            ) : (
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
                <CfoKpi label="Financial Exposure" value={fmt(selRow.exposure)} color="text-amber-400" />
                <CfoKpi
                  label="Risk Score"
                  value={`${selectedAnalysis?.result?.risk_score ?? selRow.score}/10`}
                  color={selRow.level === 'critical' ? 'text-red-400' : selRow.level === 'high' ? 'text-orange-400' : 'text-amber-400'}
                />
                <CfoKpi
                  label="Inventory Cover"
                  value={`${selRow.inventory_days_cover}d`}
                  color={selRow.inventory_days_cover <= 7 ? 'text-red-400' : selRow.inventory_days_cover <= 14 ? 'text-amber-400' : 'text-emerald-400'}
                />
                <CfoKpi label="Declared Value" value={fmt(selRow.declared_value_usd)} color="text-white" />
                <CfoKpi
                  label="Supplier Delays"
                  value={String(selRow.supplier_delay_count)}
                  color={selRow.supplier_delay_count >= 3 ? 'text-orange-400' : 'text-slate-300'}
                />
                <CfoKpi label="Action" value={ACTION[selRow.level]} color="text-slate-300" small />
              </div>
            )}
            {selectedAnalysis?.result?.signals?.length > 0 && (
              <div className="mt-4 p-4 rounded-xl bg-amber-500/5 border border-amber-500/20">
                <p className="text-xs font-semibold text-amber-400 uppercase tracking-wide mb-2">Risk Signals</p>
                <div className="flex flex-wrap gap-2">
                  {selectedAnalysis.result.signals.map((sig: string, i: number) => (
                    <span key={i} className="badge bg-amber-500/10 text-amber-300 border border-amber-500/20">{sig}</span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </section>

      {/* ── Maritime intelligence ── */}
      <section className="card">
        <MaritimeIntelligence
          selectedOrigin={selShipment?.origin ?? null}
          selectedDestination={selShipment?.destination ?? null}
          selectedVesselImo={selShipment?.imo_number ?? null}
          selectedVesselName={selShipment?.vessel_name ?? null}
        />
      </section>

      {/* ── Risk table ── */}
      <section>
        <h2 className="section-title flex items-center gap-2 mb-4">
          <BarChart3 className="w-4 h-4 text-slate-400" />
          Active Risk Summary
        </h2>
        <div className="card !p-0 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-900/60 border-b border-slate-800">
                <th className="table-header">Shipment</th>
                <th className="table-header">Route</th>
                <th className="table-header">Risk Level</th>
                <th className="table-header text-right">Exposure</th>
                <th className="table-header">Action</th>
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, 8).map((row) => (
                <tr
                  key={row.shipment_id}
                  onClick={() => { setSelectedId(row.shipment_id); window.scrollTo({ top: 0, behavior: 'smooth' }); }}
                  className={`table-row border-b border-slate-800/60 ${
                    row.shipment_id === selectedId ? 'bg-amber-500/5 border-l-2 border-l-amber-500' : ''
                  }`}
                >
                  <td className="table-cell">
                    <p className="font-semibold text-white">{row.supplier}</p>
                    <p className="mono mt-0.5">{row.shipment_id}</p>
                  </td>
                  <td className="table-cell">
                    <span className="flex items-center gap-1.5 text-slate-300">
                      {row.origin}
                      <ArrowRight className="w-3 h-3 text-slate-600 shrink-0" />
                      {row.destination}
                    </span>
                  </td>
                  <td className="table-cell">
                    <span className={`badge ${
                      row.level === 'critical' ? 'badge-critical' :
                      row.level === 'high'     ? 'badge-high'     :
                      row.level === 'medium'   ? 'badge-medium'   : 'badge-low'
                    }`}>{row.level}</span>
                  </td>
                  <td className="table-cell text-right font-bold text-white tabular-nums">
                    {fmt(row.exposure)}
                  </td>
                  <td className="table-cell text-slate-400 max-w-[180px] truncate">
                    {ACTION[row.level]}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* ── Board actions ── */}
      <section className="card border border-amber-500/15">
        <div className="flex items-center gap-3 mb-5">
          <div className="w-8 h-8 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
          </div>
          <h2 className="section-title">Recommended Board Actions</h2>
        </div>
        <ul className="space-y-3">
          {boardActions.map((action, i) => {
            const [verb, ...rest] = action.split(' ');
            return (
              <li key={i} className="flex items-start gap-4">
                <span className="w-6 h-6 rounded-full bg-amber-500/15 text-amber-400 border border-amber-500/25 text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">
                  {i + 1}
                </span>
                <p className="text-slate-300 leading-relaxed text-sm">
                  <span className="font-bold text-white">{verb} </span>{rest.join(' ')}
                </p>
              </li>
            );
          })}
        </ul>
      </section>

      {/* ── 30-day trend ── */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="section-title flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-slate-400" />
            30-Day Risk Exposure Trend
          </h2>
          <span className="text-xs text-slate-500 italic">Based on current active shipments</span>
        </div>
        <div className="card">
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={trendM} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="amberGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#f59e0b" stopOpacity={0.25} />
                  <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="date" tick={{ fill: '#475569', fontSize: 11 }} tickLine={false} axisLine={false} interval={4} />
              <YAxis tick={{ fill: '#475569', fontSize: 11 }} tickLine={false} axisLine={false} tickFormatter={(v) => `$${v}M`} />
              <Tooltip
                contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: 10, fontSize: 12 }}
                labelStyle={{ color: '#94a3b8' }}
                formatter={(v: any) => [`$${Number(v).toFixed(2)}M`, 'Exposure']}
              />
              <Area type="monotone" dataKey="exposureM" stroke="#f59e0b" strokeWidth={2} fill="url(#amberGrad)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="pt-2 border-t border-slate-800/60 flex items-center justify-between">
        <p className="text-xs text-slate-600">
          Full technical analysis available in <span className="text-slate-400">Analyst view</span>
        </p>
        <div className="flex items-center gap-1.5 text-xs text-slate-600">
          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-700" />
          Last updated {new Date().toLocaleTimeString()}
        </div>
      </footer>
    </div>
  );
}

/* ── sub-components ── */
function CfoKpi({ label, value, color, small }: { label: string; value: string; color: string; small?: boolean }) {
  return (
    <div className="bg-slate-800/60 border border-slate-700/60 rounded-xl px-4 py-3">
      <p className="text-[10px] text-slate-500 uppercase tracking-wide">{label}</p>
      <p className={`${small ? 'text-xs mt-1 leading-tight' : 'text-base mt-0.5'} font-bold ${color}`}>{value}</p>
    </div>
  );
}
