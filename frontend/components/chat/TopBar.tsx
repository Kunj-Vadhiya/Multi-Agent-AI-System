'use client';

import React from 'react';
import { Menu, Settings as SettingsIcon, Bot } from 'lucide-react';
import { ThemeToggle } from '@/components/theme/ThemeToggle';

interface TopBarProps {
  onOpenMobileSidebar: () => void;
  onToggleSidebar?: () => void;
  onOpenSettings: () => void;
  title?: string;
}

export const TopBar: React.FC<TopBarProps> = ({
  onOpenMobileSidebar,
  onToggleSidebar,
  onOpenSettings,
  title = 'Multi-Agent AI',
}) => {
  return (
    <header className="h-12 border-b border-neutral-200 dark:border-[#222222] bg-white dark:bg-black px-4 flex items-center justify-between shrink-0 select-none">
      {/* Left side: Mobile menu toggle + Clickable System Logo & App Name */}
      <div className="flex items-center gap-2.5">
        {/* Mobile menu button */}
        <button
          type="button"
          onClick={onOpenMobileSidebar}
          className="p-1.5 rounded-md text-neutral-600 dark:text-neutral-400 hover:text-black dark:hover:text-white lg:hidden"
          title="Open Menu"
        >
          <Menu className="w-4 h-4" />
        </button>

        {/* Clickable System Logo & Title: Clicking opens the sidebar */}
        <button
          type="button"
          onClick={onToggleSidebar || onOpenMobileSidebar}
          className="flex items-center gap-2 p-1.5 -ml-1 rounded-lg hover:bg-neutral-100 dark:hover:bg-neutral-900 transition-all group cursor-pointer"
          title="Click to toggle sidebar"
          aria-label="Toggle sidebar"
        >
          <div className="w-6 h-6 flex items-center justify-center rounded-md bg-neutral-100 dark:bg-neutral-800 text-neutral-800 dark:text-neutral-200 group-hover:scale-105 transition-transform">
            <Bot className="w-4 h-4" />
          </div>
          <span className="font-semibold text-xs tracking-tight text-neutral-900 dark:text-white group-hover:text-neutral-700 dark:group-hover:text-neutral-200 transition-colors">
            {title}
          </span>
        </button>
      </div>

      {/* Right side: Theme Toggle + Settings button */}
      <div className="flex items-center gap-1.5">
        <ThemeToggle />
        <button
          type="button"
          onClick={onOpenSettings}
          title="Settings"
          aria-label="Settings"
          className="p-2 rounded-md border border-neutral-300 dark:border-neutral-800 text-black dark:text-neutral-200 hover:bg-neutral-100 dark:hover:bg-neutral-900 transition-colors"
        >
          <SettingsIcon className="w-4 h-4" />
        </button>
      </div>
    </header>
  );
};
