import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import {
  CloudSun,
  Waves,
  Wind,
  Thermometer,
  Droplets,
  AlertTriangle,
  Navigation,
  ChevronDown,
} from 'lucide-react';
import { getPositionWeather, type PositionWeatherData } from '../services/weatherService';

interface LiveWeatherBannerProps {
  latitude: number | null | undefined;
  longitude: number | null | undefined;
  vesselName?: string;
  transportMode?: string;
}

const WEATHER_EMOJIS: Record<number, string> = {
  0: '☀️', 1: '🌤️', 2: '⛅', 3: '☁️',
  45: '🌫️', 48: '🌫️',
  51: '🌦️', 53: '🌦️', 55: '🌧️',
  56: '🧊', 57: '🧊',
  61: '🌧️', 63: '🌧️', 65: '🌧️',
  66: '🧊', 67: '🧊',
  71: '🌨️', 73: '🌨️', 75: '❄️', 77: '❄️',
  80: '🌦️', 81: '🌧️', 82: '⛈️',
  85: '🌨️', 86: '❄️',
  95: '⛈️', 96: '⛈️', 99: '⛈️',
};

function getWeatherEmoji(code: number | null): string {
  if (code === null) return '🌤️';
  return WEATHER_EMOJIS[code] ?? '🌤️';
}

function severityColor(severity: string) {
  switch (severity) {
    case 'critical': return { bg: 'bg-red-500/10', border: 'border-red-500/30', text: 'text-red-300', dot: 'bg-red-400', glow: 'shadow-red-500/20' };
    case 'high': return { bg: 'bg-orange-500/10', border: 'border-orange-500/30', text: 'text-orange-300', dot: 'bg-orange-400', glow: 'shadow-orange-500/20' };
    case 'medium': return { bg: 'bg-yellow-500/10', border: 'border-yellow-500/30', text: 'text-yellow-300', dot: 'bg-yellow-400', glow: 'shadow-yellow-500/20' };
    default: return { bg: 'bg-green-500/10', border: 'border-green-500/30', text: 'text-green-300', dot: 'bg-green-400', glow: 'shadow-green-500/10' };
  }
}

function worstSeverity(data: PositionWeatherData): string {
  const levels = ['low', 'medium', 'high', 'critical'];
  const ws = data.weather?.severity ?? 'low';
  const ms = data.marine?.severity ?? 'low';
  return levels.indexOf(ws) >= levels.indexOf(ms) ? ws : ms;
}

