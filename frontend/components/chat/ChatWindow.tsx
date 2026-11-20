'use client';

import React, { useRef, useEffect } from 'react';
import { ChatMessage } from '@/lib/types';
import { Message } from '@/components/chat/Message';
import { EmptyState } from '@/components/chat/EmptyState';
import { AlertCircle, RotateCcw } from 'lucide-react';

interface ChatWindowProps {
  messages: ChatMessage[];
  isLoading: boolean;
  onSelectPrompt: (prompt: string) => void;
  onRegenerate?: () => void;
  onConfirmAction?: (approved: boolean) => void;
  onRetryLast?: () => void;
  onEditMessage?: (messageIndex: number, newContent: string) => void;
  onSelectMessageVersion?: (messageIndex: number, versionIndex: number) => void;
  errorMessage?: string | null;
}

export const ChatWindow: React.FC<ChatWindowProps> = ({
  messages,
  isLoading,
  onSelectPrompt,
  onRegenerate,
  onConfirmAction,
  onRetryLast,
  onEditMessage,
  onSelectMessageVersion,
  errorMessage,
}) => {
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll when new messages arrive
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading, errorMessage]);

  if (messages.length === 0) {
    return (
      <div className="flex-1 overflow-y-auto flex flex-col justify-center">
        <EmptyState onSelectPrompt={onSelectPrompt} />
      </div>
    );
  }

  // Find index of the latest assistant message for showing actions
  let latestAssistantIndex = -1;
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].role === 'assistant') {
      latestAssistantIndex = i;
      break;
    }
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 py-6 scroll-smooth">
      <div className="max-w-3xl mx-auto space-y-4">
        {messages.map((msg, idx) => (
          <Message
            key={msg.id || idx}
            message={msg}
            onRegenerate={onRegenerate}
            onConfirmAction={onConfirmAction}
            isLatestAssistant={idx === latestAssistantIndex}
            onEdit={(newText) => onEditMessage?.(idx, newText)}
            onSelectVersion={(vIdx) => onSelectMessageVersion?.(idx, vIdx)}
          />
        ))}


        {/* Clean Inline Error State */}
        {errorMessage && (
          <div className="my-4 p-4 rounded-lg border border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-[#121212] text-xs">
            <div className="flex items-start gap-2.5">
              <AlertCircle className="w-4 h-4 text-neutral-600 dark:text-neutral-400 mt-0.5 shrink-0" />
              <div className="flex-1">
                <p className="font-medium text-neutral-900 dark:text-neutral-100">
                  Something went wrong.
                </p>
                <p className="text-neutral-500 dark:text-neutral-400 mt-0.5">
                  {errorMessage}
                </p>
                {onRetryLast && (
                  <button
                    type="button"
                    onClick={onRetryLast}
                    className="mt-2.5 inline-flex items-center gap-1.5 px-3 py-1.5 rounded border border-neutral-300 dark:border-neutral-700 hover:bg-neutral-200 dark:hover:bg-neutral-800 text-neutral-800 dark:text-neutral-200 font-medium transition-colors"
                  >
                    <RotateCcw className="w-3.5 h-3.5" />
                    <span>Retry</span>
                  </button>
                )}
              </div>
            </div>
          </div>
        )}

        <div ref={bottomRef} className="h-4" />
      </div>
    </div>
  );
};
