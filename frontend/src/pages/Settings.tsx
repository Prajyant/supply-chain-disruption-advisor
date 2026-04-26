import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { ingestApi } from '../services/api';
import { Upload, RefreshCw, CheckCircle, AlertCircle, Mail, Database, Info } from 'lucide-react';

export function Settings() {
  const [useRealtime, setUseRealtime] = useState(true);
  const [useLiveEmails, setUseLiveEmails] = useState(false);
  const queryClient = useQueryClient();

  const ingestMutation = useMutation({
    mutationFn: () =>
      ingestApi.ingest({
        supplier_emails_path: 'data/supplier_emails.csv',
        news_feed_path: 'data/news_feed.csv',
        inventory_path: 'data/inventory.csv',
        use_realtime_news: useRealtime,
        use_live_emails: useLiveEmails,
      }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['risks'] });
      alert(`✅ Ingested ${data.data.ingested_events} events\n${data.data.message}`);
    },
    onError: () => {
      alert('❌ Ingestion failed. Check the backend logs for details.');
    },
  });

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white">Settings</h1>
        <p className="text-slate-400">Configure data sources and ingestion options</p>
      </div>

      <div className="space-y-6">

        {/* Email Source Toggle */}
        <div className="card">
          <h2 className="text-lg font-semibold text-white mb-1">Email Source</h2>
          <p className="text-sm text-slate-400 mb-4">
            Choose whether to scan your live Gmail inbox or use the built-in sample emails for testing.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* CSV / Sample Data option */}
            <button
              onClick={() => setUseLiveEmails(false)}
              className={`flex items-start gap-3 p-4 rounded-lg border-2 text-left transition-all ${
                !useLiveEmails
                  ? 'border-blue-500 bg-blue-500/10'
                  : 'border-slate-600 bg-slate-800 hover:border-slate-500'
              }`}
            >
              <Database className={`w-5 h-5 mt-0.5 flex-shrink-0 ${!useLiveEmails ? 'text-blue-400' : 'text-slate-400'}`} />
              <div>
                <p className={`font-medium ${!useLiveEmails ? 'text-blue-300' : 'text-slate-300'}`}>
                  Sample / Hardcoded Data
                </p>
                <p className="text-xs text-slate-400 mt-1">
                  Uses the built-in <code className="text-slate-300">supplier_emails.csv</code> file.
                  Great for testing and demos — always works, no credentials needed.
                </p>
              </div>
            </button>

            {/* Live Gmail option */}
            <button
              onClick={() => setUseLiveEmails(true)}
              className={`flex items-start gap-3 p-4 rounded-lg border-2 text-left transition-all ${
                useLiveEmails
                  ? 'border-emerald-500 bg-emerald-500/10'
                  : 'border-slate-600 bg-slate-800 hover:border-slate-500'
              }`}
            >
              <Mail className={`w-5 h-5 mt-0.5 flex-shrink-0 ${useLiveEmails ? 'text-emerald-400' : 'text-slate-400'}`} />
              <div>
                <p className={`font-medium ${useLiveEmails ? 'text-emerald-300' : 'text-slate-300'}`}>
                  Live Gmail Inbox
                </p>
                <p className="text-xs text-slate-400 mt-1">
                  Reads the 15 most recent emails from your configured Gmail account.
                  Requires <code className="text-slate-300">GMAIL_USER</code> and{' '}
                  <code className="text-slate-300">GMAIL_APP_PASSWORD</code> in your <code className="text-slate-300">.env</code> file.
                </p>
              </div>
            </button>
          </div>

          {/* Workflow guide for live emails */}
          {useLiveEmails && (
            <div className="mt-4 p-4 rounded-lg bg-emerald-900/20 border border-emerald-700/40">
              <div className="flex items-center gap-2 mb-2">
                <Info className="w-4 h-4 text-emerald-400" />
                <span className="text-sm font-medium text-emerald-300">How to send a test disruption email</span>
              </div>
              <ol className="text-xs text-slate-300 space-y-1 list-decimal list-inside">
                <li>Open your personal email account.</li>
                <li>Send an email <strong>to</strong> your configured fake Gmail address.</li>
                <li>
                  Use a subject like:{' '}
                  <span className="font-mono text-yellow-300">Port congestion delay — Alpha Metals shipment</span>
                </li>
                <li>
                  In the body, describe the disruption, e.g.:{' '}
                  <span className="italic text-slate-400">
                    "Our copper shipment from Shanghai is delayed by 7 days due to port congestion."
                  </span>
                </li>
                <li>Wait a few seconds, then click <strong>Ingest Data</strong> below.</li>
                <li>Check the Dashboard — your sender name should appear as a new node on the Digital Twin map!</li>
              </ol>
              <p className="text-xs text-slate-500 mt-3">
                💡 Tip: Words like <em>bankruptcy, strike, flood, cyberattack, quality recall</em> trigger higher severity alerts.
              </p>
            </div>
          )}
        </div>

        {/* News & Other Sources */}
        <div className="card">
          <h2 className="text-lg font-semibold text-white mb-4">News & Other Data Sources</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-slate-400 mb-2">Inventory CSV</label>
              <input
                type="text"
                defaultValue="data/inventory.csv"
                className="input w-full"
              />
            </div>
            <div>
              <label className="block text-sm text-slate-400 mb-2">News Feed CSV (fallback)</label>
              <input
                type="text"
                defaultValue="data/news_feed.csv"
                className="input w-full"
              />
            </div>
            <div className="col-span-2 flex items-center gap-2">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={useRealtime}
                  onChange={(e) => setUseRealtime(e.target.checked)}
                  className="w-4 h-4 rounded"
                />
                <span className="text-sm text-slate-300">
                  Fetch Real-Time News (Reuters, BBC, Supply Chain Dive)
                </span>
              </label>
            </div>
          </div>
        </div>

        {/* Ingestion Controls */}
        <div className="card">
          <h2 className="text-lg font-semibold text-white mb-2">Ingestion Controls</h2>
          <p className="text-sm text-slate-400 mb-4">
            Current mode:{' '}
            <span className={useLiveEmails ? 'text-emerald-400 font-medium' : 'text-blue-400 font-medium'}>
              {useLiveEmails ? '📬 Live Gmail Inbox' : '📁 Sample CSV Data'}
            </span>
            {useRealtime && (
              <span className="text-slate-400"> + <span className="text-purple-400">🌐 Real-Time News</span></span>
            )}
          </p>
          <div className="flex gap-4">
            <button
              onClick={() => ingestMutation.mutate()}
              disabled={ingestMutation.isPending}
              className="btn-primary flex items-center gap-2 disabled:opacity-50"
            >
              {ingestMutation.isPending ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  Ingesting...
                </>
              ) : (
                <>
                  <Upload className="w-4 h-4" />
                  Ingest Data
                </>
              )}
            </button>
            <button
              onClick={() => queryClient.invalidateQueries({ queryKey: ['risks'] })}
              className="btn-secondary flex items-center gap-2"
            >
              <RefreshCw className="w-4 h-4" />
              Refresh Dashboard
            </button>
          </div>
        </div>

        {/* System Status */}
        <div className="card">
          <h2 className="text-lg font-semibold text-white mb-4">System Status</h2>
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <CheckCircle className="w-5 h-5 text-green-500" />
              <span className="text-slate-300">Backend API: Online</span>
            </div>
            <div className="flex items-center gap-3">
              <CheckCircle className="w-5 h-5 text-green-500" />
              <span className="text-slate-300">WebSocket: Connected</span>
            </div>
            <div className="flex items-center gap-3">
              <AlertCircle className="w-5 h-5 text-yellow-500" />
              <span className="text-slate-300">Background Workers: Active</span>
            </div>
            <div className="flex items-center gap-3">
              {useLiveEmails ? (
                <CheckCircle className="w-5 h-5 text-emerald-500" />
              ) : (
                <AlertCircle className="w-5 h-5 text-blue-400" />
              )}
              <span className="text-slate-300">
                Email Source: {useLiveEmails ? 'Live Gmail Inbox' : 'Sample CSV Data'}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
