// Knowledge Search — dedicated RAG search interface.
// Surfaces confidence scores and source documents for every result.
// Shows the RAG system's transparency — a major talking point.
'use client';
import { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, BookOpen, Clock, ChevronDown, ChevronUp, Loader2, Sparkles } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { knowledgeApi } from '@/lib/api';
import { queryKeys } from '@/lib/query';
import { ConfidenceMeter } from '@/components/shared/ConfidenceMeter';
import { cn } from '@/lib/utils';

const CATEGORIES = ['All', 'Account', 'Cards', 'UPI', 'Loans', 'Fraud', 'Security', 'Limits'];
const RECENT = ['What is UPI Lite?', 'How to lock my card?', 'Minimum balance requirement'];

export default function KnowledgePage() {
  const [query, setQuery] = useState('');
  const [activeQuery, setActiveQuery] = useState('');
  const [category, setCategory] = useState('All');
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: queryKeys.faqSearch(activeQuery, 6),
    queryFn: () => knowledgeApi.search({ query: activeQuery, k: 6 }),
    enabled: activeQuery.length >= 2,
  });

  const handleSearch = useCallback(() => {
    if (query.trim().length >= 2) setActiveQuery(query.trim());
  }, [query]);

  return (
    <div className="p-4 lg:p-6 max-w-4xl mx-auto space-y-6">
      <div className="flex items-center gap-2">
        <BookOpen className="w-5 h-5 text-green-400" />
        <h2 className="text-xl font-semibold text-white">Knowledge Base</h2>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
        <input
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSearch()}
          placeholder="Search banking policies, FAQ, and guidelines..."
          className="w-full pl-11 pr-24 py-3.5 rounded-2xl bg-white/4 border border-white/8 text-white placeholder:text-white/25 focus:outline-none focus:border-violet-500/40 transition-colors text-sm"
        />
        <button
          onClick={handleSearch}
          disabled={query.length < 2}
          className="absolute right-3 top-1/2 -translate-y-1/2 px-3 py-1.5 rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-xs font-medium disabled:opacity-40 transition-colors"
        >
          Search
        </button>
      </div>

      {/* Categories */}
      <div className="flex gap-2 flex-wrap">
        {CATEGORIES.map(cat => (
          <button
            key={cat}
            onClick={() => setCategory(cat)}
            className={cn(
              'px-3 py-1.5 rounded-lg text-xs font-medium transition-all',
              category === cat
                ? 'bg-violet-600 text-white'
                : 'bg-white/4 text-white/40 hover:text-white/70 hover:bg-white/8 border border-white/6',
            )}
          >
            {cat}
          </button>
        ))}
      </div>

      {/* Recent Searches */}
      {!activeQuery && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <Clock className="w-3.5 h-3.5 text-white/25" />
            <span className="text-xs text-white/30 uppercase tracking-widest">Recent</span>
          </div>
          <div className="space-y-1.5">
            {RECENT.map(r => (
              <button
                key={r}
                onClick={() => { setQuery(r); setActiveQuery(r); }}
                className="flex items-center gap-2 text-sm text-white/40 hover:text-white/70 transition-colors"
              >
                <Search className="w-3 h-3" /> {r}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Results */}
      {isLoading && (
        <div className="flex items-center gap-3 text-sm text-white/40">
          <Loader2 className="w-4 h-4 animate-spin text-violet-400" />
          Searching knowledge base...
        </div>
      )}

      <AnimatePresence mode="wait">
        {data && (
          <motion.div
            key={activeQuery}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-3"
          >
            <div className="flex items-center gap-2 text-xs text-white/30">
              <Sparkles className="w-3 h-3 text-violet-400" />
              {data.results.length} results for &ldquo;{activeQuery}&rdquo;
            </div>

            {data.results.map((result, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
                className="rounded-2xl border border-white/5 bg-white/[0.02] overflow-hidden"
              >
                <div className="p-4">
                  <div className="flex items-start justify-between gap-3 mb-2">
                    <div className="flex items-center gap-2">
                      <BookOpen className="w-3.5 h-3.5 text-green-400 flex-shrink-0" />
                      <span className="text-xs font-medium text-white/60 truncate">
                        {result.source ?? `Result ${i + 1}`}
                      </span>
                    </div>
                    {result.score !== undefined && (
                      <div className="flex items-center gap-2 flex-shrink-0 w-28">
                        <span className="text-[10px] text-white/30">Confidence</span>
                        <ConfidenceMeter score={result.score} />
                      </div>
                    )}
                  </div>

                  <p className={cn(
                    'text-sm text-white/70 leading-relaxed',
                    expandedIndex !== i && 'line-clamp-3',
                  )}>
                    {result.text}
                  </p>

                  <button
                    onClick={() => setExpandedIndex(expandedIndex === i ? null : i)}
                    className="flex items-center gap-1 text-xs text-white/30 hover:text-white/60 transition-colors mt-2"
                  >
                    {expandedIndex === i
                      ? <><ChevronUp className="w-3 h-3" /> Collapse</>
                      : <><ChevronDown className="w-3 h-3" /> Expand context</>
                    }
                  </button>
                </div>
              </motion.div>
            ))}

            {data.results.length === 0 && (
              <div className="py-12 text-center text-sm text-white/25">
                No results found for &ldquo;{activeQuery}&rdquo;
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
