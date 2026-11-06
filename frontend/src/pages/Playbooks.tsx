import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { playbookApi } from '../services/api';
import {
  Zap, Play, CheckCircle2, XCircle, AlertTriangle,
  Clock, Shield, Truck, Building2, Activity,
  ThumbsUp, ThumbsDown, Loader2, BookOpen,
} from 'lucide-react';
import { PlaybookWithStats, PlaybookExecution } from '../types';

/* ── helpers ─────────────────────────────────────────────────────────── */
function catStyle(cat: string) {
  switch (cat) {
    case 'logistics':        return { icon: Truck,        color: 'text-blue-400',    bg: 'bg-blue-400/10',    border: 'border-blue-400/20' };
    case 'natural_disaster': return { icon: AlertTriangle, color: 'text-rose-400',    bg: 'bg-rose-400/10',    border: 'border-rose-400/20' };
    case 'operations':       return { icon: Building2,    color: 'text-amber-400',   bg: 'bg-amber-400/10',   border: 'border-amber-400/20' };
    case 'security':         return { icon: Shield,       color: 'text-purple-400',  bg: 'bg-purple-400/10',  border: 'border-purple-400/20' };
    case 'financial':        return { icon: Activity,     color: 'text-emerald-400', bg: 'bg-emerald-400/10', border: 'border-emerald-400/20' };
    default:                 return { icon: Zap,          color: 'text-slate-400',   bg: 'bg-slate-400/10',   border: 'border-slate-700' };
  }
}

function severityBadge(s: string) {
  if (s === 'critical') return 'badge-critical';
  if (s === 'high')     return 'badge-high';
  if (s === 'medium')   return 'badge-medium';
  return 'badge-low';
}

