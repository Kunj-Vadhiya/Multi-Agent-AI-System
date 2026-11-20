'use client';

import React, { useState } from 'react';
import { MessageSquare, MoreVertical, Edit2, Trash2, Check, X } from 'lucide-react';
import { ThreadSummary } from '@/lib/types';

interface ConversationListProps {
  threads: ThreadSummary[];
  activeThreadId?: string;
  onSelectThread: (threadId: string) => void;
  onRenameThread: (threadId: string, newTitle: string) => void;
  onDeleteThread: (threadId: string) => void;
  isLoading?: boolean;
}

export const ConversationList: React.FC<ConversationListProps> = ({
  threads,
  activeThreadId,
  onSelectThread,
  onRenameThread,
  onDeleteThread,
  isLoading = false,
}) => {
  const [editingThreadId, setEditingThreadId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [menuOpenThreadId, setMenuOpenThreadId] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  const startRename = (thread: ThreadSummary, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingThreadId(thread.thread_id);
    setEditTitle(thread.title);
    setMenuOpenThreadId(null);
  };

  const saveRename = (threadId: string, e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (editTitle.trim()) {
      onRenameThread(threadId, editTitle.trim());
    }
    setEditingThreadId(null);
  };

  const cancelRename = (e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    setEditingThreadId(null);
  };

  const startDelete = (threadId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setConfirmDeleteId(threadId);
    setMenuOpenThreadId(null);
  };

  const confirmDelete = (threadId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    onDeleteThread(threadId);
    setConfirmDeleteId(null);
  };

  const cancelDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    setConfirmDeleteId(null);
  };

  if (isLoading && threads.length === 0) {
    return (
      <div className="space-y-1.5 p-2">
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="h-8 rounded-md bg-neutral-200/50 dark:bg-neutral-800/40 animate-pulse"
          />
        ))}
      </div>
    );
  }

  if (threads.length === 0) {
    return (
      <div className="p-4 text-center text-xs text-neutral-400 dark:text-neutral-600">
        No conversations yet.
      </div>
    );
  }

  return (
    <div className="space-y-0.5 overflow-y-auto pr-1">
      {threads.map((t) => {
        const isActive = t.thread_id === activeThreadId;
        const isEditing = t.thread_id === editingThreadId;
        const isConfirming = t.thread_id === confirmDeleteId;
        const isMenuOpen = t.thread_id === menuOpenThreadId;

        if (isEditing) {
          return (
            <form
              key={t.thread_id}
              onSubmit={(e) => saveRename(t.thread_id, e)}
              className="flex items-center gap-1 px-2 py-1.5 rounded-md bg-white dark:bg-[#141414] border border-neutral-300 dark:border-neutral-700"
            >
              <input
                type="text"
                autoFocus
                value={editTitle}
                onChange={(e) => setEditTitle(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Escape') cancelRename();
                }}
                className="w-full bg-transparent text-xs text-neutral-900 dark:text-neutral-100 focus:outline-none"
              />
              <button
                type="submit"
                className="p-1 hover:text-black dark:hover:text-white text-neutral-600"
                title="Save"
              >
                <Check className="w-3.5 h-3.5" />
              </button>
              <button
                type="button"
                onClick={cancelRename}
                className="p-1 hover:text-black dark:hover:text-white text-neutral-600"
                title="Cancel"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </form>
          );
        }

        if (isConfirming) {
          return (
            <div
              key={t.thread_id}
              className="flex items-center justify-between px-2.5 py-1.5 rounded-md bg-neutral-100 dark:bg-[#1a1a1a] text-xs text-neutral-800 dark:text-neutral-200 border border-neutral-300 dark:border-neutral-800"
            >
              <span className="text-[11px] truncate">Delete chat?</span>
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={(e) => confirmDelete(t.thread_id, e)}
                  className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-red-600 text-white hover:bg-red-700"
                >
                  Yes
                </button>
                <button
                  type="button"
                  onClick={cancelDelete}
                  className="px-1.5 py-0.5 rounded text-[10px] text-neutral-500 hover:text-black dark:hover:text-white"
                >
                  Cancel
                </button>
              </div>
            </div>
          );
        }

        return (
          <div
            key={t.thread_id}
            onClick={() => onSelectThread(t.thread_id)}
            className={`group relative flex items-center justify-between px-2.5 py-2 rounded-lg cursor-pointer text-xs transition-colors ${
              isActive
                ? 'bg-neutral-200/90 dark:bg-[#181818] text-black dark:text-white font-semibold'
                : 'text-neutral-900 dark:text-neutral-300 hover:bg-neutral-200/60 dark:hover:bg-[#121212] hover:text-black dark:hover:text-white'
            }`}
          >
            <div className="flex items-center gap-2 truncate pr-2">
              <MessageSquare className="w-3.5 h-3.5 shrink-0 text-neutral-700 dark:text-neutral-400" />
              <span className="truncate font-medium">{t.title}</span>
            </div>

            {/* Actions Trigger */}
            <div className="relative shrink-0">
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setMenuOpenThreadId(isMenuOpen ? null : t.thread_id);
                }}
                className={`p-1 rounded text-neutral-600 dark:text-neutral-400 hover:text-black dark:hover:text-white hover:bg-neutral-300/50 dark:hover:bg-neutral-800 transition-opacity ${
                  isMenuOpen || isActive ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'
                }`}
                title="Conversation Options"
              >
                <MoreVertical className="w-3.5 h-3.5" />
              </button>

              {/* Popover Menu */}
              {isMenuOpen && (
                <div
                  onClick={(e) => e.stopPropagation()}
                  className="absolute right-0 top-6 z-30 w-28 py-1 rounded-md bg-white dark:bg-[#141414] border border-neutral-200 dark:border-neutral-800 shadow-lg text-xs"
                >
                  <button
                    type="button"
                    onClick={(e) => startRename(t, e)}
                    className="w-full flex items-center gap-2 px-2.5 py-1.5 text-left text-neutral-700 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-[#202020] transition-colors"
                  >
                    <Edit2 className="w-3 h-3 text-neutral-500" />
                    <span>Rename</span>
                  </button>
                  <button
                    type="button"
                    onClick={(e) => startDelete(t.thread_id, e)}
                    className="w-full flex items-center gap-2 px-2.5 py-1.5 text-left text-red-600 hover:bg-neutral-100 dark:hover:bg-[#202020] transition-colors"
                  >
                    <Trash2 className="w-3 h-3 text-red-500" />
                    <span>Delete</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
};
