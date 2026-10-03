import React, { useState } from 'react';
import { Search, SlidersHorizontal, Clock, ExternalLink, Sparkles, Zap, AlignLeft } from 'lucide-react';
import { runHybridSearch, SearchResult } from '../api/client';

export interface SearchExplorerProps {
  onSelectSession?: (sessionId: string) => void;
}

const SEARCH_EXAMPLES = [
  'Budget forecast for Q3',
  'Client presentation feedback',
  'Action items for next sprint',
  'Team leads decision',
];

export const SearchExplorer: React.FC<SearchExplorerProps> = ({ onSelectSession }) => {
  const [query, setQuery] = useState('');
  const [searchMode, setSearchMode] = useState<'HYBRID' | 'SEMANTIC' | 'LEXICAL'>('HYBRID');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  const handleSearch = async (e: React.FormEvent | null, overrideQuery?: string) => {
    if (e) e.preventDefault();
    const q = (overrideQuery ?? query).trim();
    if (!q) return;

    try {
      setIsSearching(true);
      setHasSearched(true);
      setSearchError(null);
      if (overrideQuery) setQuery(overrideQuery);
      const res = await runHybridSearch(q, searchMode);
      setResults(res);
    } catch (err: unknown) {
      setResults([]);
      setSearchError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsSearching(false);
    }
  };

  const modeConfig = {
    HYBRID: { label: '✦ Hybrid', sublabel: 'Semantic + Keyword', color: 'sky' },
    SEMANTIC: { label: '⊕ Semantic', sublabel: 'Meaning-based', color: 'indigo' },
    LEXICAL: { label: '⌗ Keyword', sublabel: 'Exact match', color: 'emerald' },
  };

  return (
    <div className="space-y-5">
      {/* Search Panel */}
      <div className="glass-card rounded-3xl p-6 md:p-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-base md:text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <Search className="w-5 h-5 text-emerald-500 dark:text-emerald-400" />
              AI Semantic Search
            </h3>
            <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
              Search across all your conversations, decisions, and action items
            </p>
          </div>
          {results.length > 0 && (
            <span className="text-xs font-mono bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-500/25 px-3 py-1.5 rounded-xl">
              {results.length} results
            </span>
          )}
        </div>

        {/* Search Form */}
        <form onSubmit={handleSearch} className="space-y-4">
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search className="w-4 h-4 text-slate-400 absolute left-4 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search your meeting memories..."
                className="w-full bg-slate-50 dark:bg-white/[0.04] border border-slate-200 dark:border-white/[0.09] rounded-2xl pl-11 pr-4 py-3 text-sm text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:border-emerald-400 dark:focus:border-emerald-500 focus:ring-1 focus:ring-emerald-400/30 dark:focus:ring-emerald-500/30 transition"
              />
            </div>
            <button
              type="submit"
              disabled={isSearching || !query.trim()}
              className="px-5 py-3 bg-gradient-to-tr from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 disabled:opacity-40 text-white font-semibold rounded-2xl text-sm transition shadow-md shadow-emerald-500/20 cursor-pointer flex items-center gap-2 shrink-0"
            >
              {isSearching
                ? <Sparkles className="w-4 h-4 animate-spin" />
                : <Search className="w-4 h-4" />
              }
              <span className="hidden sm:inline">Search</span>
            </button>
          </div>

          {/* Mode Selector */}
          <div className="flex items-center gap-3 flex-wrap">
            <div className="flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400">
              <SlidersHorizontal className="w-3.5 h-3.5" />
              <span>Mode:</span>
            </div>
            <div className="flex items-center gap-1.5">
              {(['HYBRID', 'SEMANTIC', 'LEXICAL'] as const).map((mode) => (
                <button
                  key={mode}
                  type="button"
                  onClick={() => setSearchMode(mode)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium border transition cursor-pointer ${
                    searchMode === mode
                      ? 'bg-emerald-50 dark:bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border-emerald-300 dark:border-emerald-500/40'
                      : 'glass-pill text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
                  }`}
                >
                  {modeConfig[mode].label}
                </button>
              ))}
            </div>
          </div>

          {/* Example queries */}
          {!hasSearched && (
            <div className="flex items-center gap-2 flex-wrap pt-1">
              <span className="text-[10px] text-slate-400 dark:text-slate-500 uppercase font-semibold tracking-wider">Try:</span>
              {SEARCH_EXAMPLES.map((ex, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => handleSearch(null, ex)}
                  className="text-[11px] text-slate-600 dark:text-slate-400 hover:text-emerald-600 dark:hover:text-emerald-400 glass-pill px-3 py-1 rounded-full transition cursor-pointer"
                >
                  {ex}
                </button>
              ))}
            </div>
          )}
        </form>
      </div>

      {/* Error */}
      {searchError && (
        <div className="p-4 rounded-2xl bg-rose-50 dark:bg-rose-500/10 border border-rose-200 dark:border-rose-500/20 text-rose-700 dark:text-rose-300 text-xs">
          Search error: {searchError}
        </div>
      )}

      {/* Empty state */}
      {hasSearched && results.length === 0 && !isSearching && !searchError && (
        <div className="glass-card rounded-3xl p-12 text-center animate-fade-in">
          <div className="w-12 h-12 rounded-2xl bg-slate-100 dark:bg-white/[0.05] border border-slate-200 dark:border-white/[0.07] flex items-center justify-center mx-auto mb-3">
            <AlignLeft className="w-6 h-6 text-slate-400" />
          </div>
          <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">No matches found</p>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Try different keywords or switch to Semantic mode for conceptual search
          </p>
        </div>
      )}

      {/* Results */}
      {results.length > 0 && (
        <div className="space-y-3 animate-fade-in-up">
          {results.map((res, idx) => (
            <div
              key={res.segment_id || idx}
              className="glass-card glass-card-hover rounded-2xl p-5 border border-slate-200 dark:border-white/[0.07] animate-fade-in-up"
              style={{ animationDelay: `${idx * 0.04}s` }}
            >
              <div className="flex items-center justify-between mb-3 gap-3">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-xs px-2.5 py-1 rounded-lg font-semibold bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-500/25">
                    {res.speaker_label}
                  </span>
                  <span className="flex items-center gap-1 text-[11px] text-slate-500 dark:text-slate-400 font-mono bg-slate-100 dark:bg-white/[0.04] px-2 py-0.5 rounded-lg border border-slate-200 dark:border-white/[0.06]">
                    <Zap className="w-3 h-3 text-amber-400" />
                    {(res.rrf_score * 100).toFixed(1)}% relevance
                  </span>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <span className="flex items-center gap-1 text-[10px] text-slate-400 dark:text-slate-500 font-mono">
                    <Clock className="w-3 h-3" />
                    {res.start_time.toFixed(1)}s – {res.end_time.toFixed(1)}s
                  </span>
                  {onSelectSession && (
                    <button
                      onClick={() => onSelectSession(res.session_id)}
                      className="text-xs text-emerald-600 dark:text-emerald-400 hover:text-emerald-700 dark:hover:text-emerald-300 flex items-center gap-1 cursor-pointer font-medium"
                    >
                      Open <ExternalLink className="w-3 h-3" />
                    </button>
                  )}
                </div>
              </div>
              <p className="text-xs md:text-sm text-slate-800 dark:text-slate-200 leading-relaxed">{res.text}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
