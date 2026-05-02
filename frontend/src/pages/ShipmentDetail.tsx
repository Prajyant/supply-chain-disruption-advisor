import type { ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate, useParams } from 'react-router-dom';
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  CloudSun,
  Cpu,
  Database,
  ExternalLink,
  FileText,
  Loader2,
  RefreshCw,
  Ship,
  ShieldCheck,
  AlertCircle,
  Link as LinkIcon,
  Newspaper,
  Bot,
} from 'lucide-react';
import { agentApi, shipmentApi } from '../services/api';
import { loadDemoShipments } from '../services/shipmentData';
import { EvidenceEvent, ShipmentInput, StrandsShipmentRiskResponse } from '../types';
import { VesselMap } from '../components/VesselMap';
import { DebugPanel } from '../components/DebugPanel';
import { LiveWeatherBanner } from '../components/LiveWeatherBanner';
import { getPositionWeather, type PositionWeatherData } from '../services/weatherService';

type StrandsStatus = {
  agent: string;
  strands_sdk_available: boolean;
};

const FEATURE_LABELS: Record<string, string> = {
  lead_time_days: 'Lead Time',
  inventory_pressure: 'Inventory Pressure',
  supplier_delay_count: 'Supplier Delay History',
  priority_score: 'Buyer Priority',
  declared_value_score: 'Declared Value',
  weather_severity_score: 'Weather Severity',
  trade_severity_score: 'Trade Restrictions',
  news_severity_score: 'News Pressure',
  vessel_status_score: 'Vessel Status',
  marine_weather_score: 'Marine Weather',
  route_progress_score: 'Route Exposure',
  route_signal_count: 'Matched Signals',
  is_air: 'Air Mode',
  is_sea: 'Sea Mode',
  is_multimodal: 'Multimodal Mode',
};

type ProcessorStep = {
  id: string;
  label: string;
  detail: string;
  status: 'waiting' | 'running' | 'complete';
  icon: typeof Database;
};

