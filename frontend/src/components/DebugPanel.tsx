import { useState, type ReactNode } from 'react';
import {
  Activity,
  Bug,
  ChevronDown,
  CloudSun,
  Cpu,
  FileText,
} from 'lucide-react';

type DebugSection = {
  id: string;
  label: string;
  count: number;
  icon: typeof Cpu;
  content: ReactNode;
};

interface DebugPanelProps {
  modelFeatureCount: number;
  modelFeaturesContent: ReactNode;
  evidenceCount: number;
  evidenceContent: ReactNode;
  technicalStepCount: number;
  technicalWorkflowContent: ReactNode;
  contextCount: number;
  contextContent: ReactNode;
}

export function DebugPanel({
  modelFeatureCount,
  modelFeaturesContent,
  evidenceCount,
  evidenceContent,
  technicalStepCount,
  technicalWorkflowContent,
  contextCount,
  contextContent,
}: DebugPanelProps) {
  const [openSection, setOpenSection] = useState('features');

  const sections: DebugSection[] = [
    {
      id: 'features',
      label: 'Model Features',
      count: modelFeatureCount,
      icon: Cpu,
      content: modelFeaturesContent,
    },
    {
      id: 'evidence',
      label: 'Evidence Events',
      count: evidenceCount,
      icon: Activity,
      content: evidenceContent,
    },
    {
      id: 'workflow',
      label: 'Technical Workflow',
      count: technicalStepCount,
      icon: FileText,
      content: technicalWorkflowContent,
    },
    {
      id: 'context',
      label: 'Live Context',
      count: contextCount,
      icon: CloudSun,
      content: contextContent,
    },
  ];

  const activeSection = sections.find((section) => section.id === openSection) ?? sections[0];
  const ActiveIcon = activeSection.icon;

  return (
    <section className="overflow-hidden rounded-xl border border-cyan-500/20 bg-[linear-gradient(135deg,rgba(8,47,73,0.26),rgba(2,6,23,0.95)_38%,rgba(15,23,42,0.95))] p-4 shadow-2xl shadow-cyan-950/20">
      <div className="-mx-4 -mt-4 mb-4 h-1 bg-cyan-400/80" />
      <div className="mb-4 flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-cyan-400/30 bg-cyan-400/10 text-cyan-300">
            <Bug className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <h2 className="text-base font-semibold text-white">Debug Panel</h2>
            <p className="text-xs text-slate-400">Model internals, evidence, workflow, and full context</p>
          </div>
        </div>

        <div className="flex min-w-0 flex-wrap gap-2">
          {sections.map((section) => {
            const Icon = section.icon;
            const selected = section.id === openSection;

            return (
              <button
                key={section.id}
                onClick={() => setOpenSection(section.id)}
                className={`inline-flex items-center gap-2 rounded-full border px-3 py-2 text-xs font-medium transition-all ${
                  selected
                    ? 'border-cyan-400/50 bg-cyan-400/15 text-cyan-200 shadow-lg shadow-cyan-950/30'
                    : 'border-slate-700 bg-slate-900 text-slate-300 hover:border-slate-500 hover:bg-slate-800'
                }`}
              >
                <Icon className="h-3.5 w-3.5" />
                {section.label}
                <span className="rounded-full bg-slate-950/70 px-1.5 py-0.5 font-mono text-[10px] text-slate-300">
                  {section.count}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-4 shadow-inner shadow-slate-950/50">
        <div className="mb-4 flex items-center justify-between gap-3 border-b border-slate-800 pb-3">
          <div className="flex min-w-0 items-center gap-2">
            <ActiveIcon className="h-4 w-4 shrink-0 text-cyan-300" />
            <h3 className="text-sm font-semibold text-white">{activeSection.label}</h3>
          </div>
          <ChevronDown className="h-4 w-4 shrink-0 text-slate-500" />
        </div>
        {activeSection.content}
      </div>
    </section>
  );
}
