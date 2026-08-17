// SourcesAccordion — expandable list of RAG source documents.
// Showing sources is a critical trust signal in banking contexts.
// Score is the cosine similarity returned by the retrieval system.
'use client';
import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { FileText, ChevronDown } from 'lucide-react';
import { ConfidenceMeter } from '@/components/shared/ConfidenceMeter';

interface Source {
  text: string;
  source?: string;
  score?: number;
}

interface SourcesAccordionProps {
  sources: Source[];
}

export function SourcesAccordion({ sources }: SourcesAccordionProps) {
  const [isOpen, setIsOpen] = useState(false);
  if (!sources.length) return null;

  return (
    <div className="mt-3 rounded-lg border border-white/8 bg-white/2 overflow-hidden">
      <button
        onClick={() => setIsOpen(v => !v)}
        className="w-full flex items-center justify-between px-3 py-2 text-xs text-white/40 hover:text-white/60 transition-colors"
      >
        <div className="flex items-center gap-2">
          <FileText className="w-3 h-3" />
          <span>Sources ({sources.length})</span>
        </div>
        <motion.div animate={{ rotate: isOpen ? 180 : 0 }} transition={{ duration: 0.2 }}>
          <ChevronDown className="w-3 h-3" />
        </motion.div>
      </button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ height: 0 }}
            animate={{ height: 'auto' }}
            exit={{ height: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="px-3 pb-3 space-y-3 border-t border-white/5">
              {sources.map((src, i) => (
                <div key={i} className="pt-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[10px] font-medium text-white/50 truncate">
                      {src.source ?? `Source ${i + 1}`}
                    </span>
                    {src.score !== undefined && (
                      <div className="flex items-center gap-2 ml-3 flex-shrink-0 w-24">
                        <ConfidenceMeter score={src.score} />
                      </div>
                    )}
                  </div>
                  <p className="text-xs text-white/30 leading-relaxed line-clamp-3">{src.text}</p>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