export function LiveWeatherBanner({ latitude, longitude, vesselName, transportMode = 'sea' }: LiveWeatherBannerProps) {
  const hasPosition = typeof latitude === 'number' && typeof longitude === 'number';
  const [expanded, setExpanded] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ['position-weather', latitude, longitude],
    queryFn: () => getPositionWeather(latitude!, longitude!),
    enabled: hasPosition,
    staleTime: 3 * 60 * 1000,
    refetchInterval: 5 * 60 * 1000,
  });

  if (!hasPosition || isLoading || !data) {
    return null;
  }

  const weather = data.weather ?? {
    temperature_c: null,
    wind_speed_kmh: 0,
    wind_gusts_kmh: 0,
    precipitation_mm: 0,
    weather_code: 2,
    weather_description: 'Partly cloudy',
    severity: 'low' as const,
  };
  const marine = data.marine ?? {
    wave_height_m: 0,
    wind_wave_height_m: 0,
    swell_wave_height_m: 0,
    ocean_current_velocity_kmh: 0,
    wave_period_s: 0,
    wave_direction_deg: null,
    ocean_current_direction_deg: null,
    severity: 'low' as const,
  };
  const alerts = data.alerts ?? [];
  const overall = worstSeverity(data);
  const tone = severityColor(overall);
  const isSea = transportMode === 'sea' || transportMode === 'multimodal';

  return (
    <section className={`rounded-xl border ${tone.border} ${tone.bg} shadow-lg ${tone.glow}`}>
      {/* Clickable header — always visible */}
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center gap-4 p-4 text-left"
        aria-expanded={expanded}
      >
        <span className="text-3xl leading-none">{getWeatherEmoji(weather.weather_code)}</span>
        <div className="min-w-0 flex-1">
          <div className="text-base font-bold text-white">{weather.weather_description}</div>
          <div className="text-xs text-slate-400 truncate">
            {vesselName ? `Near ${vesselName}` : 'At vessel position'} · {latitude!.toFixed(2)}°, {longitude!.toFixed(2)}°
            {weather.temperature_c !== null && ` · ${weather.temperature_c}°C`}
            {isSea && ` · Waves ${marine.wave_height_m.toFixed(1)}m`}
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className={`flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold uppercase ${tone.border} ${tone.text}`}>
            <span className={`h-2 w-2 rounded-full ${tone.dot} animate-pulse`} />
            {overall} risk
          </span>
          <span className="flex items-center gap-1 rounded-full border border-green-500/30 bg-green-500/10 px-2 py-1 text-[10px] font-medium text-green-400">
            <span className="h-1.5 w-1.5 rounded-full bg-green-400 animate-pulse" />
            Live
          </span>
          <ChevronDown className={`h-4 w-4 text-slate-400 transition-transform ${expanded ? 'rotate-180' : ''}`} />
        </div>
      </button>

      {/* Expandable detail section */}
      {expanded && (
        <div className="px-4 pb-4 space-y-3">
          {/* Alerts banner */}
          {alerts.length > 0 && (
            <div className="space-y-2">
              {alerts.map((alert, i) => {
                const at = severityColor(alert.severity);
                return (
                  <div key={i} className={`flex items-start gap-2 rounded-lg border ${at.border} ${at.bg} px-4 py-3`}>
                    <AlertTriangle className={`mt-0.5 h-5 w-5 shrink-0 ${at.text}`} />
                    <span className={`text-sm font-medium ${at.text}`}>{alert.message}</span>
                  </div>
                );
              })}
            </div>
          )}

          {/* Weather + Marine grid */}
          <div className={`grid gap-3 ${isSea ? 'grid-cols-1 lg:grid-cols-2' : 'grid-cols-1'}`}>
            {/* Atmospheric weather */}
            <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-4">
              <div className="flex items-center gap-2 mb-3">
                <CloudSun className="h-4 w-4 text-cyan-300" />
                <span className="text-sm font-semibold text-white">Atmosphere</span>
                <span className={`ml-auto rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase ${severityColor(weather.severity).border} ${severityColor(weather.severity).bg} ${severityColor(weather.severity).text}`}>
                  {weather.severity}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <StatCard icon={Thermometer} label="Temperature" value={weather.temperature_c !== null ? `${weather.temperature_c}°C` : 'N/A'} />
                <StatCard icon={Wind} label="Wind Speed" value={`${weather.wind_speed_kmh.toFixed(0)} km/h`} />
                <StatCard icon={Wind} label="Wind Gusts" value={`${weather.wind_gusts_kmh.toFixed(0)} km/h`} />
                <StatCard icon={Droplets} label="Precipitation" value={`${weather.precipitation_mm.toFixed(1)} mm`} />
              </div>
            </div>

            {/* Marine conditions */}
            {isSea && (
              <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-4">
                <div className="flex items-center gap-2 mb-3">
                  <Waves className="h-4 w-4 text-blue-300" />
                  <span className="text-sm font-semibold text-white">Sea State</span>
                  <span className={`ml-auto rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase ${severityColor(marine.severity).border} ${severityColor(marine.severity).bg} ${severityColor(marine.severity).text}`}>
                    {marine.severity}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <StatCard icon={Waves} label="Wave Height" value={`${marine.wave_height_m.toFixed(1)} m`} />
                  <StatCard icon={Waves} label="Swell" value={`${marine.swell_wave_height_m.toFixed(1)} m`} />
                  <StatCard icon={Navigation} label="Current" value={`${marine.ocean_current_velocity_kmh.toFixed(1)} km/h`} />
                  <StatCard icon={Waves} label="Wave Period" value={`${marine.wave_period_s.toFixed(0)} s`} />
                </div>
              </div>
            )}
          </div>

          <div className="text-[10px] text-slate-500">
            Auto-refreshes every 5 min · Source: Open-Meteo
          </div>
        </div>
      )}
    </section>
  );
}

function StatCard({ icon: Icon, label, value }: { icon: any; label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-800/50 bg-slate-900/40 px-3 py-2">
      <div className="flex items-center gap-1.5 mb-1">
        <Icon className="h-3 w-3 text-slate-500" />
        <span className="text-[10px] uppercase tracking-wide text-slate-500">{label}</span>
      </div>
      <div className="text-sm font-semibold text-slate-100">{value}</div>
    </div>
  );
}
