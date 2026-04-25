import { RiskAssessment } from '../types/index';
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

      <h3 className="font-semibold text-white mb-2">{risk.headline || risk.summary}</h3>
      <p className="text-sm text-slate-400 mb-3 line-clamp-2">{risk.summary}</p>

      <div className="flex items-center gap-4 text-xs text-slate-500">
        <span className="capitalize">{risk.source.replace('_', ' ')}</span>
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
