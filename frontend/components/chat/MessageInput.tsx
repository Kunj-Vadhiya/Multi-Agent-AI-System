'use client';

import React, { useState, useRef, useEffect } from 'react';
import { ArrowUp, Paperclip, X, FileText, Check, Loader2 } from 'lucide-react';
import { uploadDocument } from '@/lib/api';

interface MessageInputProps {
  onSendMessage: (message: string) => void;
  isLoading: boolean;
  enterSendsMessage?: boolean;
  onDocumentUploaded?: () => void;
}

export const MessageInput: React.FC<MessageInputProps> = ({
  onSendMessage,
  isLoading,
  enterSendsMessage = true,
  onDocumentUploaded,
}) => {
  const [input, setInput] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadState, setUploadState] = useState<'idle' | 'uploading' | 'processing' | 'indexed' | 'error'>('idle');
  const [uploadError, setUploadError] = useState<string | null>(null);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Auto-resize textarea height up to 160px
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      const scrollHeight = textareaRef.current.scrollHeight;
      textareaRef.current.style.height = `${Math.min(scrollHeight, 160)}px`;
    }
  }, [input]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      if (enterSendsMessage) {
        e.preventDefault();
        handleSend();
      }
    }
  };

  const handleSend = () => {
    const trimmed = input.trim();
    if (!trimmed || isLoading) return;
    onSendMessage(trimmed);
    setInput('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setSelectedFile(file);
    setUploadState('uploading');
    setUploadError(null);

    try {
      setUploadState('uploading');
      setTimeout(() => setUploadState('processing'), 600);

      await uploadDocument(file);
      setUploadState('indexed');
      if (onDocumentUploaded) {
        onDocumentUploaded();
      }
      setTimeout(() => {
        setSelectedFile(null);
        setUploadState('idle');
      }, 3000);
    } catch (err: any) {
      setUploadState('error');
      setUploadError(err.message || 'Failed to upload document');
    } finally {
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const clearFile = () => {
    setSelectedFile(null);
    setUploadState('idle');
    setUploadError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  return (
    <div className="w-full max-w-3xl mx-auto px-4 pb-4">
      {/* File Upload Status Pill */}
      {selectedFile && (
        <div className="mb-2 p-2 rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#111111] flex items-center justify-between text-xs animate-in fade-in slide-in-from-bottom-1">
          <div className="flex items-center gap-2 truncate">
            <FileText className="w-4 h-4 text-neutral-500 shrink-0" />
            <span className="font-medium text-neutral-800 dark:text-neutral-200 truncate">
              {selectedFile.name}
            </span>

            {/* Status indicators */}
            {uploadState === 'uploading' && (
              <span className="flex items-center gap-1 text-neutral-500 text-[11px]">
                <Loader2 className="w-3 h-3 animate-spin" /> Uploading...
              </span>
            )}
            {uploadState === 'processing' && (
              <span className="flex items-center gap-1 text-neutral-500 text-[11px]">
                <Loader2 className="w-3 h-3 animate-spin" /> Chunking &amp; Indexing...
              </span>
            )}
            {uploadState === 'indexed' && (
              <span className="flex items-center gap-1 text-neutral-900 dark:text-neutral-100 font-medium text-[11px]">
                <Check className="w-3 h-3" /> Indexed ✓
              </span>
            )}
            {uploadState === 'error' && (
              <span className="text-red-500 text-[11px] truncate">
                {uploadError || 'Upload failed'}
              </span>
            )}
          </div>

          <button
            type="button"
            onClick={clearFile}
            className="p-1 text-neutral-400 hover:text-black dark:hover:text-white rounded"
            title="Remove file"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Main Input Box */}
      <div className="relative flex items-end gap-2 border border-neutral-400 dark:border-neutral-800 rounded-2xl bg-white dark:bg-[#101010] p-2 shadow-sm focus-within:border-black dark:focus-within:border-neutral-500 transition-all">
        {/* Hidden File Input */}
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileChange}
          accept=".pdf,.txt,.text,.md,.markdown"
          className="hidden"
          disabled={isLoading}
        />

        {/* Attachment Button */}
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={isLoading || uploadState === 'uploading' || uploadState === 'processing'}
          title="Upload Document (.pdf, .txt, .md)"
          className="p-2 text-neutral-800 hover:text-black dark:text-neutral-300 dark:hover:text-white hover:bg-neutral-100 dark:hover:bg-[#1a1a1a] rounded-xl transition-colors disabled:opacity-40"
        >
          <Paperclip className="w-4 h-4" />
        </button>

        {/* Auto-growing Textarea */}
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask anything..."
          rows={1}
          disabled={isLoading}
          className="flex-1 max-h-40 py-1.5 px-1 bg-transparent text-sm text-black dark:text-neutral-100 placeholder:text-neutral-600 dark:placeholder:text-neutral-500 resize-none focus:outline-none disabled:opacity-50"
        />

        {/* Send Button */}
        <button
          type="button"
          onClick={handleSend}
          disabled={!input.trim() || isLoading}
          title="Send message"
          className="p-2 rounded-xl bg-black dark:bg-white text-white dark:text-black hover:opacity-85 disabled:opacity-20 disabled:hover:opacity-20 transition-all shrink-0"
        >
          {isLoading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <ArrowUp className="w-4 h-4 stroke-[2.5]" />
          )}
        </button>
      </div>

      <div className="text-center mt-2">
        <span className="text-[11px] text-neutral-600 dark:text-neutral-500 font-medium select-none">
          Multi-Agent AI can produce inaccurate results. Verify important info.
        </span>
      </div>
    </div>
  );
};
