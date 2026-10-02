import React, { useState } from 'react';
import { Search, SlidersHorizontal, Clock, ExternalLink, Sparkles } from 'lucide-react';
import { runHybridSearch, SearchResult } from '../api/client';

export interface SearchExplorerProps {
  onSelectSession?: (sessionId: string) => void;
}

export const SearchExplorer: React.FC<SearchExplorerProps> = ({ onSelectSession }) => {
  const [query, setQuery] = useState('');
  const [searchMode, setSearchMode] = useState<'HYBRID' | 'SEMANTIC' | 'LEXICAL'>('HYBRID');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    try {
      setIsSearching(true);
      setHasSearched(true);
      setSearchError(null);
      const res = await runHybridSearch(query.trim(), searchMode);
      setResults(res);
    } catch (err: unknown) {
      setResults([]);
      setSearchError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <div className="glass-card rounded-3xl p-6 md:p-8 relative overflow-hidden">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-lg md:text-xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <Search className="w-5 h-5 text-sky-500 dark:text-sky-400" />
            AI Semantic & Hybrid Search
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Instant search across all your recorded meetings, action items, and spoken thoughts
          </p>
        </div>
      </div>

      <form onSubmit={handleSearch} className="space-y-4 mb-8">
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-400 absolute left-4 top-3.5" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. 'budget forecast for Q3', 'client presentation discussion'..."
              className="w-full bg-slate-50 dark:bg-white/[0.04] border border-slate-300 dark:border-white/[0.1] rounded-2xl pl-11 pr-4 py-3 text-xs md:text-sm text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:border-sky-500 transition"
            />
          </div>
          <button
            type="submit"
            disabled={isSearching || !query.trim()}
            className="px-5 py-3 bg-gradient-to-tr from-sky-500 to-indigo-600 hover:from-sky-400 hover:to-indigo-500 disabled:opacity-40 text-white font-semibold rounded-2xl text-xs md:text-sm transition shadow-md shadow-sky-500/20 cursor-pointer flex items-center gap-2 shrink-0"
          >
            {isSearching ? <Sparkles className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
            <span>Search</span>
          </button>
        </div>

        {/* Mode filter pills */}
        <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
          <SlidersHorizontal className="w-3.5 h-3.5 text-slate-400" />
          <span>Mode:</span>
          <div className="flex items-center gap-1.5">
            {(['HYBRID', 'SEMANTIC', 'LEXICAL'] as const).map((mode) => (
              <button
                key={mode}
                type="button"
                onClick={() => setSearchMode(mode)}
                className={`px-3 py-1 rounded-full text-xs transition cursor-pointer ${
                  searchMode === mode
                    ? 'bg-sky-50 dark:bg-sky-500/20 text-sky-700 dark:text-sky-300 border border-sky-300 dark:border-sky-500/40 font-medium'
                    : 'glass-pill text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
                }`}
              >
                {mode === 'HYBRID' ? '✦ Hybrid (Semantic + Keyword)' : mode === 'SEMANTIC' ? 'Semantic' : 'Keyword'}
              </button>
            ))}
          </div>
        </div>
      </form>

      {/* Results */}
      {searchError && (
        <div className="p-4 rounded-2xl bg-rose-50 dark:bg-rose-500/10 border border-rose-200 dark:border-rose-500/20 text-rose-700 dark:text-rose-300 text-xs mb-4">
          Search Error: {searchError}
        </div>
      )}

      {hasSearched && results.length === 0 && !isSearching && !searchError && (
        <div className="p-8 text-center glass-card rounded-2xl text-slate-500 dark:text-slate-400 text-sm">
          No matches found for "{query}". Try different keywords or broader concepts.
        </div>
      )}

      <div className="space-y-3">
        {results.map((res, idx) => (
          <div
            key={res.segment_id || idx}
            className="p-5 rounded-2xl bg-white dark:bg-white/[0.03] border border-slate-200 dark:border-white/[0.08] hover:border-slate-300 dark:hover:border-white/[0.16] transition shadow-sm"
          >
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className="text-xs px-2.5 py-0.5 rounded-full font-semibold bg-sky-50 dark:bg-sky-500/15 text-sky-700 dark:text-sky-300 border border-sky-200 dark:border-sky-500/30">
                  {res.speaker_label}
                </span>
                <span className="text-[11px] text-slate-400 dark:text-slate-500 font-mono">
                  Relevance: {(res.rrf_score * 100).toFixed(1)}%
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="flex items-center gap-1 text-[11px] text-slate-500 dark:text-slate-400 font-mono">
                  <Clock className="w-3 h-3 text-slate-400" />
                  {res.start_time.toFixed(1)}s - {res.end_time.toFixed(1)}s
                </span>
                {onSelectSession && (
                  <button
                    onClick={() => onSelectSession(res.session_id)}
                    className="text-xs text-sky-600 dark:text-sky-400 hover:text-sky-700 dark:hover:text-sky-300 flex items-center gap-1 cursor-pointer"
                  >
                    View <ExternalLink className="w-3 h-3" />
                  </button>
                )}
              </div>
            </div>
            <p className="text-xs md:text-sm text-slate-800 dark:text-slate-200 leading-relaxed">{res.text}</p>
          </div>
        ))}
      </div>
    </div>
  );
};
