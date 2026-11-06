import { useQuery } from '@tanstack/react-query';
import { ExternalLink, Newspaper, RefreshCw, Waves, Wind } from 'lucide-react';
import { getLiveIntelligence, type IntelligenceEvent } from '../services/intelligenceApi';
import { getPositionWeather } from '../services/weatherService';
import type { VesselStatus } from '../types/vessel';

interface LiveIntelligencePanelProps {
  vessel: VesselStatus | null;
}

function severityClass(severity: string): string {
  switch (severity.toLowerCase()) {
    case 'critical': return 'border-red-500/40 bg-red-500/10 text-red-300';
    case 'high': return 'border-orange-500/40 bg-orange-500/10 text-orange-300';
    case 'medium': return 'border-yellow-500/40 bg-yellow-500/10 text-yellow-300';
    default: return 'border-sky-500/30 bg-sky-500/10 text-sky-300';
  }
}

function signalLabel(event: IntelligenceEvent): string {
  if (event.source.includes('weather') || event.source.includes('marine')) return 'Weather';
  if (event.source.includes('trade')) return 'Trade';
  return 'News';
}

export function LiveIntelligencePanel({ vessel }: LiveIntelligencePanelProps) {
  const news = useQuery({
    queryKey: ['live-intelligence'],
    queryFn: () => getLiveIntelligence(),
    staleTime: 2 * 60 * 1000,
    refetchInterval: 5 * 60 * 1000,
  });
  const hasPosition = vessel !== null && Number.isFinite(vessel.latitude) && Number.isFinite(vessel.longitude);
  const conditions = useQuery({
    queryKey: ['map-vessel-weather', vessel?.imo_number, vessel?.latitude, vessel?.longitude],
    queryFn: () => getPositionWeather(vessel!.latitude, vessel!.longitude),
    enabled: hasPosition,
    staleTime: 3 * 60 * 1000,
    refetchInterval: 5 * 60 * 1000,
  });

  return (
    <aside className="w-[22rem] overflow-hidden rounded-xl border border-slate-700/80 bg-slate-950/95 shadow-2xl backdrop-blur">
      <div className="flex items-center justify-between border-b border-slate-800 px-4 py-3">
        <div className="flex items-center gap-2 text-sm font-semibold text-white">
          <Newspaper className="h-4 w-4 text-cyan-300" />
          Live Intelligence
        </div>
        <span className="flex items-center gap-1 text-[10px] font-medium uppercase tracking-wider text-emerald-400">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" /> Live
        </span>
      </div>

      {vessel && conditions.data && (
        <div className="border-b border-slate-800 bg-slate-900/60 px-4 py-3">
          <p className="mb-2 truncate text-xs font-medium text-slate-200">Conditions near {vessel.name}</p>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="rounded bg-slate-800/80 px-2 py-1.5 text-slate-300">
              <span className="flex items-center gap-1 text-slate-500"><Wind className="h-3 w-3" /> Wind</span>
              {conditions.data.weather?.wind_speed_kmh.toFixed(0) ?? '—'} km/h
            </div>
            <div className="rounded bg-slate-800/80 px-2 py-1.5 text-slate-300">
              <span className="flex items-center gap-1 text-slate-500"><Waves className="h-3 w-3" /> Waves</span>
              {conditions.data.marine?.wave_height_m.toFixed(1) ?? '—'} m
            </div>
          </div>
        </div>
      )}

      <div className="max-h-[calc(100vh-19rem)] overflow-y-auto p-2">
        {news.isLoading && <p className="p-3 text-xs text-slate-500">Loading live signals…</p>}
        {news.isError && <p className="p-3 text-xs text-amber-400">Live feed is temporarily unavailable.</p>}
        {news.data?.events.map((event) => (
          <article key={`${event.id}-${event.source}`} className="rounded-lg p-2.5 hover:bg-slate-900">
            <div className="mb-1 flex items-center gap-2">
              <span className={`rounded border px-1.5 py-0.5 text-[10px] font-semibold ${severityClass(event.severity)}`}>
                {signalLabel(event)}
              </span>
              {event.location && <span className="truncate text-[10px] text-slate-500">{event.location}</span>}
            </div>
            <p className="line-clamp-2 text-xs font-medium leading-5 text-slate-200">{event.title}</p>
            {event.url && (
              <a className="mt-1 inline-flex items-center gap-1 text-[10px] text-cyan-400 hover:text-cyan-300" href={event.url} target="_blank" rel="noreferrer">
                Source <ExternalLink className="h-2.5 w-2.5" />
              </a>
            )}
          </article>
        ))}
      </div>

      <div className="flex items-center gap-1 border-t border-slate-800 px-4 py-2 text-[10px] text-slate-500">
        <RefreshCw className="h-3 w-3" /> RSS, weather &amp; trade signals refresh automatically
      </div>
    </aside>
  );
}