/* ── component ───────────────────────────────────────────────────────── */
export function Playbooks() {
  const qc = useQueryClient();
  const [toast, setToast] = useState<{
    title: string; msg: string; type: 'success' | 'warning' | 'error';
  } | null>(null);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 4500);
    return () => clearTimeout(t);
  }, [toast]);

  const { data: pbData,   isLoading: loadPb   } = useQuery({
    queryKey: ['playbooks'],
    queryFn: () => playbookApi.getPlaybooks().then(r => r.data),
  });
  const { data: execData, isLoading: loadExec } = useQuery({
    queryKey: ['playbook-executions'],
    queryFn: () => playbookApi.getExecutions().then(r => r.data),
    refetchInterval: 10_000,
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      playbookApi.togglePlaybook(id, enabled),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['playbooks'] });
      setToast({ title: 'Updated', msg: data.data.warning || 'Playbook toggled.', type: 'warning' });
    },
  });

  const simulateMutation = useMutation({
    mutationFn: (id: string) => playbookApi.simulate(id),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['playbook-executions'] });
      qc.invalidateQueries({ queryKey: ['playbooks'] });
      setToast({ title: 'Simulation Started', msg: data.data.message, type: 'success' });
    },
    onError: (err: any) =>
      setToast({ title: 'Simulation Failed', msg: err.response?.data?.detail || 'Failed.', type: 'error' }),
  });

  const feedbackMutation = useMutation({
    mutationFn: ({ id, decision }: { id: string; decision: string }) =>
      playbookApi.submitFeedback(id, decision),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['playbook-executions'] });
      qc.invalidateQueries({ queryKey: ['playbooks'] });
      setToast({ title: 'Feedback Recorded', msg: data.data.message, type: 'success' });
    },
    onError: (err: any) => {
      if (err.response?.status === 409) {
        setToast({ title: 'Already Submitted', msg: 'Feedback already recorded.', type: 'warning' });
      } else {
        setToast({ title: 'Error', msg: 'Failed to record feedback.', type: 'error' });
      }
    },
  });

  const playbooks  = (pbData?.playbooks   || []) as PlaybookWithStats[];
  const executions = (execData?.executions || []) as PlaybookExecution[];

  return (
    <div className="p-8 h-full flex flex-col bg-slate-950 relative overflow-hidden">

      {/* ── Toast ── */}
      {toast && (
        <div className={`absolute top-8 right-8 z-50 max-w-sm flex items-start gap-3 px-4 py-3.5 rounded-xl border shadow-2xl glass ${
          toast.type === 'success' ? 'border-emerald-500/30 text-emerald-300' :
          toast.type === 'warning' ? 'border-amber-500/30  text-amber-300'   :
                                     'border-red-500/30    text-red-300'
        }`}>
          {toast.type === 'success' && <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />}
          {toast.type === 'warning' && <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />}
          {toast.type === 'error'   && <XCircle       className="w-4 h-4 shrink-0 mt-0.5" />}
          <div className="flex-1 min-w-0">
            <p className="font-semibold text-white text-sm">{toast.title}</p>
            <p className="text-xs mt-0.5 opacity-80">{toast.msg}</p>
          </div>
          <button onClick={() => setToast(null)} className="opacity-50 hover:opacity-100 ml-2 shrink-0">
            <XCircle className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* ── Page header ── */}
      <div className="shrink-0 mb-7">
        <h1 className="page-title flex items-center gap-2">
          <BookOpen className="w-6 h-6 text-primary-400" />
          Automated Playbooks
        </h1>
        <p className="page-subtitle">
          Rule-based response templates with reinforcement-learning feedback loops
        </p>
      </div>

      <div className="flex-1 overflow-y-auto space-y-10 pb-10">

        {/* ── Playbook library ── */}
        <section>
          <div className="flex items-center justify-between mb-5">
            <h2 className="section-title flex items-center gap-2">
              <Zap className="w-4 h-4 text-amber-400" />
              Playbook Library
            </h2>
            <div className="badge badge-neutral gap-1.5">
              <Shield className="w-3 h-3" />
              {playbooks.filter(p => p.enabled).length} Active
            </div>
          </div>

          {loadPb ? (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
              {[...Array(6)].map((_, i) => (
                <div key={i} className="skeleton h-60 rounded-xl" />
              ))}
            </div>
          ) : playbooks.length === 0 ? (
            <div className="empty-state">
              <BookOpen className="empty-state-icon" />
              <p className="empty-state-title">No playbooks found</p>
              <p className="empty-state-body">Run a data ingestion to generate playbooks.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
              {playbooks.map((pb) => {
                const cs   = catStyle(pb.category || 'other');
                const Icon = cs.icon;
                return (
                  <div
                    key={pb.id}
                    className={`relative overflow-hidden bg-slate-900 rounded-xl border transition-all duration-200 ${
                      pb.enabled
                        ? 'border-slate-700 hover:border-slate-600 shadow-lg shadow-black/20'
                        : 'border-slate-800 opacity-55'
                    }`}
                  >
                    {/* Category colour stripe */}
                    <div className={`h-0.5 w-full ${cs.bg}`} />

                    <div className="p-5">
                      {/* Top row: icon + controls */}
                      <div className="flex items-start justify-between mb-4">
                        <div className={`w-10 h-10 rounded-xl flex items-center justify-center border ${cs.bg} ${cs.color} ${cs.border}`}>
                          <Icon className="w-5 h-5" />
                        </div>
                        <div className="flex items-center gap-2">
                          {/* Simulate */}
                          <button
                            onClick={() => simulateMutation.mutate(pb.id)}
                            disabled={!pb.enabled || simulateMutation.isPending}
                            title="Simulate playbook"
                            className={`w-8 h-8 rounded-lg flex items-center justify-center transition-colors ${
                              pb.enabled
                                ? 'bg-primary-600/15 text-primary-400 hover:bg-primary-600/30'
                                : 'bg-slate-800 text-slate-600 cursor-not-allowed'
                            }`}
                          >
                            {simulateMutation.isPending
                              ? <Loader2 className="w-4 h-4 animate-spin" />
                              : <Play className="w-4 h-4" />}
                          </button>
                          {/* Toggle */}
                          <button
                            onClick={() => toggleMutation.mutate({ id: pb.id, enabled: !pb.enabled })}
                            className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                              pb.enabled ? 'bg-primary-600' : 'bg-slate-700'
                            }`}
                          >
                            <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform ${
                              pb.enabled ? 'translate-x-[18px]' : 'translate-x-1'
                            }`} />
                          </button>
                        </div>
                      </div>

                      <h3 className="text-sm font-bold text-white mb-1.5">{pb.name}</h3>
                      <p className="text-xs text-slate-400 mb-5 line-clamp-2 min-h-[2.5rem]">{pb.description}</p>

                      {/* Trigger conditions */}
                      <div className="space-y-2 mb-5">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-[10px] text-slate-500 w-16 shrink-0">Trigger</span>
                          <span className="badge badge-neutral text-[10px]">{pb.trigger.disruption_type}</span>
                          <span className={`badge ${severityBadge(pb.trigger.min_severity || 'medium')} text-[10px]`}>
                            ≥ {pb.trigger.min_severity}
                          </span>
                        </div>
                        {pb.trigger.requires_active_shipment && (
                          <div className="flex items-center gap-2">
                            <span className="text-[10px] text-slate-500 w-16 shrink-0">Condition</span>
                            <span className="text-[10px] text-slate-400">Active shipments required</span>
                          </div>
                        )}
                        {pb.trigger.requires_low_buffer && (
                          <div className="flex items-center gap-2">
                            <span className="text-[10px] text-slate-500 w-16 shrink-0">Buffer</span>
                            <span className="text-[10px] text-slate-400">≤ {pb.trigger.buffer_threshold} days</span>
                          </div>
                        )}
                      </div>

                      {/* Footer stats */}
                      <div className="pt-3 border-t border-slate-800 flex items-center justify-between">
                        <div className="flex items-center gap-1.5 text-xs text-slate-500">
                          <Clock className="w-3.5 h-3.5" />
                          {pb.times_triggered} trigger{pb.times_triggered !== 1 ? 's' : ''}
                        </div>
                        {pb.acceptance_rate !== null ? (
                          <div className="flex items-center gap-2">
                            <div className="text-right">
                              <p className="text-xs font-bold text-emerald-400">{pb.acceptance_rate}%</p>
                              <p className="text-[9px] text-slate-600 uppercase tracking-wide">Acceptance</p>
                            </div>
                            {/* Mini circular progress */}
                            <svg className="w-7 h-7 -rotate-90" viewBox="0 0 36 36">
                              <circle cx="18" cy="18" r="15.9" fill="none" stroke="#1e293b" strokeWidth="3.5" />
                              <circle cx="18" cy="18" r="15.9" fill="none" stroke="#34d399" strokeWidth="3.5"
                                strokeDasharray={`${pb.acceptance_rate} 100`} strokeLinecap="round" />
                            </svg>
                          </div>
                        ) : (
                          <span className="text-[10px] text-slate-600 italic">No feedback yet</span>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {/* ── Execution log ── */}
        <section>
          <div className="flex items-center justify-between mb-5">
            <h2 className="section-title flex items-center gap-2">
              <Activity className="w-4 h-4 text-emerald-400" />
              Execution Log &amp; Feedback
            </h2>
            {executions.length > 0 && (
              <span className="text-xs text-slate-500">{executions.length} execution{executions.length !== 1 ? 's' : ''}</span>
            )}
          </div>

          <div className="card !p-0 overflow-hidden">
            {loadExec ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="w-6 h-6 text-primary-500 animate-spin" />
              </div>
            ) : executions.length === 0 ? (
              <div className="empty-state py-14">
                <Shield className="empty-state-icon" />
                <p className="empty-state-title">No Playbooks Triggered Yet</p>
                <p className="empty-state-body">
                  Playbooks trigger automatically when risk conditions are met during data ingestion,
                  or you can simulate one above.
                </p>
              </div>
            ) : (
              <div className="divide-y divide-slate-800/50">
                {executions.map((exec) => (
                  <div key={exec.execution_id} className="p-6 hover:bg-slate-800/20 transition-colors">
                    <div className="flex flex-col lg:flex-row gap-6">

                      {/* Left: context + actions */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center flex-wrap gap-2 mb-3">
                          <span className={`badge ${severityBadge(exec.severity)}`}>{exec.severity}</span>
                          {exec.is_simulation && (
                            <span className="badge bg-purple-500/10 text-purple-400 border border-purple-500/20">
                              Simulation
                            </span>
                          )}
                          <span className="text-xs text-slate-500 flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {new Date(exec.triggered_at).toLocaleString()}
                          </span>
                        </div>

                        <h3 className="text-sm font-bold text-white mb-0.5">{exec.playbook_name}</h3>
                        <p className="text-xs text-slate-400 mb-4">
                          Triggered by risk on node <span className="text-slate-200 font-semibold">{exec.node_name}</span>
                        </p>

                        <div className="space-y-2">
                          <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Automated Actions</p>
                          {exec.actions.map((action, idx) => (
                            <div key={idx} className="flex gap-3 bg-slate-950/60 px-3 py-2.5 rounded-xl border border-slate-800/60">
                              <div className="w-5 h-5 rounded-full bg-primary-600/15 border border-primary-600/25 flex items-center justify-center text-[10px] text-primary-400 font-bold shrink-0 mt-0.5">
                                {idx + 1}
                              </div>
                              <div>
                                <p className="text-sm text-slate-200">{action.description}</p>
                                <div className="flex gap-2 mt-1.5">
                                  <span className="badge badge-neutral text-[10px]">Target: {action.target}</span>
                                  <span className="badge badge-neutral text-[10px]">{action.urgency?.replace('_', ' ')}</span>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Right: feedback */}
                      <div className="lg:w-64 shrink-0 bg-slate-950/50 rounded-xl border border-slate-800 p-5 flex flex-col justify-center">
                        {exec.status === 'pending' ? (
                          <>
                            <p className="text-sm font-semibold text-white text-center mb-0.5">Review Actions</p>
                            <p className="text-xs text-slate-500 text-center mb-4">Help train the model</p>
                            <div className="flex gap-3">
                              <button
                                onClick={() => feedbackMutation.mutate({ id: exec.execution_id, decision: 'accepted' })}
                                disabled={feedbackMutation.isPending}
                                className="flex-1 py-2 rounded-xl border border-emerald-500/30 bg-emerald-500/8 text-emerald-400 hover:bg-emerald-500/15 flex items-center justify-center gap-2 text-sm font-medium transition-colors disabled:opacity-40"
                              >
                                <ThumbsUp className="w-4 h-4" /> Accept
                              </button>
                              <button
                                onClick={() => feedbackMutation.mutate({ id: exec.execution_id, decision: 'rejected' })}
                                disabled={feedbackMutation.isPending}
                                className="flex-1 py-2 rounded-xl border border-rose-500/30 bg-rose-500/8 text-rose-400 hover:bg-rose-500/15 flex items-center justify-center gap-2 text-sm font-medium transition-colors disabled:opacity-40"
                              >
                                <ThumbsDown className="w-4 h-4" /> Reject
                              </button>
                            </div>
                          </>
                        ) : (
                          <div className="flex flex-col items-center gap-2 py-4">
                            {exec.status === 'accepted' ? (
                              <>
                                <div className="w-12 h-12 rounded-full bg-emerald-500/10 border border-emerald-500/25 flex items-center justify-center">
                                  <ThumbsUp className="w-6 h-6 text-emerald-400" />
                                </div>
                                <p className="text-emerald-400 font-semibold text-sm">Accepted</p>
                              </>
                            ) : (
                              <>
                                <div className="w-12 h-12 rounded-full bg-rose-500/10 border border-rose-500/25 flex items-center justify-center">
                                  <ThumbsDown className="w-6 h-6 text-rose-400" />
                                </div>
                                <p className="text-rose-400 font-semibold text-sm">Rejected</p>
                              </>
                            )}
                            <p className="text-xs text-slate-600">Feedback recorded</p>
                          </div>
                        )}
                      </div>

                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>

      </div>
    </div>
  );
}
