import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { playbookApi } from '../services/api';
import {
  Zap,
  Play,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Clock,
  Shield,
  Truck,
  Building2,
  Activity,
  ThumbsUp,
  ThumbsDown,
  Loader2,
  Settings2,
} from 'lucide-react';
import { PlaybookWithStats, PlaybookExecution } from '../types';

// Helper for disruption category styling
const getCategoryStyles = (category: string) => {
  switch (category) {
    case 'logistics':
      return { icon: Truck, color: 'text-blue-400', bg: 'bg-blue-400/10', border: 'border-blue-400/20' };
    case 'natural_disaster':
      return { icon: AlertTriangle, color: 'text-rose-400', bg: 'bg-rose-400/10', border: 'border-rose-400/20' };
    case 'operations':
      return { icon: Building2, color: 'text-amber-400', bg: 'bg-amber-400/10', border: 'border-amber-400/20' };
    case 'security':
      return { icon: Shield, color: 'text-purple-400', bg: 'bg-purple-400/10', border: 'border-purple-400/20' };
    case 'financial':
      return { icon: Activity, color: 'text-emerald-400', bg: 'bg-emerald-400/10', border: 'border-emerald-400/20' };
    default:
      return { icon: Zap, color: 'text-slate-400', bg: 'bg-slate-400/10', border: 'border-slate-400/20' };
  }
};

const getSeverityColor = (severity: string) => {
  switch (severity) {
    case 'critical': return 'text-rose-400 bg-rose-400/10 border-rose-400/20';
    case 'high': return 'text-orange-400 bg-orange-400/10 border-orange-400/20';
    case 'medium': return 'text-amber-400 bg-amber-400/10 border-amber-400/20';
    default: return 'text-emerald-400 bg-emerald-400/10 border-emerald-400/20';
  }
};

