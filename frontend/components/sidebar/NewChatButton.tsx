'use client';

import React from 'react';
import { Plus } from 'lucide-react';

interface NewChatButtonProps {
  onClick: () => void;
  className?: string;
}

export const NewChatButton: React.FC<NewChatButtonProps> = ({ onClick, className = '' }) => {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full flex items-center justify-between px-3 py-2 rounded-lg border border-neutral-300 dark:border-neutral-800 bg-white dark:bg-[#111111] hover:border-neutral-400 dark:hover:border-neutral-700 text-neutral-900 dark:text-neutral-100 font-medium text-xs shadow-sm transition-all ${className}`}
    >
      <span className="flex items-center gap-2">
        <Plus className="w-4 h-4 text-neutral-700 dark:text-neutral-300" />
        <span>New Chat</span>
      </span>
      <kbd className="hidden sm:inline-block px-1.5 py-0.5 text-[10px] font-mono text-neutral-400 dark:text-neutral-500 bg-neutral-100 dark:bg-[#1a1a1a] rounded border border-neutral-200 dark:border-neutral-800">
        Ctrl+N
      </kbd>
    </button>
  );
};
