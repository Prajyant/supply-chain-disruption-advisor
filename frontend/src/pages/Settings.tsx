import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { ingestApi } from '../services/api';
import { Upload, RefreshCw, CheckCircle, AlertCircle } from 'lucide-react';

export function Settings() {
  const [useRealtime, setUseRealtime] = useState(true);
  const queryClient = useQueryClient();

  const ingestMutation = useMutation({
    mutationFn: () =>
      ingestApi.ingest({
        supplier_emails_path: 'data/supplier_emails.csv',
        news_feed_path: 'data/news_feed.csv',
        inventory_path: 'data/inventory.csv',
        use_realtime_news: useRealtime,
      }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['risks'] });
      alert(`Ingested ${data.data.ingested_events} events`);
    },
  });

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white">Settings</h1>
        <p className="text-slate-400">Configure data sources and ingestion options</p>
      </div>

      <div className="space-y-6">
        {/* Data Sources */}
        <div className="card">
          <h2 className="text-lg font-semibold text-white mb-4">Data Sources</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-slate-400 mb-2">
                Supplier Emails CSV
              </label>
              <input
                type="text"
                defaultValue="data/supplier_emails.csv"
                className="input w-full"
              />
            </div>
            <div>
              <label className="block text-sm text-slate-400 mb-2">
                Inventory CSV
              </label>
              <input
                type="text"
                defaultValue="data/inventory.csv"
                className="input w-full"
              />
            </div>
            <div>
              <label className="block text-sm text-slate-400 mb-2">
                News Feed CSV (fallback)
              </label>
              <input
                type="text"
                defaultValue="data/news_feed.csv"
                className="input w-full"
              />
            </div>
            <div className="flex items-end">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={useRealtime}
                  onChange={(e) => setUseRealtime(e.target.checked)}
                  className="w-4 h-4 rounded"
                />
                <span className="text-sm text-slate-300">
                  Use Real-Time News Feeds
                </span>
              </label>
            </div>
          </div>
        </div>

        {/* Ingestion Controls */}
        <div className="card">
          <h2 className="text-lg font-semibold text-white mb-4">Ingestion Controls</h2>
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
              Refresh Risks
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
          </div>
        </div>
      </div>
    </div>
  );
}
