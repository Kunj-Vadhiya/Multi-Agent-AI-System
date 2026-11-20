'use client';

import React, { useState, useCallback, useRef, useEffect } from 'react';
import {
  SquarePen,
  Clock,
  Library,
  Search,
  PanelLeftClose,
  MoreVertical,
  Edit2,
  Trash2,
  Check,
  X,
  Settings as SettingsIcon,
  Bot,
} from 'lucide-react';
import { ThreadSummary } from '@/lib/types';

interface SidebarProps {
  threads: ThreadSummary[];
  activeThreadId?: string;
  onNewChat: () => void;
  onSelectThread: (threadId: string) => void;
  onRenameThread: (threadId: string, newTitle: string) => void;
  onDeleteThread: (threadId: string) => void;
  onOpenKnowledgeBase: () => void;
  onOpenSettings: () => void;
  isOpenMobile: boolean;
  onCloseMobile: () => void;
  isLoadingThreads?: boolean;
  documentCount?: number;
  isOpen: boolean;
  onToggle: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  threads,
  activeThreadId,
  onNewChat,
  onSelectThread,
  onRenameThread,
  onDeleteThread,
  onOpenKnowledgeBase,
  onOpenSettings,
  isOpenMobile,
  onCloseMobile,
  isLoadingThreads = false,
  documentCount = 0,
  isOpen,
  onToggle,
}) => {
  const [sidebarWidth, setSidebarWidth] = useState(260);
  const [isDragging, setIsDragging] = useState(false);
  const [showSearch, setShowSearch] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [editingThreadId, setEditingThreadId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [activeMenuId, setActiveMenuId] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  // Load width from localStorage
  useEffect(() => {
    try {
      const stored = localStorage.getItem('sidebar_width_pref');
      if (stored) {
        const parsed = parseInt(stored, 10);
        if (!isNaN(parsed) && parsed >= 200 && parsed <= 500) {
          setSidebarWidth(parsed);
        }
      }
    } catch {}
  }, []);

  // Drag resizer
  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      setIsDragging(true);

      const startX = e.clientX;
      const startWidth = sidebarWidth;

      const handleMouseMove = (moveEvent: MouseEvent) => {
        const delta = moveEvent.clientX - startX;
        const newWidth = Math.min(
          Math.max(200, startWidth + delta),
          Math.min(500, window.innerWidth * 0.45)
        );
        setSidebarWidth(Math.round(newWidth));
      };

      const handleMouseUp = () => {
        setIsDragging(false);
        window.removeEventListener('mousemove', handleMouseMove);
        window.removeEventListener('mouseup', handleMouseUp);
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
        try {
          localStorage.setItem('sidebar_width_pref', String(sidebarWidth));
        } catch {}
      };

      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    },
    [sidebarWidth]
  );

  const handleToggleSearch = () => {
    setShowSearch((prev) => {
      const next = !prev;
      if (next) {
        setTimeout(() => searchInputRef.current?.focus(), 100);
      } else {
        setSearchQuery('');
      }
      return next;
    });
  };

  const handleStartRename = (thread: ThreadSummary, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingThreadId(thread.thread_id);
    setEditTitle(thread.title);
    setActiveMenuId(null);
  };

  const handleSaveRename = (threadId: string, e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (editTitle.trim()) {
      onRenameThread(threadId, editTitle.trim());
    }
    setEditingThreadId(null);
  };

  const handleStartDelete = (threadId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setConfirmDeleteId(threadId);
    setActiveMenuId(null);
  };

  const handleConfirmDelete = (threadId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    onDeleteThread(threadId);
    setConfirmDeleteId(null);
  };

  const filteredThreads = searchQuery.trim()
    ? threads.filter((t) =>
        t.title.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : threads;

  // Primary Navigation Items (Clean & Focused)
  const navItems = [
    {
      icon: SquarePen,
      label: 'New chat',
      onClick: () => {
        onNewChat();
        if (isOpenMobile) onCloseMobile();
      },
    },
    {
      icon: Clock,
      label: 'Scheduled',
      onClick: () => {
        onNewChat();
      },
    },
    {
      icon: Library,
      label: 'Library',
      badge: documentCount > 0 ? documentCount : undefined,
      onClick: () => {
        onOpenKnowledgeBase();
        if (isOpenMobile) onCloseMobile();
      },
    },
  ];

  return (
    <>
      {/* Mobile Backdrop */}
      {isOpenMobile && (
        <div
          onClick={onCloseMobile}
          className="fixed inset-0 z-40 bg-black/60 dark:bg-black/70 backdrop-blur-sm lg:hidden transition-opacity"
        />
      )}

      {/* Adaptive Sidebar supporting Light & Dark Modes */}
      <aside
        style={{
          width: isOpen ? `${sidebarWidth}px` : 0,
        }}
        className={`fixed lg:static top-0 bottom-0 left-0 z-50 flex flex-col justify-between bg-[#F8F9FA] dark:bg-black text-neutral-900 dark:text-[#ECECEC] border-r border-neutral-200 dark:border-[#1F1F1F] shrink-0 select-none overflow-hidden ${
          isDragging ? 'select-none transition-none' : 'transition-[width,transform] duration-200 ease-out'
        } ${
          !isOpen
            ? 'hidden lg:flex w-0 border-r-0 pointer-events-none p-0'
            : ''
        } ${
          isOpenMobile ? 'translate-x-0 w-[280px] max-w-[85vw]' : 'max-lg:-translate-x-full'
        }`}
      >
        {/* Top Header & Navigation Container */}
        <div className="flex flex-col h-full min-w-[200px]">
          {/* Header: Multi-Agent AI Brand + Search + Collapse Button */}
          <div className="flex items-center justify-between px-3 pt-3.5 pb-2">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-[15px] tracking-tight text-neutral-900 dark:text-white">
                Multi-Agent AI
              </span>
            </div>

            <div className="flex items-center gap-0.5 text-neutral-500 dark:text-neutral-400">
              {/* Search Toggle Icon */}
              <button
                type="button"
                onClick={handleToggleSearch}
                className="p-1.5 rounded-lg hover:text-black dark:hover:text-white hover:bg-neutral-200/70 dark:hover:bg-[#212121] transition-colors"
                title="Search chats"
                aria-label="Search chats"
              >
                <Search className="w-4 h-4 stroke-[2]" />
              </button>

              {/* Sidebar Collapse Toggle Icon */}
              <button
                type="button"
                onClick={onToggle}
                className="p-1.5 rounded-lg hover:text-black dark:hover:text-white hover:bg-neutral-200/70 dark:hover:bg-[#212121] transition-colors"
                title="Close sidebar"
                aria-label="Close sidebar"
              >
                <PanelLeftClose className="w-4 h-4 stroke-[2]" />
              </button>
            </div>
          </div>

          {/* Search Input (conditionally revealed) */}
          {showSearch && (
            <div className="px-3 pb-2">
              <div className="relative">
                <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-neutral-400 dark:text-neutral-500" />
                <input
                  ref={searchInputRef}
                  type="text"
                  placeholder="Search conversations..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-8 pr-7 py-1.5 rounded-lg text-xs bg-white dark:bg-[#171717] text-neutral-900 dark:text-white placeholder-neutral-400 dark:placeholder-neutral-500 border border-neutral-300 dark:border-[#262626] focus:outline-none focus:border-neutral-500 transition-colors"
                />
                {searchQuery && (
                  <button
                    type="button"
                    onClick={() => setSearchQuery('')}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-neutral-400 hover:text-black dark:hover:text-white"
                  >
                    <X className="w-3 h-3" />
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Quick Navigation Items (New chat, Scheduled, Library) */}
          <div className="px-2 pt-1 pb-2 space-y-0.5">
            {navItems.map((item, idx) => {
              const Icon = item.icon;
              return (
                <button
                  key={idx}
                  type="button"
                  onClick={item.onClick}
                  className="w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-sm text-neutral-700 dark:text-[#ECECEC] hover:bg-neutral-200/60 dark:hover:bg-[#212121] transition-colors group text-left"
                >
                  <div className="flex items-center gap-3">
                    <Icon className="w-4 h-4 text-neutral-500 dark:text-neutral-400 group-hover:text-neutral-900 dark:group-hover:text-white stroke-[1.75]" />
                    <span className="font-normal text-[13.5px]">{item.label}</span>
                  </div>
                  {item.badge !== undefined && (
                    <span className="px-1.5 py-0.2 rounded text-[10px] font-mono bg-neutral-200 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-400">
                      {item.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </div>

          {/* Section: Recents */}
          <div className="flex-1 flex flex-col min-h-0 px-2 pt-2 border-t border-neutral-200/80 dark:border-neutral-900">
            <p className="text-[11px] font-semibold uppercase text-neutral-500 dark:text-neutral-400 px-2 pb-1.5 tracking-wider">
              Recents
            </p>

            <div className="flex-1 overflow-y-auto space-y-0.5 pr-1 scrollbar-thin scrollbar-thumb-neutral-300 dark:scrollbar-thumb-neutral-800">
              {isLoadingThreads && threads.length === 0 ? (
                <div className="p-3 text-xs text-neutral-400">Loading chats...</div>
              ) : filteredThreads.length === 0 ? (
                <div className="px-2 py-3 text-xs text-neutral-400">
                  {searchQuery ? 'No matching chats' : 'No recent chats'}
                </div>
              ) : (
                filteredThreads.map((thread) => {
                  const isActive = thread.thread_id === activeThreadId;
                  const isEditing = editingThreadId === thread.thread_id;
                  const isConfirming = confirmDeleteId === thread.thread_id;
                  const isMenuOpen = activeMenuId === thread.thread_id;

                  if (isEditing) {
                    return (
                      <form
                        key={thread.thread_id}
                        onSubmit={(e) => handleSaveRename(thread.thread_id, e)}
                        className="flex items-center gap-1 px-2 py-1 bg-white dark:bg-[#1F1F1F] border border-neutral-300 dark:border-transparent rounded-lg"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <input
                          type="text"
                          value={editTitle}
                          onChange={(e) => setEditTitle(e.target.value)}
                          className="flex-1 min-w-0 bg-transparent text-xs text-neutral-900 dark:text-white focus:outline-none"
                          autoFocus
                        />
                        <button
                          type="submit"
                          className="p-1 text-green-600 dark:text-green-400 hover:opacity-80"
                        >
                          <Check className="w-3.5 h-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => setEditingThreadId(null)}
                          className="p-1 text-neutral-400 hover:text-black dark:hover:text-white"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </form>
                    );
                  }

                  if (isConfirming) {
                    return (
                      <div
                        key={thread.thread_id}
                        className="flex items-center justify-between px-2.5 py-1.5 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900/60 rounded-lg text-xs"
                      >
                        <span className="text-red-700 dark:text-red-300 text-[11px] truncate">Delete?</span>
                        <div className="flex items-center gap-1">
                          <button
                            type="button"
                            onClick={(e) => handleConfirmDelete(thread.thread_id, e)}
                            className="px-1.5 py-0.5 rounded bg-red-600 text-white text-[10px] font-semibold hover:bg-red-500"
                          >
                            Yes
                          </button>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              setConfirmDeleteId(null);
                            }}
                            className="px-1.5 py-0.5 rounded bg-neutral-200 dark:bg-neutral-800 text-neutral-700 dark:text-neutral-300 text-[10px] hover:bg-neutral-300 dark:hover:bg-neutral-700"
                          >
                            No
                          </button>
                        </div>
                      </div>
                    );
                  }

                  return (
                    <div
                      key={thread.thread_id}
                      onClick={() => {
                        onSelectThread(thread.thread_id);
                        if (isOpenMobile) onCloseMobile();
                      }}
                      className={`group relative flex items-center justify-between px-2.5 py-2 rounded-lg text-[13.5px] cursor-pointer transition-colors ${
                        isActive
                          ? 'bg-neutral-200/80 dark:bg-[#212121] text-neutral-900 dark:text-white font-medium'
                          : 'text-neutral-700 dark:text-[#ECECEC] hover:bg-neutral-200/50 dark:hover:bg-[#1A1A1A] hover:text-black dark:hover:text-white'
                      }`}
                    >
                      <span className="truncate flex-1 min-w-0">
                        {thread.title || 'Untitled conversation'}
                      </span>

                      {/* Thread action button (3 dots) */}
                      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            setActiveMenuId(isMenuOpen ? null : thread.thread_id);
                          }}
                          className="p-1 rounded text-neutral-500 dark:text-neutral-400 hover:text-black dark:hover:text-white hover:bg-neutral-300 dark:hover:bg-[#2B2B2B]"
                          title="Chat options"
                        >
                          <MoreVertical className="w-3.5 h-3.5" />
                        </button>
                      </div>

                      {/* Dropdown Menu for Rename/Delete */}
                      {isMenuOpen && (
                        <div
                          className="absolute right-2 top-8 z-30 w-32 py-1 rounded-lg bg-white dark:bg-[#212121] border border-neutral-200 dark:border-[#2E2E2E] shadow-xl text-xs space-y-0.5 text-neutral-700 dark:text-neutral-300"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <button
                            type="button"
                            onClick={(e) => handleStartRename(thread, e)}
                            className="w-full flex items-center gap-2 px-2.5 py-1.5 hover:bg-neutral-100 dark:hover:bg-[#2B2B2B] hover:text-black dark:hover:text-white text-left"
                          >
                            <Edit2 className="w-3 h-3 text-neutral-500 dark:text-neutral-400" />
                            <span>Rename</span>
                          </button>
                          <button
                            type="button"
                            onClick={(e) => handleStartDelete(thread.thread_id, e)}
                            className="w-full flex items-center gap-2 px-2.5 py-1.5 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-[#2B2B2B] text-left"
                          >
                            <Trash2 className="w-3 h-3 text-red-500 dark:text-red-400" />
                            <span>Delete</span>
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* Clean Bottom Navigation: Settings */}
          <div className="p-2 border-t border-neutral-200 dark:border-[#1F1F1F]">
            <button
              type="button"
              onClick={() => {
                onOpenSettings();
                if (isOpenMobile) onCloseMobile();
              }}
              className="w-full flex items-center gap-3 px-2.5 py-2 rounded-lg text-sm text-neutral-700 dark:text-[#ECECEC] hover:bg-neutral-200/60 dark:hover:bg-[#212121] transition-colors group"
            >
              <SettingsIcon className="w-4 h-4 text-neutral-500 dark:text-neutral-400 group-hover:text-neutral-900 dark:group-hover:text-white stroke-[1.75]" />
              <span className="font-normal text-[13.5px]">Settings</span>
            </button>
          </div>
        </div>

        {/* Resizer Handle on the Right Edge of Sidebar */}
        {isOpen && (
          <div
            onMouseDown={handleMouseDown}
            onDoubleClick={() => setSidebarWidth(260)}
            className={`hidden lg:block absolute top-0 right-0 w-2 h-full cursor-col-resize z-50 transition-colors group select-none ${
              isDragging
                ? 'bg-blue-500/30'
                : 'hover:bg-neutral-300 dark:hover:bg-neutral-800'
            }`}
            title="Drag to resize sidebar (Double-click to reset)"
          >
            <div
              className={`w-[2px] h-full mx-auto transition-colors ${
                isDragging
                  ? 'bg-blue-500'
                  : 'bg-transparent group-hover:bg-neutral-400 dark:group-hover:bg-neutral-700'
              }`}
            />
          </div>
        )}
      </aside>
    </>
  );
};
