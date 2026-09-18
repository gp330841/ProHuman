import React, { useState } from 'react';
import { Search, SlidersHorizontal, Clock, User } from 'lucide-react';
import { runHybridSearch, SearchResult } from '../api/client';

export const SearchExplorer: React.FC = () => {
  const [query, setQuery] = useState('');
  const [searchMode, setSearchMode] = useState<'HYBRID' | 'SEMANTIC' | 'LEXICAL'>('HYBRID');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    try {
      setIsSearching(true);
      setHasSearched(true);
      const res = await runHybridSearch(query.trim(), searchMode);
      setResults(res);
    } catch (err) {
      console.error(err);
      setResults([]);
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-6 shadow-xl backdrop-blur">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-bold text-white flex items-center gap-2">
            <Search className="w-5 h-5 text-sky-400" />
            Hybrid Search Explorer (pgvector + tsvector)
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Test Reciprocal Rank Fusion (RRF k=60) combining semantic vector cosine similarity with BM25 lexical ranking.
          </p>
        </div>
      </div>

      <form onSubmit={handleSearch} className="space-y-4 mb-6">
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. 'budget forecast for Q3', 'renegotiating vendor agreement'..."
              className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-10 pr-4 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-sky-500 transition"
            />
          </div>
          <button
            type="submit"
            disabled={isSearching || !query.trim()}
            className="px-5 py-2 bg-sky-600 hover:bg-sky-500 disabled:bg-slate-800 text-white font-medium rounded-lg text-sm transition"
          >
            {isSearching ? 'Searching...' : 'Search'}
          </button>
        </div>

        {/* Search Mode Toggles */}
        <div className="flex items-center gap-4 text-xs">
          <span className="text-slate-400 flex items-center gap-1">
            <SlidersHorizontal className="w-3.5 h-3.5" /> Search Mode:
          </span>
          {(['HYBRID', 'SEMANTIC', 'LEXICAL'] as const).map((mode) => (
            <label key={mode} className="flex items-center gap-1.5 cursor-pointer text-slate-300">
              <input
                type="radio"
                name="searchMode"
                value={mode}
                checked={searchMode === mode}
                onChange={() => setSearchMode(mode)}
                className="text-sky-500 focus:ring-sky-500 bg-slate-800 border-slate-700"
              />
              <span className={searchMode === mode ? 'text-sky-400 font-semibold' : ''}>
                {mode === 'HYBRID' ? 'Hybrid (RRF Fusion)' : mode === 'SEMANTIC' ? 'Semantic (pgvector)' : 'Lexical (tsvector)'}
              </span>
            </label>
          ))}
        </div>
      </form>

      {/* Results List */}
      {hasSearched && (
        <div className="space-y-3">
          <div className="flex items-center justify-between text-xs text-slate-400 border-b border-slate-800 pb-2">
            <span>Query Results ({results.length} matches)</span>
            <span className="font-mono">Ranking via Reciprocal Rank Fusion</span>
          </div>

          {results.length > 0 ? (
            <div className="space-y-3 max-h-[500px] overflow-y-auto pr-1">
              {results.map((res: SearchResult, idx: number) => (
                <div key={res.segment_id || idx} className="bg-slate-950/70 border border-slate-800/80 p-4 rounded-lg hover:border-slate-700 transition">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-xs bg-sky-500/10 text-sky-400 border border-sky-500/30 px-2 py-0.5 rounded font-mono font-semibold">
                        Rank #{idx + 1}
                      </span>
                      <span className="text-xs text-slate-300 flex items-center gap-1">
                        <User className="w-3 h-3 text-slate-500" />
                        {res.speaker_label}
                      </span>
                    </div>

                    <div className="flex items-center gap-3 text-xs font-mono text-slate-400">
                      <span>RRF Score: <b className="text-emerald-400">{res.rrf_score.toFixed(4)}</b></span>
                      <span className="flex items-center gap-1 text-[11px]">
                        <Clock className="w-3 h-3 text-slate-500" />
                        {res.start_time.toFixed(1)}s - {res.end_time.toFixed(1)}s
                      </span>
                    </div>
                  </div>

                  <p className="text-sm text-slate-200 leading-relaxed">{res.text}</p>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-slate-500 text-sm">
              No matching conversation turns found. Try adjusting the query or search mode.
            </div>
          )}
        </div>
      )}
    </div>
  );
};