export function ShipmentDetail() {
  const navigate = useNavigate();
  const { shipmentId = '' } = useParams();

  const shipmentsQuery = useQuery({
    queryKey: ['demo-shipments'],
    queryFn: loadDemoShipments,
  });

  const shipment = shipmentsQuery.data?.find((item) => item.shipment_id === shipmentId);

  const analysisQuery = useQuery({
    queryKey: ['shipment-analysis', shipmentId],
    enabled: Boolean(shipment),
    queryFn: () =>
      shipmentApi
        .runStrandsRisk(
          shipment as ShipmentInput,
          `Explain the concrete causes of risk for shipment ${shipmentId} from ${shipment?.origin} to ${shipment?.destination}.`
        )
        .then((res) => res.data as StrandsShipmentRiskResponse),
  });

  const strandsStatusQuery = useQuery({
    queryKey: ['strands-status'],
    queryFn: () => agentApi.getStrandsStatus().then((res) => res.data as StrandsStatus),
    retry: 0,
  });

  const positionWeatherQuery = useQuery({
    queryKey: ['position-weather', shipment?.vessel_latitude, shipment?.vessel_longitude],
    queryFn: () => getPositionWeather(shipment!.vessel_latitude!, shipment!.vessel_longitude!),
    enabled: typeof shipment?.vessel_latitude === 'number' && typeof shipment?.vessel_longitude === 'number',
    staleTime: 3 * 60 * 1000,
  });

  if (shipmentsQuery.isLoading) {
    return <PageLoading label="Loading shipment record" />;
  }

  if (shipmentsQuery.error) {
    return <PageState title="Unable to load shipment feed" description="The demo supplier CSV could not be loaded." />;
  }

  if (!shipment) {
    return (
      <PageState
        title="Shipment not found"
        description={`No shipment with id ${shipmentId} exists in the demo supplier feed.`}
        action={
          <button onClick={() => navigate('/')} className="btn-secondary flex items-center gap-2">
            <ArrowLeft className="w-4 h-4" />
            Back to dashboard
          </button>
        }
      />
    );
  }

  const analysis = analysisQuery.data;
  const evidenceEvents = analysis?.result.evidence_events ?? [];
  const contextEvents = analysis?.result.context_events ?? [];
  const isAir = shipment.transport_mode === 'air';
  const isGround = shipment.transport_mode === 'ground';

  const weatherEvents = evidenceEvents.filter((event) => {
    const isMarine = isEventSource(event, ['marine']);
    if (isGround && isMarine) return false;
    return isEventSource(event, ['weather', 'marine']);
  });
  const worldEvents = evidenceEvents.filter((event) => isEventSource(event, ['trade', 'news']));

  // For the Live Context panel, combine evidence + context events so it's never empty
  // Filter weather events to only show route-relevant ones
  const routeTerms = [
    shipment.origin,
    shipment.destination,
    ...(shipment.route_nodes || []),
  ]
    .filter(Boolean)
    .map((s) => s.toLowerCase());

  const allLiveEvents = [...evidenceEvents, ...contextEvents];
  const seenTitles = new Set<string>();
  const dedupedLiveEvents = allLiveEvents.filter((event) => {
    const key = event.title;
    if (seenTitles.has(key)) return false;
    seenTitles.add(key);
    if (!isEventSource(event, ['weather', 'marine', 'trade', 'news'])) return false;

    // For weather events, only include if location matches the route
    if (isEventSource(event, ['weather', 'marine'])) {
      const titleLower = event.title.toLowerCase();
      const location = (event.metadata?.location || '').toLowerCase();
      return routeTerms.some(
        (term) => titleLower.includes(term) || location.includes(term) || term.includes(location)
      );
    }
    return true; // news/trade events always included
  });
  const liveWeatherContextEvents = dedupedLiveEvents.filter((event) => {
    const isMarine = isEventSource(event, ['marine']);
    if (isGround && isMarine) return false;
    return isEventSource(event, ['weather', 'marine']);
  });
  const liveWorldContextEvents = dedupedLiveEvents.filter((event) => isEventSource(event, ['trade', 'news']));
  
  const vesselEvents = evidenceEvents.filter((event) => isEventSource(event, ['vessel']));
  const flightEvents = evidenceEvents.filter((event) => isEventSource(event, ['flight']));
  const telemetryEvents = isAir ? flightEvents : vesselEvents;

  const processorSteps = buildProcessorSteps(
    shipment,
    analysis,
    strandsStatusQuery.data?.strands_sdk_available ?? false,
    analysisQuery.isLoading || analysisQuery.isFetching,
    contextEvents
  );

  return (
    <div className="space-y-6 p-5 lg:p-8">
      <section className="overflow-hidden rounded-xl border border-slate-800 bg-[linear-gradient(135deg,#111827_0%,#020617_46%,#0f172a_100%)] shadow-2xl shadow-slate-950/50">
        <div className="border-b border-slate-800/80 px-5 py-4 lg:px-6">
          <button
            onClick={() => navigate('/')}
            className="inline-flex items-center gap-2 text-sm text-slate-400 transition-colors hover:text-white"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to dashboard
          </button>
        </div>

        <div className="flex flex-col gap-5 px-5 py-6 lg:px-6 xl:flex-row xl:items-end xl:justify-between">
          <div className="min-w-0">
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <span className="rounded-full border border-cyan-400/30 bg-cyan-400/10 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-cyan-200">
                Operations Brief
              </span>
              <span className="rounded-full border border-slate-700 bg-slate-950/60 px-3 py-1 text-xs font-medium uppercase text-slate-300">
                {shipment.transport_mode}
              </span>
              <span className="rounded-full border border-slate-700 bg-slate-950/60 px-3 py-1 text-xs font-medium text-slate-300">
                ETA {shipment.eta_date || 'not set'}
              </span>
            </div>
            <h1 className="text-3xl font-bold text-white">Shipment Detail Analysis</h1>
            <p className="mt-2 max-w-4xl text-lg text-slate-300">
              <span className="font-mono text-cyan-200">{shipment.shipment_id}</span> for {shipment.supplier}
            </p>
            <div className="mt-4 flex min-w-0 flex-wrap items-center gap-2 text-sm">
              <RouteChip label="Origin" value={shipment.origin} />
              <span className="text-slate-600">to</span>
              <RouteChip label="Destination" value={shipment.destination} />
              <RouteChip label="Material" value={shipment.material} />
              <RouteChip label="Inventory" value={`${shipment.inventory_days_cover} days`} />
            </div>
          </div>

          <button
            onClick={() => analysisQuery.refetch()}
            disabled={analysisQuery.isFetching}
            className="inline-flex w-fit items-center gap-2 rounded-lg border border-primary-400/30 bg-primary-500/20 px-4 py-3 text-sm font-semibold text-primary-100 shadow-lg shadow-primary-950/30 transition-all hover:bg-primary-500/30 disabled:opacity-50"
          >
            {analysisQuery.isFetching ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
            Refresh analysis
          </button>
        </div>
      </section>

      {/* Live weather + marine conditions at vessel position */}
      {!isGround && (
        <LiveWeatherBanner
          latitude={shipment.vessel_latitude}
          longitude={shipment.vessel_longitude}
          vesselName={shipment.vessel_name ?? undefined}
          transportMode={shipment.transport_mode}
        />
      )}

      {analysis ? (
        <div className="grid grid-cols-1 gap-5 2xl:grid-cols-[minmax(0,1.15fr)_minmax(420px,0.85fr)]">
          <div className="min-w-0 space-y-5">
            <CompactRiskSummary result={analysis} />
            <KeyRiskDrivers result={analysis} positionWeather={positionWeatherQuery.data ?? undefined} />
          </div>

          {!isGround && (
          <section className="card min-w-0 space-y-4 overflow-hidden">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <Ship className="h-5 w-5 text-primary-300" />
                  <h2 className="text-lg font-semibold text-white">Live Route View</h2>
                </div>
                <p className="mt-1 text-sm text-slate-400">
                  {shipment.origin} to {shipment.destination}
                </p>
              </div>
              <span className="w-fit rounded-full border border-slate-700 bg-slate-950/60 px-3 py-1 text-xs font-medium uppercase text-slate-300">
                {shipment.transport_mode}
              </span>
            </div>

            <VesselMap
              vesselName={isAir ? (shipment.flight_callsign || shipment.vessel_name || undefined) : (shipment.vessel_name || undefined)}
              origin={shipment.origin}
              destination={shipment.destination}
              latitude={shipment.vessel_latitude}
              longitude={shipment.vessel_longitude}
              status={telemetryEvents[0]?.metadata?.status || telemetryEvents[0]?.metadata?.vessel_status || undefined}
              speed={telemetryEvents[0]?.metadata?.speed_knots}
              progress={telemetryEvents[0]?.metadata?.progress_percent}
              transportMode={shipment.transport_mode}
            />
          </section>
          )}
        </div>
      ) : analysisQuery.isLoading ? (
        <PageLoading label="Running shipment analysis" compact />
      ) : analysisQuery.error ? (
        <InlineError message="Shipment analysis failed. Check that the backend is running and then refresh this page." />
      ) : null}

      {analysis && (
        <DebugPanel
          modelFeatureCount={Object.keys(analysis.result.features).length}
          modelFeaturesContent={<ModelFeaturesList features={analysis.result.features} />}
          evidenceCount={evidenceEvents.length}
          evidenceContent={<EvidenceDebugContent weatherEvents={weatherEvents} worldEvents={worldEvents} />}
          technicalStepCount={processorSteps.length}
          technicalWorkflowContent={
            <AnalysisProcessor
              steps={processorSteps}
              toolSteps={analysis.steps}
              isLoading={analysisQuery.isLoading || analysisQuery.isFetching}
            />
          }
          mitigationCount={analysis.result.recommended_actions.length}
          mitigationContent={
            <MitigationDebugContent
              actions={analysis.result.recommended_actions}
              escalationRequired={analysis.result.escalation_required}
            />
          }
          contextCount={contextEvents.length + 1}
          contextContent={
            <LiveContextDebugContent
              shipment={shipment}
              weatherContextEvents={liveWeatherContextEvents}
              worldContextEvents={liveWorldContextEvents}
            />
          }
        />
      )}
    </div>
  );
}

function AnalysisProcessor({
  steps,
  toolSteps,
  isLoading,
}: {
  steps: ProcessorStep[];
  toolSteps: string[];
  isLoading: boolean;
}) {
  return (
    <div className="min-w-0 space-y-4 overflow-hidden">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h4 className="text-sm font-semibold text-white">Analysis Processor</h4>
          <p className="text-sm text-slate-400">Live view of how Strands coordinates the shipment decision workflow</p>
        </div>
        {isLoading && (
          <div className="inline-flex items-center gap-2 rounded-lg border border-primary-500/30 bg-primary-500/10 px-3 py-2 text-sm text-primary-300">
            <Loader2 className="h-4 w-4 animate-spin" />
            Processing
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
        {steps.map((step) => (
          <ProcessorNode key={step.id} step={step} />
        ))}
      </div>

      {toolSteps.length > 0 && (
        <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-3">
          <div className="mb-2 text-xs uppercase tracking-wide text-slate-500">Strands tool order</div>
          <div className="flex min-w-0 flex-wrap gap-2">
            {toolSteps.map((step) => (
              <span key={step} className="max-w-full rounded bg-slate-800 px-2 py-1 text-xs text-slate-300 break-words">
                {step}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ProcessorNode({ step }: { step: ProcessorStep }) {
  const Icon = step.icon;
  const statusClass = {
    waiting: 'border-slate-800 bg-slate-950/40 text-slate-500',
    running: 'border-primary-500/40 bg-primary-500/10 text-primary-300',
    complete: 'border-green-500/30 bg-green-500/10 text-green-300',
  }[step.status];

  return (
    <div className={`min-h-[118px] min-w-0 rounded-lg border p-3 ${statusClass}`}>
      <div className="mb-3 flex items-center justify-between gap-2">
        <Icon className="h-4 w-4" />
        {step.status === 'running' ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
      </div>
      <div className="break-words text-sm font-semibold text-white">{step.label}</div>
      <div className="mt-2 break-words text-xs leading-5 text-slate-400">{step.detail}</div>
    </div>
  );
}

function ModelFeaturesList({ features }: { features: Record<string, number> }) {
  return (
    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3">
      {Object.entries(features).map(([feature, value]) => (
        <div key={feature} className="flex min-w-0 items-center justify-between gap-3 rounded-lg bg-slate-950/60 px-3 py-2 text-sm">
          <span className="min-w-0 break-words text-slate-400">{FEATURE_LABELS[feature] || feature}</span>
          <span className="shrink-0 font-mono text-white">{value.toFixed(2)}</span>
        </div>
      ))}
    </div>
  );
}

function EvidenceDebugContent({
  weatherEvents,
  worldEvents,
}: {
  weatherEvents: EvidenceEvent[];
  worldEvents: EvidenceEvent[];
}) {
  if (weatherEvents.length === 0 && worldEvents.length === 0) {
    return <p className="text-sm text-slate-500">No evidence events matched this shipment.</p>;
  }

  return (
    <div className="space-y-4">
      {weatherEvents.length > 0 && (
        <div>
          <h4 className="mb-2 text-sm font-semibold text-white">Weather & Marine</h4>
          <div className="space-y-2">
            {weatherEvents.map((event, index) => (
              <CompactEvidenceCard key={`${event.title}-${index}`} event={event} />
            ))}
          </div>
        </div>
      )}
      {worldEvents.length > 0 && (
        <div>
          <h4 className="mb-2 text-sm font-semibold text-white">News & Trade</h4>
          <div className="space-y-2">
            {worldEvents.map((event, index) => (
              <CompactEvidenceCard key={`${event.title}-${index}`} event={event} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function MitigationDebugContent({
  actions,
  escalationRequired,
}: {
  actions: string[];
  escalationRequired: boolean;
}) {
  return (
    <div className="space-y-3">
      {actions.map((action, index) => (
        <div key={action} className="min-w-0 rounded-lg border border-slate-800 bg-slate-950/60 p-4">
          <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-primary-300">
            Action {index + 1}
          </div>
          <p className="break-words text-sm leading-6 text-slate-200">{action}</p>
        </div>
      ))}
      {escalationRequired && (
        <div className="rounded-lg border border-danger-500/30 bg-danger-500/10 p-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-danger-300">
            <AlertCircle className="h-4 w-4" />
            Escalation Required
          </div>
          <p className="mt-2 text-sm text-slate-300">
            This shipment requires immediate attention from procurement and logistics leadership.
          </p>
        </div>
      )}
    </div>
  );
}

function LiveContextDebugContent({
  shipment,
  weatherContextEvents,
  worldContextEvents,
}: {
  shipment: ShipmentInput;
  weatherContextEvents: EvidenceEvent[];
  worldContextEvents: EvidenceEvent[];
}) {
  const liveEvents = [...weatherContextEvents, ...worldContextEvents];

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-4">
        <h4 className="mb-3 text-sm font-semibold text-white">Shipment Context</h4>
        <ContextRow label="Supplier" value={shipment.supplier} />
        <ContextRow label="Material" value={shipment.material} />
        <ContextRow label="Quantity" value={String(shipment.quantity)} />
        <ContextRow label="Lead Time" value={`${shipment.lead_time_days} days`} />
        <ContextRow label="Inventory Cover" value={`${shipment.inventory_days_cover} days`} />
        <ContextRow label="Declared Value" value={formatCurrency(shipment.declared_value_usd)} />
        <ContextRow label="ETA" value={shipment.eta_date || 'Not set'} />
      </div>

      <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-4">
        <h4 className="mb-3 text-sm font-semibold text-white">Live Weather & News</h4>
        {liveEvents.length > 0 ? (
          <div className="space-y-2">
            {liveEvents.slice(0, 8).map((event, index) => {
              const eventLink = getEventLink(event);
              const isNews = isEventSource(event, ['news', 'trade']);
              return (
                <div key={`${event.title}-${index}`} className="flex items-start gap-2 text-xs">
                  <span className={`mt-0.5 shrink-0 rounded px-1.5 py-0.5 font-medium ${severityClass(event.severity)}`}>
                    {event.severity}
                  </span>
                  <div className="min-w-0 flex-1">
                    {eventLink ? (
                      <a
                        href={eventLink}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-cyan-200 underline decoration-cyan-400/30 hover:text-cyan-100 hover:decoration-cyan-400/60 transition-colors"
                      >
                        {event.title}
                        <ExternalLink className="ml-1 inline h-3 w-3" />
                      </a>
                    ) : isNews && event.metadata?.link ? (
                      <a
                        href={String(event.metadata.link)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-cyan-200 underline decoration-cyan-400/30 hover:text-cyan-100 hover:decoration-cyan-400/60 transition-colors"
                      >
                        {event.title}
                        <ExternalLink className="ml-1 inline h-3 w-3" />
                      </a>
                    ) : (
                      <span className="text-slate-300">{event.title}</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-sm text-slate-500">No non-scoring context events were returned for this shipment.</p>
        )}
      </div>
    </div>
  );
}

function buildProcessorSteps(
  shipment: ShipmentInput,
  result: StrandsShipmentRiskResponse | undefined,
  strandsAvailable: boolean,
  isLoading: boolean,
  contextEvents: EvidenceEvent[]
): ProcessorStep[] {
  const status = (complete: boolean): ProcessorStep['status'] => {
    if (complete) return 'complete';
    return isLoading ? 'running' : 'waiting';
  };
  const hasWeatherContext = contextEvents.some((event) => isEventSource(event, ['weather', 'marine']));
  const hasNewsContext = contextEvents.some((event) => isEventSource(event, ['news', 'trade']));
  const toolSteps = result?.steps ?? [];

  const steps: ProcessorStep[] = [
    {
      id: 'csv',
      label: 'Supplier CSV',
      detail: `${shipment.inventory_days_cover} inventory days, priority ${formatPriority(shipment.priority)}, ${shipment.lead_time_days} day lead time`,
      status: 'complete',
      icon: FileText,
    },
    {
      id: 'weather',
      label: 'Weather API',
      detail: hasWeatherContext || result ? 'Open-Meteo route and marine context checked' : 'Waiting for live weather check',
      status: status(Boolean(result || hasWeatherContext)),
      icon: CloudSun,
    },
    {
      id: 'news',
      label: 'World Monitor',
      detail: hasNewsContext || result ? 'News and trade context checked for awareness' : 'Waiting for news/trade context',
      status: status(Boolean(result || hasNewsContext)),
      icon: Newspaper,
    },
    {
      id: 'xgboost',
      label: 'XGBoost',
      detail: result ? `${result.result.scoring_method}: ${result.result.risk_score.toFixed(2)}/10` : 'Waiting for feature vector',
      status: status(Boolean(result)),
      icon: Cpu,
    },
    {
      id: 'strands',
      label: 'Strands',
      detail: result ? result.orchestration_method : strandsAvailable ? 'SDK available, workflow queued' : 'Fallback mirror available',
      status: status(Boolean(result)),
      icon: Bot,
    },
    {
      id: 'gemini',
      label: 'Gemini',
      detail: result ? result.result.reasoning_method : 'Waiting for mitigation reasoning',
      status: status(Boolean(result)),
      icon: Bot,
    },
    {
      id: 'validation',
      label: 'Guardrails',
      detail: result ? 'Schema, score, level, and actions validated' : 'Waiting for final response',
      status: status(Boolean(result?.steps.includes('validate_risk_response'))),
      icon: ShieldCheck,
    },
  ];

  if (shipment.transport_mode !== 'ground') {
    steps.splice(1, 0, {
      id: 'vessel',
      label: 'Vessel Tracker',
      detail: shipment.vessel_name ? `${shipment.vessel_name} at ${formatCoordinates(shipment.vessel_latitude, shipment.vessel_longitude)}` : 'No vessel telemetry attached',
      status: status(Boolean(shipment.vessel_name || toolSteps.includes('track_vessel_by_imo'))),
      icon: Ship,
    });
  }

  return steps;
}

function PageLoading({ label, compact = false }: { label: string; compact?: boolean }) {
  return (
    <div className={compact ? 'rounded-lg border border-slate-800 bg-slate-950/50 p-5' : 'p-8'}>
      <div className="flex items-center gap-3 text-slate-300">
        <Loader2 className="h-5 w-5 animate-spin text-primary-400" />
        <span>{label}</span>
      </div>
    </div>
  );
}

function PageState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="p-8">
      <div className="card max-w-2xl space-y-4">
        <div className="flex items-start gap-3">
          <AlertTriangle className="mt-0.5 h-5 w-5 text-danger-400" />
          <div>
            <h1 className="text-lg font-semibold text-white">{title}</h1>
            <p className="mt-1 text-sm text-slate-400">{description}</p>
          </div>
        </div>
        {action}
      </div>
    </div>
  );
}

function ContextRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex min-w-0 items-center justify-between gap-4 border-b border-slate-800/80 pb-3 text-sm last:border-b-0 last:pb-0">
      <span className="shrink-0 text-slate-500">{label}</span>
      <span className="min-w-0 break-words text-right text-slate-200">{value}</span>
    </div>
  );
}

function InlineError({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-danger-500/40 bg-danger-500/10 p-4 text-sm text-danger-300">
      {message}
    </div>
  );
}

function RouteChip({ label, value }: { label: string; value: string }) {
  return (
    <span className="inline-flex max-w-full items-center gap-2 rounded-lg border border-slate-700 bg-slate-950/70 px-3 py-2">
      <span className="shrink-0 text-xs uppercase tracking-wide text-slate-500">{label}</span>
      <span className="min-w-0 truncate text-slate-200">{value}</span>
    </span>
  );
}

function formatPriority(priority: ShipmentInput['priority']): string {
  const numeric = Number(priority);
  if (Number.isFinite(numeric)) {
    if (numeric >= 3) return 'Express';
    if (numeric >= 2) return 'High';
    if (numeric >= 1) return 'Normal';
    return 'Low';
  }
  return String(priority);
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(value);
}

function severityClass(severity: string): string {
  const normalized = severity.toLowerCase();
  if (normalized === 'critical') return 'bg-danger-500/10 text-danger-300';
  if (normalized === 'high') return 'bg-orange-500/10 text-orange-300';
  if (normalized === 'medium') return 'bg-yellow-500/10 text-yellow-300';
  return 'bg-green-500/10 text-green-300';
}

function riskTone(level: string) {
  const tones = {
    low: {
      hex: '#22c55e',
      border: 'border-green-500/30',
      panel: 'bg-[linear-gradient(135deg,rgba(20,83,45,0.26),rgba(2,6,23,0.96)_42%,rgba(15,23,42,0.95))]',
      badge: 'border-green-500/30 bg-green-500/10 text-green-300',
      strip: 'bg-green-400',
      shadow: 'shadow-green-950/20',
    },
    medium: {
      hex: '#eab308',
      border: 'border-yellow-500/30',
      panel: 'bg-[linear-gradient(135deg,rgba(113,63,18,0.28),rgba(2,6,23,0.96)_42%,rgba(15,23,42,0.95))]',
      badge: 'border-yellow-500/30 bg-yellow-500/10 text-yellow-200',
      strip: 'bg-yellow-400',
      shadow: 'shadow-yellow-950/20',
    },
    high: {
      hex: '#f97316',
      border: 'border-orange-500/30',
      panel: 'bg-[linear-gradient(135deg,rgba(124,45,18,0.32),rgba(2,6,23,0.96)_42%,rgba(15,23,42,0.95))]',
      badge: 'border-orange-500/30 bg-orange-500/10 text-orange-200',
      strip: 'bg-orange-400',
      shadow: 'shadow-orange-950/20',
    },
    critical: {
      hex: '#ef4444',
      border: 'border-danger-500/30',
      panel: 'bg-[linear-gradient(135deg,rgba(127,29,29,0.36),rgba(2,6,23,0.96)_42%,rgba(15,23,42,0.95))]',
      badge: 'border-danger-500/30 bg-danger-500/10 text-danger-200',
      strip: 'bg-danger-400',
      shadow: 'shadow-danger-950/20',
    },
  };

  return tones[level as keyof typeof tones] ?? tones.medium;
}

function formatDecision(decision: string): string {
  return decision.replace(/_/g, ' ');
}

function parseActionOwner(action: string): { owner: string; text: string } {
  const match = action.match(/^\s*\[([^\]]+)\]\s*(.*)$/);
  if (match) {
    return { owner: match[1], text: match[2] || action };
  }

  const lower = action.toLowerCase();
  if (lower.includes('supplier')) return { owner: 'Supplier', text: action };
  if (lower.includes('carrier') || lower.includes('vessel') || lower.includes('flight')) return { owner: 'Carrier', text: action };
  if (lower.includes('customs') || lower.includes('compliance')) return { owner: 'Compliance', text: action };
  if (lower.includes('stock') || lower.includes('inventory') || lower.includes('plant')) return { owner: 'Plant', text: action };
  if (lower.includes('forwarder') || lower.includes('route') || lower.includes('port')) return { owner: 'Forwarder', text: action };
  return { owner: 'Procurement', text: action };
}

function driverLevel(value: number): { bar: string; badge: string; dot: string } {
  if (value >= 7) {
    return {
      bar: 'bg-danger-400',
      badge: 'border-danger-500/30 bg-danger-500/10 text-danger-200',
      dot: 'bg-danger-400 shadow-lg shadow-danger-500/30',
    };
  }
  if (value >= 4) {
    return {
      bar: 'bg-orange-400',
      badge: 'border-orange-500/30 bg-orange-500/10 text-orange-200',
      dot: 'bg-orange-400 shadow-lg shadow-orange-500/30',
    };
  }
  return {
    bar: 'bg-green-400',
    badge: 'border-green-500/30 bg-green-500/10 text-green-200',
    dot: 'bg-green-400 shadow-lg shadow-green-500/30',
  };
}

function isEventSource(event: EvidenceEvent, terms: string[]): boolean {
  const source = event.source.toLowerCase();
  return terms.some((term) => source.includes(term));
}

function getEventLink(event: EvidenceEvent): string {
  const metadataLink = typeof event.metadata.link === 'string' ? decodeHtmlEntities(event.metadata.link).trim() : '';
  if (isExternalUrl(metadataLink)) {
    return metadataLink;
  }
  const summaryLink = extractHref(event.summary);
  return isExternalUrl(summaryLink) ? summaryLink : '';
}

function extractHref(value: string): string {
  const match = value.match(/href=["']([^"']+)["']/i);
  return match ? decodeHtmlEntities(match[1]).trim() : '';
}

function cleanEventText(value: string): string {
  const withoutAnchors = value.replace(/<a\s+[^>]*>(.*?)<\/a>/gi, '$1');
  const withoutTags = withoutAnchors.replace(/<[^>]+>/g, ' ');
  return decodeHtmlEntities(withoutTags).replace(/\s+/g, ' ').trim();
}

function decodeHtmlEntities(value: string): string {
  if (!value) return '';
  const textarea = document.createElement('textarea');
  textarea.innerHTML = value;
  return textarea.value;
}

function isExternalUrl(value: string): boolean {
  return /^https?:\/\//i.test(value);
}

function formatCoordinates(latitude?: number | null, longitude?: number | null): string {
  if (typeof latitude !== 'number' || typeof longitude !== 'number') {
    return 'Unavailable';
  }
  return `${latitude.toFixed(2)}, ${longitude.toFixed(2)}`;
}

function driverExplanation(feature: string): string {
  const explanations: Record<string, string> = {
    inventory_pressure: 'Low destination cover increases stockout pressure.',
    priority_score: 'Buyer priority raises business impact if delayed.',
    supplier_delay_count: 'Past supplier delays add reliability risk.',
    weather_severity_score: 'Weather events are active on the shipment route.',
    news_severity_score: 'World events are raising route uncertainty.',
    trade_severity_score: 'Trade restrictions may slow flow or customs handling.',
    vessel_status_score: 'The vessel status suggests operational friction.',
    marine_weather_score: 'Marine conditions could affect sea transit speed.',
    route_progress_score: 'The shipment still has route exposure ahead.',
    lead_time_days: 'Longer lead time leaves more time for disruption.',
    declared_value_score: 'Higher shipment value increases consequence.',
    route_signal_count: 'Multiple live signals matched this route.',
  };

  return explanations[feature] || 'This feature contributed to the shipment risk score.';
}

// New compact components

function CompactRiskSummary({ result }: { result: StrandsShipmentRiskResponse }) {
  const advice = result.result;
  const tone = riskTone(advice.risk_level);

  const topActions = advice.recommended_actions.slice(0, 3);
  const scoreAngle = Math.min(Math.max(advice.risk_score, 0), 10) * 36;

  return (
    <section className={`relative min-w-0 overflow-hidden rounded-xl border ${tone.border} ${tone.panel} p-5 shadow-2xl ${tone.shadow}`}>
      <div className={`absolute inset-x-0 top-0 h-1 ${tone.strip}`} />
      <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
        <div className="min-w-0 flex-1 space-y-4">
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <span className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-wide ${tone.badge}`}>
              {advice.risk_level} risk
            </span>
            <span className="rounded-full border border-slate-700 bg-slate-950/70 px-3 py-1 text-xs text-slate-400">
              {result.orchestration_method}
            </span>
            <span className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase ${tone.badge}`}>
              {formatDecision(advice.decision)}
            </span>
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-[132px_minmax(0,1fr)]">
            <div
              className="flex aspect-square w-32 items-center justify-center rounded-full p-2"
              style={{
                background: `conic-gradient(${tone.hex} ${scoreAngle}deg, rgba(30,41,59,0.75) 0deg)`,
              }}
            >
              <div className="flex h-full w-full flex-col items-center justify-center rounded-full bg-slate-950">
                <span className="text-4xl font-bold text-white">{advice.risk_score.toFixed(1)}</span>
                <span className="text-xs uppercase tracking-wide text-slate-500">of 10</span>
              </div>
            </div>

            <div className="min-w-0">
              <h2 className="text-xl font-semibold text-white">Control Tower Recommendation</h2>
              <p className="mt-2 text-sm leading-6 text-slate-300">{advice.reason}</p>
              <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
                <MetricPill label="Confidence" value={`${advice.confidence_score}%`} />
                <MetricPill label="Method" value={advice.scoring_method.split('_').slice(0, 2).join(' ')} />
                <MetricPill label="Actions" value={String(advice.recommended_actions.length)} />
              </div>
            </div>
          </div>
        </div>
      </div>

      {topActions.length > 0 && (
        <div className="mt-5 border-t border-slate-800/80 pt-4">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h3 className="text-sm font-semibold text-white">Immediate Actions</h3>
            <span className="text-xs text-slate-500">Owner tagged</span>
          </div>
          <div className="grid grid-cols-1 gap-3 xl:grid-cols-3">
            {topActions.map((action, index) => (
              <ActionCard key={action} action={action} index={index} />
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

function MetricPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950/70 px-3 py-2">
      <div className="text-[10px] uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 truncate text-sm font-semibold text-slate-100">{value}</div>
    </div>
  );
}

function ActionCard({ action, index }: { action: string; index: number }) {
  const parsed = parseActionOwner(action);

  return (
    <div className="min-w-0 rounded-lg border border-slate-800 bg-slate-950/70 p-3 transition-colors hover:border-slate-700 hover:bg-slate-900/80">
      <div className="mb-2 flex items-center gap-2">
        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary-500/20 text-xs font-semibold text-primary-200">
                  {index + 1}
                </span>
        <span className="rounded-full border border-cyan-400/30 bg-cyan-400/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-cyan-200">
          {parsed.owner}
        </span>
      </div>
      <p className="text-sm leading-6 text-slate-200">{parsed.text}</p>
    </div>
  );
}

function KeyRiskDrivers({ result, positionWeather }: { result: StrandsShipmentRiskResponse; positionWeather?: PositionWeatherData }) {
  const topDrivers = Object.entries(result.result.features)
    .filter(([, value]) => value > 0)
    .sort((left, right) => right[1] - left[1])
    .slice(0, 5);

  const evidenceEvents = result.result.evidence_events ?? [];

  // Build live condition cards from position weather when severity >= medium
  const liveConditions: { type: string; severity: string; title: string; detail: string }[] = [];
  if (positionWeather?.weather && positionWeather.weather.severity !== 'low') {
    const w = positionWeather.weather;
    liveConditions.push({
      type: 'weather',
      severity: w.severity,
      title: `${w.weather_description} at vessel position`,
      detail: `Wind ${w.wind_speed_kmh.toFixed(0)} km/h, gusts ${w.wind_gusts_kmh.toFixed(0)} km/h, rain ${w.precipitation_mm.toFixed(1)} mm`,
    });
  }
  if (positionWeather?.marine && positionWeather.marine.severity !== 'low') {
    const m = positionWeather.marine;
    liveConditions.push({
      type: 'marine',
      severity: m.severity,
      title: `Rough sea conditions at vessel position`,
      detail: `Waves ${m.wave_height_m.toFixed(1)} m, swell ${m.swell_wave_height_m.toFixed(1)} m, current ${m.ocean_current_velocity_kmh.toFixed(1)} km/h`,
    });
  }

  return (
    <section className="min-w-0 overflow-hidden rounded-xl border border-slate-800 bg-slate-900/80 p-5 shadow-xl shadow-slate-950/30">
      <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-orange-400/30 bg-orange-400/10 text-orange-300">
            <AlertCircle className="h-4 w-4" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-white">What Affects This Shipment</h2>
            <p className="text-xs text-slate-500">Ranked model drivers with route evidence</p>
          </div>
        </div>
        <span className="w-fit rounded-full border border-slate-700 bg-slate-950/70 px-3 py-1 text-xs text-slate-400">
          Top {topDrivers.length}
        </span>
      </div>

      <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
        {topDrivers.map(([feature, value]) => {
          const explanation = driverExplanation(feature);
          const relatedEvent = evidenceEvents.find((e) => {
            const source = e.source.toLowerCase();
            if (feature.includes('weather') && source.includes('weather')) return true;
            if (feature.includes('trade') && source.includes('trade')) return true;
            if (feature.includes('news') && source.includes('news')) return true;
            return false;
          });
          const level = driverLevel(value);
          const eventLink = relatedEvent ? getEventLink(relatedEvent) : '';

          return (
            <article key={feature} className="group relative overflow-hidden rounded-lg border border-slate-800 bg-slate-950/60 p-4 transition-colors hover:border-slate-700">
              <div className={`absolute inset-y-0 left-0 w-1 ${level.bar}`} />
              <div className="flex items-start justify-between gap-3 pl-2">
                <div className="min-w-0 flex-1">
                  <div className="mb-2 flex items-center gap-2">
                    <span className="text-sm font-medium text-white">{FEATURE_LABELS[feature] || feature}</span>
                    <span className={`shrink-0 rounded-full border px-2 py-0.5 text-xs font-mono ${level.badge}`}>
                      {value.toFixed(1)}
                    </span>
                  </div>
                  <p className="text-sm leading-6 text-slate-300">{explanation}</p>
                  {relatedEvent && (
                    <a
                      href={eventLink || undefined}
                      target={eventLink ? '_blank' : undefined}
                      rel={eventLink ? 'noopener noreferrer' : undefined}
                      className={`mt-3 inline-flex max-w-full items-center gap-1 rounded-full border border-slate-700 bg-slate-900 px-2.5 py-1 text-xs text-cyan-200 transition-colors ${eventLink ? 'hover:border-cyan-400/40 hover:text-cyan-100' : 'cursor-default'}`}
                    >
                      <LinkIcon className="h-3 w-3" />
                      <span className="truncate">Source: {relatedEvent.title}</span>
                    </a>
                  )}
                </div>
                <div className={`mt-1 h-3 w-3 shrink-0 rounded-full ${level.dot}`} />
              </div>
            </article>
          );
        })}
      </div>

      {/* Live weather/marine conditions (medium+ severity) */}
      {liveConditions.length > 0 && (
        <div className="mt-4">
          <div className="mb-2 flex items-center gap-2 text-xs text-slate-500">
            <CloudSun className="h-3.5 w-3.5" />
            <span className="uppercase tracking-wide">Live conditions at vessel position</span>
          </div>
          <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
            {liveConditions.map((cond) => {
              const condLevel = driverLevel(cond.severity === 'critical' ? 9 : cond.severity === 'high' ? 7 : 5);
              return (
                <article key={cond.type} className="group relative overflow-hidden rounded-lg border border-slate-800 bg-slate-950/60 p-4 transition-colors hover:border-slate-700">
                  <div className={`absolute inset-y-0 left-0 w-1 ${condLevel.bar}`} />
                  <div className="flex items-start justify-between gap-3 pl-2">
                    <div className="min-w-0 flex-1">
                      <div className="mb-2 flex items-center gap-2">
                        <span className="text-sm font-medium text-white">{cond.title}</span>
                        <span className={`shrink-0 rounded-full border px-2 py-0.5 text-xs font-semibold uppercase ${condLevel.badge}`}>
                          {cond.severity}
                        </span>
                      </div>
                      <p className="text-sm leading-6 text-slate-300">{cond.detail}</p>
                      <span className="mt-2 inline-flex items-center gap-1 rounded-full border border-cyan-400/20 bg-cyan-400/5 px-2 py-0.5 text-[10px] text-cyan-300">
                        <span className="h-1.5 w-1.5 rounded-full bg-green-400 animate-pulse" />
                        Live data
                      </span>
                    </div>
                    <div className={`mt-1 h-3 w-3 shrink-0 rounded-full ${condLevel.dot}`} />
                  </div>
                </article>
              );
            })}
          </div>
        </div>
      )}
    </section>
  );
}

function CompactEvidenceCard({ event }: { event: EvidenceEvent }) {
  const eventLink = getEventLink(event);
  const summary = cleanEventText(event.summary);

  return (
    <div className="min-w-0 overflow-hidden rounded-lg border border-slate-800 bg-slate-950/50 p-3">
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex items-center gap-2">
          <span className={`shrink-0 rounded px-2 py-0.5 text-[10px] font-semibold uppercase ${severityClass(event.severity)}`}>
            {event.severity}
          </span>
          <span className="text-xs text-slate-500">{event.source}</span>
        </div>
        {eventLink && (
          <a
            href={eventLink}
            target="_blank"
            rel="noopener noreferrer"
            className="shrink-0 text-primary-400 hover:text-primary-300"
          >
            <ExternalLink className="h-4 w-4" />
          </a>
        )}
      </div>
      <h4 className="text-sm font-medium text-white mb-1">{event.title}</h4>
      <p className="text-xs text-slate-400 line-clamp-2">{summary || event.title}</p>
    </div>
  );
}
