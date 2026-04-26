import { RiskAssessment } from '../types';
import { AlertTriangle, Shield, TrendingUp } from 'lucide-react';

interface RiskCardProps {
  risk: RiskAssessment;
}

const severityColors = {
  critical: 'bg-danger-600 border-danger-500',
  high: 'bg-orange-600 border-orange-500',
  medium: 'bg-yellow-600 border-yellow-500',
  low: 'bg-green-600 border-green-500',
};

const severityIcons = {
  critical: AlertTriangle,
  high: AlertTriangle,
  medium: TrendingUp,
  low: Shield,
};

export function RiskCard({ risk }: RiskCardProps) {
  const colorClass = severityColors[risk.severity];
  const Icon = severityIcons[risk.severity];

  return (
    <div className="card border-l-4 hover:border-l-8 transition-all">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className={`p-2 rounded-lg ${colorClass}`}>
            <Icon className="w-4 h-4 text-white" />
          </div>
          <span className={`px-2 py-1 rounded text-xs font-semibold uppercase ${colorClass}`}>
            {risk.severity}
          </span>
        </div>
        <span className="text-sm text-slate-400">
          {Math.round(risk.confidence * 100)}% confidence
        </span>
      </div>

      <h3 className="font-semibold text-white mb-2 line-clamp-1" title={risk.headline || risk.metadata?.subject || risk.summary}>
        {risk.headline || risk.metadata?.subject || risk.summary}
      </h3>
      <p className="text-sm text-slate-400 mb-3 line-clamp-2">
        {risk.headline || risk.metadata?.subject ? risk.summary : ''}
      </p>

      <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
        <span className="capitalize px-2 py-1 bg-slate-800 rounded">
          {risk.source.replace('_', ' ')}
        </span>
        {/* Try to show the actual sender name if available */}
        {(risk.metadata?.sender_name || risk.metadata?.supplier || risk.metadata?.region) && (
          <>
            <span>•</span>
            <span className="text-slate-300 truncate max-w-[150px]">
              {risk.metadata.sender_name || risk.metadata.supplier || risk.metadata.region}
            </span>
          </>
        )}
        <span>•</span>
        <span className="capitalize">{risk.disruption_type.replace('_', ' ')}</span>
      </div>

      {risk.recommendations.length > 0 && (
        <details className="mt-3">
          <summary className="text-sm text-primary-400 cursor-pointer hover:text-primary-300">
            View {risk.recommendations.length} recommendation{risk.recommendations.length > 1 ? 's' : ''}
          </summary>
          <ul className="mt-2 space-y-1 text-sm text-slate-300">
            {risk.recommendations.slice(0, 3).map((rec, i) => (
              <li key={i} className="flex items-start gap-2">
                <span className="text-primary-400 mt-1">•</span>
                <span>{rec}</span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
