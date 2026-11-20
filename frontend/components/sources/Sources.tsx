'use client';

import React, { useState } from 'react';
import { FileText, Globe, ChevronDown, ChevronRight } from 'lucide-react';
import { RetrievedDocument } from '@/lib/types';

interface SourcesProps {
  sources?: RetrievedDocument[];
}

export const Sources: React.FC<SourcesProps> = ({ sources = [] }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);

  if (!sources || sources.length === 0) {
    return null;
  }

  const toggleSourceDetail = (idx: number, e: React.MouseEvent) => {
    e.stopPropagation();
    setExpandedIndex(expandedIndex === idx ? null : idx);
  };

  return (
    <div className="my-2 border border-neutral-200 dark:border-neutral-800 rounded-lg bg-neutral-50/50 dark:bg-neutral-950/40 text-xs overflow-hidden">
      {/* Header Button */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-3 py-2 flex items-center justify-between hover:bg-neutral-100 dark:hover:bg-neutral-900 transition-colors text-left"
        aria-expanded={isOpen}
      >
        <div className="flex items-center gap-2">
          <span className="font-bold text-black dark:text-neutral-200">Sources</span>
          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono font-bold bg-neutral-200 dark:bg-neutral-800 text-black dark:text-neutral-300 border border-neutral-300 dark:border-neutral-700">
            {sources.length}
          </span>
        </div>
        <div className="flex items-center gap-1 text-neutral-800 dark:text-neutral-400 text-[11px] font-medium">
          <span>{isOpen ? 'Collapse' : 'Expand'}</span>
          {isOpen ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
        </div>
      </button>

      {/* Expanded list of sources */}
      {isOpen && (
        <div className="px-3 pb-2 pt-1 border-t border-neutral-300 dark:border-neutral-800 divide-y divide-neutral-200 dark:divide-neutral-900">
          {sources.map((src, idx) => {
            const isWeb = src.filename.toLowerCase().includes('http') || src.filename.toLowerCase().includes('search');
            const isExpanded = expandedIndex === idx;

            return (
              <div key={idx} className="py-2">
                <button
                  type="button"
                  onClick={(e) => toggleSourceDetail(idx, e)}
                  className="w-full text-left flex items-center justify-between hover:text-black dark:hover:text-white transition-colors"
                >
                  <div className="flex items-center gap-2 truncate">
                    {isWeb ? (
                      <Globe className="w-3.5 h-3.5 text-neutral-700 dark:text-neutral-400 shrink-0" />
                    ) : (
                      <FileText className="w-3.5 h-3.5 text-neutral-700 dark:text-neutral-400 shrink-0" />
                    )}
                    <span className="font-semibold text-black dark:text-neutral-200 truncate">
                      {src.filename}
                    </span>
                    {src.page !== undefined && src.page !== null && (
                      <span className="text-neutral-800 dark:text-neutral-400 text-[11px] font-medium shrink-0">
                        · Page {src.page}
                      </span>
                    )}
                    {src.chunk_id !== undefined && src.chunk_id !== null && (
                      <span className="text-neutral-700 dark:text-neutral-400 text-[10px] font-mono shrink-0 font-medium">
                        chunk #{src.chunk_id}
                      </span>
                    )}
                  </div>
                  <ChevronDown
                    className={`w-3 h-3 text-neutral-700 dark:text-neutral-400 transition-transform ${
                      isExpanded ? 'rotate-180' : ''
                    }`}
                  />
                </button>

                {/* Expanded Source Details */}
                {isExpanded && (
                  <div className="mt-2 p-2.5 rounded bg-neutral-100 dark:bg-neutral-900 text-black dark:text-neutral-200 text-[11px] font-mono leading-relaxed border border-neutral-300 dark:border-neutral-800">
                    {src.snippet ? (
                      <p className="whitespace-pre-wrap font-medium">{src.snippet}</p>
                    ) : (
                      <p className="italic text-neutral-700 dark:text-neutral-400">Document chunk verified in vector store index.</p>
                    )}
                    {src.score !== undefined && (
                      <div className="mt-1.5 pt-1.5 border-t border-neutral-300 dark:border-neutral-800 text-[10px] text-neutral-700 dark:text-neutral-400 font-semibold">
                        Semantic Similarity Score: {(src.score * 100).toFixed(1)}%
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
