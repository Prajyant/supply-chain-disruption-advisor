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
  Activity,
  Newspaper,
  Bot,
} from 'lucide-react';
import { agentApi, shipmentApi } from '../services/api';
import { loadDemoShipments } from '../services/shipmentData';
import { EvidenceEvent, ShipmentInput, StrandsShipmentRiskResponse } from '../types';
import { VesselMap } from '../components/VesselMap';
import { CollapsibleSection } from '../components/CollapsibleSection';

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
  const weatherEvents = evidenceEvents.filter((event) => isEventSource(event, ['weather', 'marine']));
  const worldEvents = evidenceEvents.filter((event) => isEventSource(event, ['trade', 'news']));
  const weatherContextEvents = contextEvents.filter((event) => isEventSource(event, ['weather', 'marine']));
  const worldContextEvents = contextEvents.filter((event) => isEventSource(event, ['trade', 'news']));
  const vesselEvents = evidenceEvents.filter((event) => isEventSource(event, ['vessel']));
  const flightEvents = evidenceEvents.filter((event) => isEventSource(event, ['flight']));
  const isAir = shipment.transport_mode === 'air';
  const telemetryEvents = isAir ? flightEvents : vesselEvents;

  return (
    <div className="space-y-6 p-5 lg:p-8">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
        <div className="min-w-0">
          <button
            onClick={() => navigate('/')}
            className="mb-4 inline-flex items-center gap-2 text-sm text-slate-400 transition-colors hover:text-white"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to dashboard
          </button>
          <h1 className="text-2xl font-bold text-white">Shipment Detail Analysis</h1>
          <p className="max-w-4xl text-slate-400">
            {shipment.shipment_id} for {shipment.supplier} on the route from {shipment.origin} to {shipment.destination}
          </p>
        </div>

        <button
          onClick={() => analysisQuery.refetch()}
          disabled={analysisQuery.isFetching}
          className="btn-primary flex items-center gap-2 disabled:opacity-50"
        >
          {analysisQuery.isFetching ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
          Refresh analysis
        </button>
      </div>

      {/* Always Visible: Risk Summary Card */}
      {analysis ? (
        <CompactRiskSummary result={analysis} />
      ) : analysisQuery.isLoading ? (
        <PageLoading label="Running shipment analysis" compact />
      ) : analysisQuery.error ? (
        <InlineError message="Shipment analysis failed. Check that the backend is running and then refresh this page." />
      ) : null}

      {/* Always Visible: Key Risk Drivers */}
      {analysis && <KeyRiskDrivers result={analysis} />}

      {/* Collapsible Sections */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <CollapsibleSection
          title="Technical Details"
          icon={<Cpu className="h-5 w-5 text-slate-400" />}
          defaultOpen={false}
        >
          <AnalysisProcessor
            shipment={shipment}
            result={analysis}
            strandsAvailable={strandsStatusQuery.data?.strands_sdk_available ?? false}
            isLoading={analysisQuery.isLoading || analysisQuery.isFetching}
            contextEvents={contextEvents}
          />
          {analysis && (
            <div className="mt-4 space-y-2">
              <h3 className="text-sm font-semibold text-white">Model Features</h3>
              {Object.entries(analysis.result.features).map(([feature, value]) => (
                <div key={feature} className="flex min-w-0 items-center justify-between gap-3 rounded-lg bg-slate-950/50 px-3 py-2 text-sm">
                  <span className="min-w-0 break-words text-slate-400">{FEATURE_LABELS[feature] || feature}</span>
                  <span className="shrink-0 font-mono text-white">{value.toFixed(2)}</span>
                </div>
              ))}
            </div>
          )}
        </CollapsibleSection>

        <CollapsibleSection
          title="Live Context"
          icon={<CloudSun className="h-5 w-5 text-slate-400" />}
          defaultOpen={false}
        >
          <div className="space-y-3">
            <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-4">
              <h3 className="text-sm font-semibold text-white mb-3">Shipment Context</h3>
              <ContextRow label="Supplier" value={shipment.supplier} />
              <ContextRow label="Material" value={shipment.material} />
              <ContextRow label="Quantity" value={String(shipment.quantity)} />
              <ContextRow label="Lead Time" value={`${shipment.lead_time_days} days`} />
              <ContextRow label="Inventory Cover" value={`${shipment.inventory_days_cover} days`} />
              <ContextRow label="Declared Value" value={formatCurrency(shipment.declared_value_usd)} />
              <ContextRow label="ETA" value={shipment.eta_date || 'Not set'} />
            </div>
            {[...weatherContextEvents, ...worldContextEvents].length > 0 && (
              <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-4">
                <h3 className="text-sm font-semibold text-white mb-3">Live Weather & News</h3>
                <div className="space-y-2">
                  {[...weatherContextEvents, ...worldContextEvents].slice(0, 5).map((event, index) => (
                    <div key={index} className="text-xs text-slate-300">
                      <span className={`font-medium ${severityClass(event.severity)}`}>{event.severity}</span>
                      {' '}{event.title}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </CollapsibleSection>

        <CollapsibleSection
          title="Full Mitigation Plan"
          icon={<ShieldCheck className="h-5 w-5 text-slate-400" />}
          defaultOpen={false}
        >
          {analysis ? (
            <div className="space-y-3">
              {analysis.result.recommended_actions.map((action, index) => (
                <div key={action} className="min-w-0 rounded-lg border border-slate-800 bg-slate-950/50 p-4">
                  <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-primary-300">
                    Action {index + 1}
                  </div>
                  <p className="break-words text-sm leading-6 text-slate-200">{action}</p>
                </div>
              ))}
              {analysis.result.escalation_required && (
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
          ) : (
            <p className="text-sm text-slate-500">Mitigation actions will appear after analysis completes.</p>
          )}
        </CollapsibleSection>

        <CollapsibleSection
          title="Evidence Events"
          icon={<Activity className="h-5 w-5 text-slate-400" />}
          defaultOpen={false}
        >
          <div className="space-y-4">
            {weatherEvents.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-white mb-2">Weather & Marine</h3>
                {weatherEvents.map((event, index) => (
                  <CompactEvidenceCard key={index} event={event} />
                ))}
              </div>
            )}
            {worldEvents.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-white mb-2">News & Trade</h3>
                {worldEvents.map((event, index) => (
                  <CompactEvidenceCard key={index} event={event} />
                ))}
              </div>
            )}
            {weatherEvents.length === 0 && worldEvents.length === 0 && (
              <p className="text-sm text-slate-500">No evidence events matched this shipment.</p>
            )}
          </div>
        </CollapsibleSection>
      </div>

      {/* Map Section */}
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
    </div>
  );
}

function AnalysisProcessor({
  shipment,
  result,
  strandsAvailable,
  isLoading,
  contextEvents,
}: {
  shipment: ShipmentInput;
  result?: StrandsShipmentRiskResponse;
  strandsAvailable: boolean;
  isLoading: boolean;
  contextEvents: EvidenceEvent[];
}) {
  const steps = buildProcessorSteps(shipment, result, strandsAvailable, isLoading, contextEvents);

  return (
    <section className="card min-w-0 space-y-4 overflow-hidden">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-white">Analysis Processor</h2>
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

      {result && (
        <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-3">
          <div className="mb-2 text-xs uppercase tracking-wide text-slate-500">Strands tool order</div>
          <div className="flex min-w-0 flex-wrap gap-2">
            {result.steps.map((step) => (
              <span key={step} className="max-w-full rounded bg-slate-800 px-2 py-1 text-xs text-slate-300 break-words">
                {step}
              </span>
            ))}
          </div>
        </div>
      )}
    </section>
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

  return [
    {
      id: 'csv',
      label: 'Supplier CSV',
      detail: `${shipment.inventory_days_cover} inventory days, priority ${formatPriority(shipment.priority)}, ${shipment.lead_time_days} day lead time`,
      status: 'complete',
      icon: FileText,
    },
    {
      id: 'vessel',
      label: 'Vessel Tracker',
      detail: shipment.vessel_name ? `${shipment.vessel_name} at ${formatCoordinates(shipment.vessel_latitude, shipment.vessel_longitude)}` : 'No vessel telemetry attached',
      status: status(Boolean(shipment.vessel_name || toolSteps.includes('track_vessel_by_imo'))),
      icon: Ship,
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
  const levelClass = {
    low: 'text-green-400 bg-green-500/10 border-green-500/30',
    medium: 'text-yellow-300 bg-yellow-500/10 border-yellow-500/30',
    high: 'text-orange-300 bg-orange-500/10 border-orange-500/30',
    critical: 'text-danger-400 bg-danger-500/10 border-danger-500/30',
  }[advice.risk_level];

  const topActions = advice.recommended_actions.slice(0, 2);

  return (
    <div className={`card min-w-0 space-y-4 overflow-hidden border ${levelClass}`}>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 flex-1">
          <div className="mb-3 flex min-w-0 flex-wrap items-center gap-2">
            <span className={`rounded px-3 py-1 text-sm font-semibold uppercase ${levelClass}`}>
              {advice.risk_level} RISK
            </span>
            <span className="text-xs text-slate-500">{result.orchestration_method}</span>
          </div>
          <div className="flex items-baseline gap-3">
            <span className="text-4xl font-bold text-white">{advice.risk_score.toFixed(1)}</span>
            <span className="text-lg text-slate-400">/ 10</span>
            <span className={`ml-2 rounded px-2 py-1 text-sm font-medium ${levelClass}`}>
              {advice.decision.toUpperCase()}
            </span>
          </div>
          <p className="mt-2 text-sm text-slate-300">{advice.reason}</p>
        </div>

        <div className="shrink-0 space-y-2 text-sm">
          <div className="flex items-center gap-2">
            <span className="text-slate-500">Confidence:</span>
            <span className="font-medium text-green-400">{advice.confidence_score}%</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-slate-500">Method:</span>
            <span className="font-medium text-slate-300">{advice.scoring_method.split('_').slice(0, 2).join(' ')}</span>
          </div>
        </div>
      </div>

      {topActions.length > 0 && (
        <div className="border-t border-slate-800 pt-4">
          <h3 className="mb-3 text-sm font-semibold text-white">Quick Actions</h3>
          <div className="space-y-2">
            {topActions.map((action, index) => (
              <div key={action} className="flex items-start gap-2 rounded-lg bg-slate-950/50 p-3">
                <span className="shrink-0 mt-0.5 flex h-5 w-5 items-center justify-center rounded-full bg-primary-500/20 text-xs font-medium text-primary-300">
                  {index + 1}
                </span>
                <span className="text-sm text-slate-200">{action}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function KeyRiskDrivers({ result }: { result: StrandsShipmentRiskResponse }) {
  const topDrivers = Object.entries(result.result.features)
    .filter(([, value]) => value > 0)
    .sort((left, right) => right[1] - left[1])
    .slice(0, 5);

  const evidenceEvents = result.result.evidence_events ?? [];

  return (
    <div className="card min-w-0 space-y-4 overflow-hidden">
      <div className="flex items-center gap-2">
        <AlertCircle className="h-5 w-5 text-orange-400" />
        <h2 className="text-lg font-semibold text-white">What Affects This Shipment</h2>
      </div>

      <div className="space-y-3">
        {topDrivers.map(([feature, value]) => {
          const explanation = driverExplanation(feature);
          const relatedEvent = evidenceEvents.find((e) => {
            const source = e.source.toLowerCase();
            if (feature.includes('weather') && source.includes('weather')) return true;
            if (feature.includes('trade') && source.includes('trade')) return true;
            if (feature.includes('news') && source.includes('news')) return true;
            return false;
          });

          return (
            <div key={feature} className="rounded-lg border border-slate-800 bg-slate-950/50 p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-medium text-white">{FEATURE_LABELS[feature] || feature}</span>
                    <span className="shrink-0 rounded bg-slate-800 px-2 py-0.5 text-xs font-mono text-slate-400">
                      {value.toFixed(1)}
                    </span>
                  </div>
                  <p className="text-sm text-slate-300">{explanation}</p>
                  {relatedEvent && (
                    <a
                      href={getEventLink(relatedEvent) || '#'}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mt-2 inline-flex items-center gap-1 text-xs text-primary-400 hover:text-primary-300"
                    >
                      <LinkIcon className="h-3 w-3" />
                      Source: {relatedEvent.title.slice(0, 40)}...
                    </a>
                  )}
                </div>
                <div className="shrink-0">
                  <div
                    className="h-2 w-2 rounded-full"
                    style={{
                      backgroundColor: value >= 7 ? '#ef4444' : value >= 4 ? '#f59e0b' : '#22c55e',
                    }}
                  />
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
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
