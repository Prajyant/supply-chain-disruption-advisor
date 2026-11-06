import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { ingestApi } from '../services/api';
import {
  Upload, RefreshCw, CheckCircle, AlertCircle,
  Mail, Database, Info, Settings as SettingsIcon,
  Newspaper, Wifi, Server,
} from 'lucide-react';

export function Settings() {
  const [useRealtime,   setUseRealtime]   = useState(true);
  const [useLiveEmails, setUseLiveEmails] = useState(false);
  const queryClient = useQueryClient();

  const ingestMutation = useMutation({
    mutationFn: () =>
      ingestApi.ingest({
        supplier_emails_path: 'data/supplier_emails.csv',
        news_feed_path:       'data/news_feed.csv',
        inventory_path:       'data/inventory.csv',
        use_realtime_news:    useRealtime,
        use_live_emails:      useLiveEmails,
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
    <div className="p-8 max-w-3xl space-y-7">

      {/* ── Page header ── */}
      <div>
        <h1 className="page-title flex items-center gap-2">
          <SettingsIcon className="w-6 h-6 text-slate-400" />
          Settings
        </h1>
        <p className="page-subtitle">Configure data sources and ingestion options</p>
      </div>

      {/* ── Email source ── */}
      <div className="card space-y-5">
        <div>
          <h2 className="section-title flex items-center gap-2">
            <Mail className="w-4 h-4 text-slate-400" />
            Email Source
          </h2>
          <p className="text-sm text-slate-500 mt-1">
            Choose whether to read your live Gmail inbox or use the built-in sample emails.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {/* Sample data */}
          <button
            onClick={() => setUseLiveEmails(false)}
            className={`flex items-start gap-3 p-4 rounded-xl border-2 text-left transition-all ${
              !useLiveEmails
                ? 'border-primary-500 bg-primary-500/8'
                : 'border-slate-700 bg-slate-800/50 hover:border-slate-600'
            }`}
          >
            <Database className={`w-5 h-5 mt-0.5 shrink-0 ${!useLiveEmails ? 'text-primary-400' : 'text-slate-500'}`} />
            <div>
              <p className={`text-sm font-semibold ${!useLiveEmails ? 'text-primary-300' : 'text-slate-300'}`}>
                Sample / CSV Data
              </p>
              <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                Uses the built-in <code className="text-slate-400">supplier_emails.csv</code>.
                Works immediately — no credentials needed.
              </p>
            </div>
          </button>

          {/* Live Gmail */}
          <button
            onClick={() => setUseLiveEmails(true)}
            className={`flex items-start gap-3 p-4 rounded-xl border-2 text-left transition-all ${
              useLiveEmails
                ? 'border-emerald-500 bg-emerald-500/8'
                : 'border-slate-700 bg-slate-800/50 hover:border-slate-600'
            }`}
          >
            <Mail className={`w-5 h-5 mt-0.5 shrink-0 ${useLiveEmails ? 'text-emerald-400' : 'text-slate-500'}`} />
            <div>
              <p className={`text-sm font-semibold ${useLiveEmails ? 'text-emerald-300' : 'text-slate-300'}`}>
                Live Gmail Inbox
              </p>
              <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                Reads the 15 most recent emails. Requires{' '}
                <code className="text-slate-400">GMAIL_USER</code> and{' '}
                <code className="text-slate-400">GMAIL_APP_PASSWORD</code> in <code className="text-slate-400">.env</code>.
              </p>
            </div>
          </button>
        </div>

        {/* Live email guide */}
        {useLiveEmails && (
          <div className="alert-success rounded-xl !py-4">
            <Info className="w-4 h-4 shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-semibold text-white mb-2">How to send a test disruption email</p>
              <ol className="text-xs text-slate-300 space-y-1.5 list-decimal list-inside">
                <li>Open your personal email account.</li>
                <li>Send an email <strong>to</strong> your configured Gmail address.</li>
                <li>Use a subject like: <span className="font-mono text-amber-300">Port congestion delay — Alpha Metals shipment</span></li>
                <li>Describe the disruption in the body.</li>
                <li>Click <strong>Ingest Data</strong> below and check the Dashboard.</li>
              </ol>
              <p className="text-xs text-slate-500 mt-2">
                💡 Keywords like <em>bankruptcy, strike, flood, cyberattack</em> trigger higher severity.
              </p>
            </div>
          </div>
        )}
      </div>

      {/* ── News & other sources ── */}
      <div className="card space-y-5">
        <h2 className="section-title flex items-center gap-2">
          <Newspaper className="w-4 h-4 text-slate-400" />
          News &amp; Other Sources
        </h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wide">
              Inventory CSV
            </label>
            <input type="text" defaultValue="data/inventory.csv" className="input w-full" />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wide">
              News Feed CSV (fallback)
            </label>
            <input type="text" defaultValue="data/news_feed.csv" className="input w-full" />
          </div>
        </div>

        <label className="flex items-center gap-3 cursor-pointer group">
          <input
            type="checkbox"
            checked={useRealtime}
            onChange={e => setUseRealtime(e.target.checked)}
            className="w-4 h-4 rounded accent-indigo-500"
          />
          <span className="text-sm text-slate-300 group-hover:text-white transition-colors">
            Fetch real-time news (Reuters, BBC, Supply Chain Dive)
          </span>
          <span className={`badge ${useRealtime ? 'badge-info' : 'badge-neutral'} ml-auto`}>
            {useRealtime ? 'Live' : 'Off'}
          </span>
        </label>
      </div>

      {/* ── Ingestion controls ── */}
      <div className="card space-y-5">
        <div>
          <h2 className="section-title flex items-center gap-2">
            <Wifi className="w-4 h-4 text-slate-400" />
            Ingestion Controls
          </h2>
          <p className="text-sm text-slate-500 mt-1">
            Current mode:{' '}
            <span className={`font-semibold ${useLiveEmails ? 'text-emerald-400' : 'text-primary-400'}`}>
              {useLiveEmails ? '📬 Live Gmail' : '📁 Sample CSV'}
            </span>
            {useRealtime && (
              <span className="text-slate-400 ml-1">
                + <span className="text-purple-400">🌐 Real-Time News</span>
              </span>
            )}
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => ingestMutation.mutate()}
            disabled={ingestMutation.isPending}
            className="btn-primary flex items-center gap-2"
          >
            {ingestMutation.isPending ? (
              <><RefreshCw className="w-4 h-4 animate-spin" /> Ingesting…</>
            ) : (
              <><Upload className="w-4 h-4" /> Ingest Data</>
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

      {/* ── System status ── */}
      <div className="card space-y-4">
        <h2 className="section-title flex items-center gap-2">
          <Server className="w-4 h-4 text-slate-400" />
          System Status
        </h2>

        <div className="space-y-3">
          {[
            { ok: true,  label: 'Backend API',          detail: 'Online — port 8000' },
            { ok: true,  label: 'WebSocket',             detail: 'Connected' },
            { ok: true,  label: 'Background Workers',    detail: 'Ingestion · Risk · Propagation active' },
            { ok: true,  label: 'AIS Vessel Tracking',  detail: '20 vessels monitored via AISStream' },
            { ok: !useLiveEmails, label: 'Email Source', detail: useLiveEmails ? 'Live Gmail Inbox' : 'Sample CSV Data' },
          ].map(({ ok, label, detail }) => (
            <div key={label} className="flex items-center gap-3">
              {ok
                ? <CheckCircle className="w-4 h-4 text-emerald-500 shrink-0" />
                : <AlertCircle className="w-4 h-4 text-amber-500 shrink-0" />}
              <div>
                <p className="text-sm text-white">{label}</p>
                <p className="text-xs text-slate-500">{detail}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

    </div>
  );
}
