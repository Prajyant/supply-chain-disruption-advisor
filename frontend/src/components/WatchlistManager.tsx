/**
 * WatchlistManager — UI to search vessels by name, view their IMO, and add to watchlist.
 *
 * Provides a search interface that queries the backend /vessels/search endpoint
 * and displays results with copy-to-clipboard for CSV editing.
 */

import { useState } from 'react';
import { Search, Copy, Check, Plus } from 'lucide-react';
import { searchVessels } from '../services/vesselApi';
import type { VesselSearchResult } from '../types/vessel';

export function WatchlistManager() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<VesselSearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [copiedImo, setCopiedImo] = useState<string | null>(null);

  const handleSearch = async () => {
    if (query.length < 2) return;
    setIsSearching(true);
    try {
      const data = await searchVessels(query);
      setResults(data.results);
    } catch (err) {
      console.error('Search failed:', err);
    } finally {
      setIsSearching(false);
    }
  };

  const handleCopy = (vessel: VesselSearchResult) => {
    const csvLine = `${vessel.imo_number},${vessel.name},,,`;
    navigator.clipboard.writeText(csvLine);
    setCopiedImo(vessel.imo_number);
    setTimeout(() => setCopiedImo(null), 2000);
  };

  return (
    <div className="bg-gray-900 border border-gray-700 rounded-lg p-4">
      <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
        <Plus className="w-4 h-4 text-blue-400" />
        Add Vessel to Watchlist
      </h3>

      {/* Search input */}
      <div className="flex gap-2 mb-3">
        <div className="relative flex-1">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
          <input
            type="text"
            placeholder="Search by vessel name..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            className="w-full pl-8 pr-3 py-2 text-sm bg-gray-800 border border-gray-600 rounded text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
          />
        </div>
        <button
          onClick={handleSearch}
          disabled={isSearching || query.length < 2}
          className="px-3 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {isSearching ? '...' : 'Search'}
        </button>
      </div>

      {/* Results */}
      {results.length > 0 && (
        <div className="space-y-1 max-h-60 overflow-y-auto">
          {results.map((vessel) => (
            <div
              key={vessel.imo_number}
              className="flex items-center justify-between px-3 py-2 bg-gray-800 rounded hover:bg-gray-750"
            >
              <div>
                <p className="text-xs font-medium text-white">{vessel.name}</p>
                <p className="text-xs text-gray-500">
                  IMO: {vessel.imo_number} | {vessel.vessel_type || 'Unknown'} | {vessel.flag || '?'}
                </p>
              </div>
              <button
                onClick={() => handleCopy(vessel)}
                className="p-1 rounded hover:bg-gray-700"
                title="Copy CSV line to clipboard"
              >
                {copiedImo === vessel.imo_number ? (
                  <Check className="w-4 h-4 text-green-400" />
                ) : (
                  <Copy className="w-4 h-4 text-gray-400" />
                )}
              </button>
            </div>
          ))}
        </div>
      )}

      {results.length === 0 && query.length >= 2 && !isSearching && (
        <p className="text-xs text-gray-500 text-center py-2">
          No results. Try a different search term.
        </p>
      )}

      <p className="text-xs text-gray-600 mt-3">
        Copy the CSV line and paste it into <code className="text-gray-400">watchlist.csv</code>,
        then click "Reload" to start tracking.
      </p>
    </div>
  );
}
