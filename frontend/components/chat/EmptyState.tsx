'use client';

import React from 'react';
import {
  Search,
  BarChart3,
  Code2,
  FileText,
  Database,
  Mail,
  Calendar,
  Bot,
} from 'lucide-react';

interface EmptyStateProps {
  onSelectPrompt: (prompt: string) => void;
}

export const EmptyState: React.FC<EmptyStateProps> = ({ onSelectPrompt }) => {
  const examplePrompts = [
    {
      title: 'Research RAG',
      prompt: 'Research the latest developments in RAG and compare different approaches.',
    },
    {
      title: 'Database Query',
      prompt: 'Inspect the database schema and summarize the data structure.',
    },
    {
      title: 'Coding Assistance',
      prompt: 'Create a FastAPI API endpoint for a PostgreSQL database with health checks.',
    },
    {
      title: 'Meeting Schedule',
      prompt: 'Summarize my upcoming meetings and team schedules for today.',
    },
  ];

  const capabilities = [
    { icon: Search, label: 'Research a topic' },
    { icon: BarChart3, label: 'Analyze information' },
    { icon: Code2, label: 'Write code' },
    { icon: FileText, label: 'Work with documents' },
    { icon: Database, label: 'Query databases' },
    { icon: Mail, label: 'Manage email' },
    { icon: Calendar, label: 'Manage calendar' },
  ];

  return (
    <div className="flex-1 flex flex-col items-center justify-center p-6 text-center max-w-2xl mx-auto my-auto select-none">
      {/* System Logo Symbol */}
      <div className="w-12 h-12 rounded-2xl border border-neutral-300 dark:border-neutral-700 flex items-center justify-center mb-4 bg-neutral-100 dark:bg-[#111111] shadow-sm">
        <Bot className="w-6 h-6 text-neutral-800 dark:text-neutral-200" />
      </div>

      <h1 className="text-xl sm:text-2xl font-semibold tracking-tight text-neutral-900 dark:text-neutral-100 mb-1">
        Multi-Agent AI
      </h1>
      <p className="text-sm text-neutral-500 dark:text-neutral-400 mb-6">
        What can I help you accomplish today?
      </p>

      {/* Capabilities List */}
      <div className="flex flex-wrap justify-center gap-1.5 max-w-lg mb-8">
        {capabilities.map((cap, i) => {
          const Icon = cap.icon;
          return (
            <span
              key={i}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0A0A0A] text-neutral-600 dark:text-neutral-400 font-medium"
            >
              <Icon className="w-3 h-3 text-neutral-500" />
              <span>{cap.label}</span>
            </span>
          );
        })}
      </div>

      {/* Clickable Example Prompts */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 w-full text-left">
        {examplePrompts.map((item, idx) => (
          <button
            key={idx}
            type="button"
            onClick={() => onSelectPrompt(item.prompt)}
            className="p-3 rounded-lg border border-neutral-200 dark:border-neutral-800/80 bg-white dark:bg-[#0E0E0E] hover:border-neutral-400 dark:hover:border-neutral-600 hover:bg-neutral-50 dark:hover:bg-[#141414] transition-all text-left group"
          >
            <div className="text-xs font-medium text-neutral-800 dark:text-neutral-200 group-hover:text-black dark:group-hover:text-white mb-0.5">
              {item.title}
            </div>
            <div className="text-xs text-neutral-500 dark:text-neutral-400 line-clamp-1">
              &ldquo;{item.prompt}&rdquo;
            </div>
          </button>
        ))}
      </div>
    </div>
  );
};
