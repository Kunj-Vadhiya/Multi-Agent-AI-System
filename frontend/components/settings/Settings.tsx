'use client';

import React, { useState, useEffect } from 'react';
import { X, Check, Globe, Sliders, Moon, Sun, Info, Loader2 } from 'lucide-react';
import { checkHealth, getApiBaseUrl, setApiBaseUrl } from '@/lib/api';

interface SettingsProps {
  isOpen: boolean;
  onClose: () => void;
  enterSendsMessage: boolean;
  onToggleEnterSendsMessage: (val: boolean) => void;
  onThemeChanged?: (theme: 'light' | 'dark') => void;
}

export const Settings: React.FC<SettingsProps> = ({
  isOpen,
  onClose,
  enterSendsMessage,
  onToggleEnterSendsMessage,
  onThemeChanged,
}) => {
  const [currentTheme, setCurrentTheme] = useState<'light' | 'dark'>('light');
  const [apiUrl, setApiUrlState] = useState('');
  const [testStatus, setTestStatus] = useState<'idle' | 'testing' | 'success' | 'error'>('idle');
  const [testMessage, setTestMessage] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      const isDark = document.documentElement.classList.contains('dark');
      setCurrentTheme(isDark ? 'dark' : 'light');
      setApiUrlState(getApiBaseUrl());
      setTestStatus('idle');
      setTestMessage(null);
    }
  }, [isOpen]);

  const handleSelectTheme = (theme: 'light' | 'dark') => {
    setCurrentTheme(theme);
    localStorage.setItem('theme', theme);
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
    if (onThemeChanged) {
      onThemeChanged(theme);
    }
  };

  const handleSaveApiUrl = () => {
    setApiBaseUrl(apiUrl);
  };

  const handleTestConnection = async () => {
    handleSaveApiUrl();
    setTestStatus('testing');
    setTestMessage(null);
    try {
      const res = await checkHealth();
      setTestStatus('success');
      setTestMessage(`Connected successfully (${res.status})`);
    } catch (err: any) {
      setTestStatus('error');
      setTestMessage(err.message || 'Connection failed');
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-150">
      <div
        className="w-full max-w-md rounded-2xl border border-neutral-200 dark:border-[#222222] bg-white dark:bg-[#0D0D0D] shadow-2xl overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-4 border-b border-neutral-200 dark:border-neutral-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sliders className="w-4 h-4 text-neutral-800 dark:text-neutral-200" />
            <h2 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">
              Settings
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded text-neutral-500 hover:text-black dark:hover:text-white transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="p-4 space-y-5 text-xs text-neutral-800 dark:text-neutral-200 overflow-y-auto max-h-[75vh]">
          {/* Appearance Section */}
          <div className="space-y-2">
            <label className="text-[11px] font-semibold text-neutral-500 uppercase tracking-wider block">
              Appearance
            </label>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => handleSelectTheme('light')}
                className={`flex items-center justify-center gap-2 p-2.5 rounded-lg border text-xs font-medium transition-all ${
                  currentTheme === 'light'
                    ? 'border-black dark:border-white bg-neutral-100 dark:bg-neutral-800 text-black dark:text-white shadow-sm'
                    : 'border-neutral-200 dark:border-neutral-800 hover:bg-neutral-50 dark:hover:bg-neutral-900 text-neutral-600 dark:text-neutral-400'
                }`}
              >
                <Sun className="w-4 h-4" />
                <span>Light</span>
              </button>
              <button
                type="button"
                onClick={() => handleSelectTheme('dark')}
                className={`flex items-center justify-center gap-2 p-2.5 rounded-lg border text-xs font-medium transition-all ${
                  currentTheme === 'dark'
                    ? 'border-black dark:border-white bg-neutral-100 dark:bg-neutral-800 text-black dark:text-white shadow-sm'
                    : 'border-neutral-200 dark:border-neutral-800 hover:bg-neutral-50 dark:hover:bg-neutral-900 text-neutral-600 dark:text-neutral-400'
                }`}
              >
                <Moon className="w-4 h-4" />
                <span>Black Dark</span>
              </button>
            </div>
          </div>

          {/* Chat Behavior Section */}
          <div className="space-y-2 pt-2 border-t border-neutral-200 dark:border-neutral-800">
            <label className="text-[11px] font-semibold text-neutral-500 uppercase tracking-wider block">
              Chat
            </label>
            <label className="flex items-center gap-2.5 cursor-pointer py-1 select-none">
              <input
                type="checkbox"
                checked={enterSendsMessage}
                onChange={(e) => onToggleEnterSendsMessage(e.target.checked)}
                className="rounded border-neutral-300 dark:border-neutral-700 text-black focus:ring-0 w-4 h-4 accent-neutral-800 dark:accent-neutral-200"
              />
              <span className="text-neutral-700 dark:text-neutral-300">
                Enter sends message (Shift + Enter for new line)
              </span>
            </label>
          </div>

          {/* API Server Section */}
          <div className="space-y-2 pt-2 border-t border-neutral-200 dark:border-neutral-800">
            <label className="text-[11px] font-semibold text-neutral-500 uppercase tracking-wider block">
              Backend API Server
            </label>
            <div className="flex items-center gap-2">
              <div className="relative flex-1">
                <Globe className="w-3.5 h-3.5 absolute left-2.5 top-3 text-neutral-400" />
                <input
                  type="text"
                  value={apiUrl}
                  onChange={(e) => setApiUrlState(e.target.value)}
                  onBlur={handleSaveApiUrl}
                  placeholder="http://127.0.0.1:8000"
                  className="w-full pl-8 pr-3 py-2 rounded-lg border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-[#141414] text-xs font-mono focus:outline-none focus:border-neutral-500"
                />
              </div>
              <button
                type="button"
                onClick={handleTestConnection}
                disabled={testStatus === 'testing'}
                className="px-3 py-2 rounded-lg border border-neutral-300 dark:border-neutral-700 bg-neutral-100 dark:bg-neutral-800 text-neutral-800 dark:text-neutral-200 hover:bg-neutral-200 dark:hover:bg-neutral-700 transition-colors font-medium shrink-0"
              >
                {testStatus === 'testing' ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  'Test'
                )}
              </button>
            </div>

            {testMessage && (
              <p
                className={`text-[11px] mt-1 ${
                  testStatus === 'success' ? 'text-neutral-800 dark:text-neutral-200 font-medium' : 'text-red-500'
                }`}
              >
                {testMessage}
              </p>
            )}
          </div>

          {/* About Section */}
          <div className="space-y-1.5 pt-2 border-t border-neutral-200 dark:border-neutral-800 text-[11px] text-neutral-500 dark:text-neutral-400">
            <div className="flex items-center gap-1.5 font-semibold text-neutral-700 dark:text-neutral-300">
              <Info className="w-3.5 h-3.5" />
              <span>About</span>
            </div>
            <p>Multi-Agent AI Task Automation Studio</p>
            <p className="font-mono text-[10px] text-neutral-400">Version 7.0.0 · LangGraph + Groq + SQLite RAG</p>
          </div>
        </div>

        {/* Footer */}
        <div className="p-3 border-t border-neutral-200 dark:border-neutral-800 bg-neutral-50/50 dark:bg-[#0A0A0A] flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-3.5 py-1.5 rounded-lg border border-neutral-300 dark:border-neutral-700 text-xs font-medium text-neutral-700 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
};
