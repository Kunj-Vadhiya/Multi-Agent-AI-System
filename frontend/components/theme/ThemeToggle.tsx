'use client';

import React, { useEffect, useState } from 'react';
import { Sun, Moon } from 'lucide-react';

interface ThemeToggleProps {
  className?: string;
  showLabel?: boolean;
}

export const ThemeToggle: React.FC<ThemeToggleProps> = ({ className = '', showLabel = false }) => {
  const [theme, setTheme] = useState<'light' | 'dark'>('light');
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const stored = localStorage.getItem('theme') as 'light' | 'dark' | null;
    if (stored === 'dark' || stored === 'light') {
      setTheme(stored);
      applyTheme(stored);
    } else {
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      const initial = prefersDark ? 'dark' : 'light';
      setTheme(initial);
      applyTheme(initial);
    }
  }, []);

  const applyTheme = (t: 'light' | 'dark') => {
    if (t === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  };

  const toggleTheme = () => {
    const nextTheme = theme === 'light' ? 'dark' : 'light';
    setTheme(nextTheme);
    localStorage.setItem('theme', nextTheme);
    applyTheme(nextTheme);
  };

  if (!mounted) {
    return (
      <button
        type="button"
        aria-label="Toggle Theme"
        className={`p-2 rounded-md border border-neutral-200 dark:border-neutral-800 text-neutral-600 dark:text-neutral-400 hover:text-black dark:hover:text-white transition-colors ${className}`}
      >
        <span className="w-4 h-4 block opacity-0" />
      </button>
    );
  }

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={`Switch to ${theme === 'light' ? 'black dark' : 'light'} mode`}
      title={`Switch to ${theme === 'light' ? 'Dark' : 'Light'} mode`}
      className={`flex items-center gap-2 p-2 rounded-md border border-neutral-300 dark:border-neutral-800 text-black dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-900 transition-colors focus:outline-none focus:ring-1 focus:ring-neutral-400 dark:focus:ring-neutral-600 ${className}`}
    >
      {theme === 'light' ? (
        <>
          <Moon className="w-4 h-4" />
          {showLabel && <span className="text-xs font-medium">Dark</span>}
        </>
      ) : (
        <>
          <Sun className="w-4 h-4" />
          {showLabel && <span className="text-xs font-medium">Light</span>}
        </>
      )}
    </button>
  );
};