export function Playbooks() {
  const queryClient = useQueryClient();
  const [toastMessage, setToastMessage] = useState<{title: string, message: string, type: 'success' | 'warning' | 'error'} | null>(null);

  // Auto-hide toast
  useEffect(() => {
    if (toastMessage) {
      const timer = setTimeout(() => setToastMessage(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [toastMessage]);

  // Fetch Playbooks
  const { data: playbooksData, isLoading: isLoadingPlaybooks } = useQuery({
    queryKey: ['playbooks'],
    queryFn: () => playbookApi.getPlaybooks().then((res) => res.data),
  });

  // Fetch Executions
  const { data: executionsData, isLoading: isLoadingExecutions } = useQuery({
    queryKey: ['playbook-executions'],
    queryFn: () => playbookApi.getExecutions().then((res) => res.data),
    refetchInterval: 10000, // Refresh every 10s
  });

  // Toggle Mutation
  const toggleMutation = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      playbookApi.togglePlaybook(id, enabled),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['playbooks'] });
      setToastMessage({
        title: 'Settings Updated',
        message: data.data.warning || 'Playbook toggled successfully.',
        type: 'warning',
      });
    },
  });

  // Simulate Mutation
  const simulateMutation = useMutation({
    mutationFn: (id: string) => playbookApi.simulate(id),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['playbook-executions'] });
      queryClient.invalidateQueries({ queryKey: ['playbooks'] });
      setToastMessage({
        title: 'Simulation Started',
        message: data.data.message,
        type: 'success',
      });
    },
    onError: (error: any) => {
      setToastMessage({
        title: 'Simulation Failed',
        message: error.response?.data?.detail || 'Failed to simulate playbook.',
        type: 'error',
      });
    }
  });

  // Feedback Mutation
  const feedbackMutation = useMutation({
    mutationFn: ({ executionId, decision, comment }: { executionId: string; decision: string; comment?: string }) =>
      playbookApi.submitFeedback(executionId, decision, comment),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['playbook-executions'] });
      queryClient.invalidateQueries({ queryKey: ['playbooks'] });
      setToastMessage({
        title: 'Feedback Recorded',
        message: data.data.message,
        type: 'success',
      });
    },
    onError: (error: any) => {
      // Handle 409 Conflict gracefully
      if (error.response?.status === 409) {
        setToastMessage({
          title: 'Feedback Already Recorded',
          message: 'You have already submitted feedback for this execution.',
          type: 'warning',
        });
      } else {
        setToastMessage({
          title: 'Error',
          message: 'Failed to record feedback.',
          type: 'error',
        });
      }
    }
  });

  const playbooks = (playbooksData?.playbooks || []) as PlaybookWithStats[];
  const executions = (executionsData?.executions || []) as PlaybookExecution[];

  return (
    <div className="p-8 h-full flex flex-col relative overflow-hidden bg-slate-950">
      {/* Toast Notification */}
      {toastMessage && (
        <div className={`absolute top-8 right-8 z-50 p-4 rounded-lg shadow-xl border backdrop-blur-md max-w-md animate-in slide-in-from-top-4 fade-in ${
          toastMessage.type === 'success' ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' :
          toastMessage.type === 'warning' ? 'bg-amber-500/10 border-amber-500/30 text-amber-400' :
          'bg-rose-500/10 border-rose-500/30 text-rose-400'
        }`}>
          <div className="flex gap-3">
            {toastMessage.type === 'success' && <CheckCircle2 className="w-5 h-5 shrink-0" />}
            {toastMessage.type === 'warning' && <AlertTriangle className="w-5 h-5 shrink-0" />}
            {toastMessage.type === 'error' && <XCircle className="w-5 h-5 shrink-0" />}
            <div>
              <h4 className="font-medium text-white">{toastMessage.title}</h4>
              <p className="text-sm mt-1 opacity-90">{toastMessage.message}</p>
            </div>
            <button onClick={() => setToastMessage(null)} className="ml-auto opacity-70 hover:opacity-100">
              <XCircle className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white flex items-center gap-3">
          <Settings2 className="w-6 h-6 text-primary-400" />
          Automated Playbooks
        </h1>
        <p className="text-slate-400 mt-1">Rule-based response templates with reinforcement learning feedback loops.</p>
      </div>

      <div className="flex-1 overflow-auto -mr-4 pr-4 custom-scrollbar space-y-12 pb-12">
        {/* Playbook Library Section */}
        <section>
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              <Zap className="w-5 h-5 text-amber-400" />
              Playbook Library
            </h2>
            <div className="text-sm text-slate-400 bg-slate-900 px-3 py-1.5 rounded-full border border-slate-800 flex items-center gap-2">
              <Shield className="w-4 h-4" />
              <span>8 Active Rules</span>
            </div>
          </div>

          {isLoadingPlaybooks ? (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
              {[...Array(6)].map((_, i) => (
                <div key={i} className="h-64 bg-slate-900/50 rounded-xl border border-slate-800 animate-pulse"></div>
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
              {playbooks.map((pb) => {
                const catStyles = getCategoryStyles(pb.category);
                const Icon = catStyles.icon;
                
                return (
                  <div 
                    key={pb.id} 
                    className={`relative overflow-hidden bg-slate-900 rounded-xl border transition-all duration-300 ${
                      pb.enabled ? 'border-slate-700 hover:border-slate-500 shadow-lg shadow-black/20' : 'border-slate-800 opacity-60'
                    }`}
                  >
                    {/* Top color bar */}
                    <div className={`h-1 w-full ${catStyles.bg}`}></div>
                    
                    <div className="p-5">
                      <div className="flex justify-between items-start mb-4">
                        <div className={`w-10 h-10 rounded-lg flex items-center justify-center border ${catStyles.bg} ${catStyles.color} ${catStyles.border}`}>
                          <Icon className="w-5 h-5" />
                        </div>
                        <div className="flex items-center gap-3">
                          {/* Simulate Button (Demo feature) */}
                          <button
                            onClick={() => simulateMutation.mutate(pb.id)}
                            disabled={!pb.enabled || simulateMutation.isPending}
                            className={`p-2 rounded-lg transition-colors ${
                              pb.enabled 
                                ? 'bg-primary-600/20 text-primary-400 hover:bg-primary-600/40' 
                                : 'bg-slate-800 text-slate-500 cursor-not-allowed'
                            }`}
                            title="Simulate playbook trigger"
                          >
                            <Play className="w-4 h-4" />
                          </button>
                          
                          {/* Enable/Disable Toggle */}
                          <button
                            onClick={() => toggleMutation.mutate({ id: pb.id, enabled: !pb.enabled })}
                            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                              pb.enabled ? 'bg-primary-600' : 'bg-slate-700'
                            }`}
                          >
                            <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                              pb.enabled ? 'translate-x-6' : 'translate-x-1'
                            }`} />
                          </button>
                        </div>
                      </div>

                      <h3 className="text-lg font-medium text-white mb-2">{pb.name}</h3>
                      <p className="text-sm text-slate-400 mb-6 line-clamp-2 h-10">{pb.description}</p>

                      <div className="space-y-3 mb-6">
                        <div className="flex items-center gap-2 text-xs">
                          <span className="text-slate-500 w-24">Trigger:</span>
                          <span className="bg-slate-800 text-slate-300 px-2 py-0.5 rounded border border-slate-700">
                            {pb.trigger.disruption_type}
                          </span>
                          <span className={`px-2 py-0.5 rounded border text-[10px] uppercase tracking-wider font-semibold ${getSeverityColor(pb.trigger.min_severity)}`}>
                            ≥ {pb.trigger.min_severity}
                          </span>
                        </div>
                        {pb.trigger.requires_active_shipment && (
                          <div className="flex items-center gap-2 text-xs">
                            <span className="text-slate-500 w-24">Condition:</span>
                            <span className="text-slate-300">Active shipments required</span>
                          </div>
                        )}
                        {pb.trigger.requires_low_buffer && (
                          <div className="flex items-center gap-2 text-xs">
                            <span className="text-slate-500 w-24">Condition:</span>
                            <span className="text-slate-300">Buffer ≤ {pb.trigger.buffer_threshold} days</span>
                          </div>
                        )}
                      </div>

                      {/* Footer Stats */}
                      <div className="pt-4 border-t border-slate-800 flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Clock className="w-4 h-4 text-slate-500" />
                          <span className="text-xs text-slate-400">{pb.times_triggered} triggers</span>
                        </div>
                        {pb.acceptance_rate !== null ? (
                          <div className="flex items-center gap-2">
                            <div className="text-right">
                              <div className="text-xs font-semibold text-emerald-400">{pb.acceptance_rate}%</div>
                              <div className="text-[10px] text-slate-500 uppercase tracking-wider">Acceptance</div>
                            </div>
                            {/* Circular progress indicator */}
                            <div className="w-8 h-8 rounded-full border-2 border-slate-800 flex items-center justify-center relative overflow-hidden bg-slate-900">
                              <svg className="w-full h-full transform -rotate-90 absolute" viewBox="0 0 36 36">
                                <path
                                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                                  fill="none"
                                  stroke="#0f172a"
                                  strokeWidth="3"
                                />
                                <path
                                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                                  fill="none"
                                  stroke="#34d399"
                                  strokeWidth="3"
                                  strokeDasharray={`${pb.acceptance_rate}, 100`}
                                />
                              </svg>
                            </div>
                          </div>
                        ) : (
                          <span className="text-xs text-slate-600 italic">No feedback yet</span>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {/* Execution Log Section */}
        <section>
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              <Activity className="w-5 h-5 text-emerald-400" />
              Execution Log & Feedback
            </h2>
          </div>

          <div className="bg-slate-900 rounded-xl border border-slate-800 overflow-hidden">
            {isLoadingExecutions ? (
              <div className="p-8 flex justify-center">
                <Loader2 className="w-8 h-8 text-primary-500 animate-spin" />
              </div>
            ) : executions.length === 0 ? (
              <div className="p-12 text-center">
                <Shield className="w-12 h-12 text-slate-700 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-slate-300">No Playbooks Triggered</h3>
                <p className="text-slate-500 mt-1 max-w-md mx-auto">
                  Playbooks will appear here automatically when risk conditions are met during data ingestion.
                </p>
              </div>
            ) : (
              <div className="divide-y divide-slate-800/50">
                {executions.map((exec) => (
                  <div key={exec.execution_id} className="p-6 transition-colors hover:bg-slate-800/30">
                    <div className="flex flex-col lg:flex-row gap-6">
                      
                      {/* Left: Context */}
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-3">
                          <span className={`px-2 py-1 rounded text-xs font-semibold uppercase tracking-wider border ${getSeverityColor(exec.severity)}`}>
                            {exec.severity}
                          </span>
                          {exec.is_simulation && (
                            <span className="px-2 py-1 rounded text-xs font-semibold uppercase tracking-wider bg-purple-500/10 text-purple-400 border border-purple-500/20">
                              SIMULATION
                            </span>
                          )}
                          <span className="text-sm text-slate-400 flex items-center gap-1">
                            <Clock className="w-4 h-4" />
                            {new Date(exec.triggered_at).toLocaleString()}
                          </span>
                        </div>
                        
                        <h3 className="text-lg font-medium text-white mb-1">{exec.playbook_name}</h3>
                        <p className="text-sm text-slate-400 mb-4">
                          Triggered by risk on node <strong className="text-slate-200">{exec.node_name}</strong>
                        </p>

                        {/* Action Steps */}
                        <div className="space-y-3 mt-4">
                          <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Automated Actions</h4>
                          {exec.actions.map((action, idx) => (
                            <div key={idx} className="flex gap-3 bg-slate-950 p-3 rounded-lg border border-slate-800/60">
                              <div className="mt-0.5">
                                <div className="w-5 h-5 rounded-full bg-primary-600/20 flex items-center justify-center border border-primary-600/30">
                                  <span className="text-[10px] text-primary-400 font-bold">{idx + 1}</span>
                                </div>
                              </div>
                              <div>
                                <p className="text-sm text-slate-200">{action.description}</p>
                                <div className="flex gap-3 mt-2 text-xs text-slate-500 font-medium">
                                  <span className="capitalize text-slate-400 bg-slate-800 px-1.5 py-0.5 rounded">
                                    Target: {action.target}
                                  </span>
                                  <span className="capitalize bg-slate-800 px-1.5 py-0.5 rounded">
                                    {action.urgency.replace('_', ' ')}
                                  </span>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Right: Feedback Loop */}
                      <div className="lg:w-72 flex flex-col justify-center bg-slate-950/50 rounded-xl p-5 border border-slate-800">
                        {exec.status === 'pending' ? (
                          <>
                            <div className="text-center mb-4">
                              <h4 className="text-sm font-medium text-slate-300">Review Actions</h4>
                              <p className="text-xs text-slate-500 mt-1">Help train the model by providing feedback</p>
                            </div>
                            <div className="flex gap-3">
                              <button
                                onClick={() => feedbackMutation.mutate({ executionId: exec.execution_id, decision: 'accepted' })}
                                disabled={feedbackMutation.isPending}
                                className="flex-1 py-2 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 rounded-lg border border-emerald-500/30 flex items-center justify-center gap-2 transition-colors disabled:opacity-50"
                              >
                                <ThumbsUp className="w-4 h-4" />
                                <span>Accept</span>
                              </button>
                              <button
                                onClick={() => feedbackMutation.mutate({ executionId: exec.execution_id, decision: 'rejected' })}
                                disabled={feedbackMutation.isPending}
                                className="flex-1 py-2 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 rounded-lg border border-rose-500/30 flex items-center justify-center gap-2 transition-colors disabled:opacity-50"
                              >
                                <ThumbsDown className="w-4 h-4" />
                                <span>Reject</span>
                              </button>
                            </div>
                          </>
                        ) : (
                          <div className="text-center py-4">
                            {exec.status === 'accepted' ? (
                              <div className="inline-flex flex-col items-center">
                                <div className="w-12 h-12 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center justify-center mb-3 shadow-[0_0_15px_rgba(52,211,153,0.15)]">
                                  <ThumbsUp className="w-6 h-6" />
                                </div>
                                <span className="text-emerald-400 font-medium">Actions Accepted</span>
                                <span className="text-xs text-slate-500 mt-1">Feedback recorded</span>
                              </div>
                            ) : (
                              <div className="inline-flex flex-col items-center">
                                <div className="w-12 h-12 rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/20 flex items-center justify-center mb-3 shadow-[0_0_15px_rgba(244,63,94,0.15)]">
                                  <ThumbsDown className="w-6 h-6" />
                                </div>
                                <span className="text-rose-400 font-medium">Actions Rejected</span>
                                <span className="text-xs text-slate-500 mt-1">Feedback recorded</span>
                              </div>
                            )}
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
