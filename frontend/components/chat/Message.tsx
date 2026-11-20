'use client';

import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Copy,
  Check,
  RotateCw,
  CheckCircle2,
  XCircle,
  Pencil,
  History,
  Share2,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  Image as ImageIcon,
  X,
  Maximize2,
} from 'lucide-react';
import { ChatMessage, MessageVersion } from '@/lib/types';

interface MessageProps {
  message: ChatMessage;
  onRegenerate?: () => void;
  onConfirmAction?: (approved: boolean) => void;
  isLatestAssistant?: boolean;
  onEdit?: (newContent: string) => void;
  onSelectVersion?: (versionIndex: number) => void;
}

export const Message: React.FC<MessageProps> = ({
  message,
  onRegenerate,
  onConfirmAction,
  isLatestAssistant = false,
  onEdit,
  onSelectVersion,
}) => {
  const [copied, setCopied] = useState(false);
  const [shared, setShared] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editContent, setEditContent] = useState(message.content);
  const [showVersionsMenu, setShowVersionsMenu] = useState(false);
  const [zoomedImage, setZoomedImage] = useState<{ src: string; alt: string } | null>(null);

  const editTextareaRef = useRef<HTMLTextAreaElement>(null);
  const versionsMenuRef = useRef<HTMLDivElement>(null);

  const isUser = message.role === 'user';

  // Synchronize edit content when message content updates
  useEffect(() => {
    setEditContent(message.content);
  }, [message.content]);

  // Focus textarea when entering edit mode
  useEffect(() => {
    if (isEditing && editTextareaRef.current) {
      editTextareaRef.current.focus();
      editTextareaRef.current.setSelectionRange(
        editTextareaRef.current.value.length,
        editTextareaRef.current.value.length
      );
    }
  }, [isEditing]);

  // Close versions menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (versionsMenuRef.current && !versionsMenuRef.current.contains(event.target as Node)) {
        setShowVersionsMenu(false);
      }
    };
    if (showVersionsMenu) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [showVersionsMenu]);

  const handleCopy = () => {
    if (!message.content) return;
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleShare = () => {
    if (!message.content) return;
    if (navigator.share) {
      navigator.share({
        title: 'Multi-Agent AI Message',
        text: message.content,
      }).catch(() => {});
    } else {
      navigator.clipboard.writeText(message.content);
      setShared(true);
      setTimeout(() => setShared(false), 2000);
    }
  };

  const handleSaveEdit = () => {
    const trimmed = editContent.trim();
    if (!trimmed) return;
    if (trimmed !== message.content && onEdit) {
      onEdit(trimmed);
    }
    setIsEditing(false);
  };

  const handleCancelEdit = () => {
    setEditContent(message.content);
    setIsEditing(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSaveEdit();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      handleCancelEdit();
    }
  };

  // Versions calculation
  const versions = message.versions || [];
  const hasMultipleVersions = versions.length > 1;
  const currentVerIndex =
    message.currentVersionIndex !== undefined
      ? message.currentVersionIndex
      : Math.max(0, versions.length - 1);

  const handlePrevVersion = () => {
    if (currentVerIndex > 0 && onSelectVersion) {
      onSelectVersion(currentVerIndex - 1);
    }
  };

  const handleNextVersion = () => {
    if (currentVerIndex < versions.length - 1 && onSelectVersion) {
      onSelectVersion(currentVerIndex + 1);
    }
  };

  // Custom CodeBlock component for Markdown code snippets
  const CodeBlock = ({ node, inline, className, children, ...props }: any) => {
    const [copiedCode, setCopiedCode] = useState(false);
    const match = /language-(\w+)/.exec(className || '');
    const codeString = String(children).replace(/\n$/, '');

    const handleCopyCode = () => {
      navigator.clipboard.writeText(codeString);
      setCopiedCode(true);
      setTimeout(() => setCopiedCode(false), 2000);
    };

    if (inline) {
      return (
        <code
          className="px-1.5 py-0.5 rounded bg-neutral-200/80 dark:bg-[#181818] text-black dark:text-neutral-100 font-mono text-xs border border-neutral-300 dark:border-neutral-800 font-semibold"
          {...props}
        >
          {children}
        </code>
      );
    }

    return (
      <div className="relative my-3 rounded-lg overflow-hidden border border-neutral-300 dark:border-neutral-800 bg-neutral-100 dark:bg-[#0E0E0E] text-xs">
        <div className="flex items-center justify-between px-3 py-1.5 bg-neutral-200 dark:bg-[#161616] text-[11px] text-black dark:text-neutral-300 font-mono font-semibold border-b border-neutral-300 dark:border-neutral-800">
          <span>{match ? match[1] : 'code'}</span>
          <button
            type="button"
            onClick={handleCopyCode}
            className="flex items-center gap-1 text-black dark:text-neutral-300 hover:opacity-70 transition-opacity"
            title="Copy code"
          >
            {copiedCode ? (
              <>
                <Check className="w-3.5 h-3.5 text-black dark:text-white" />
                <span>Copied</span>
              </>
            ) : (
              <>
                <Copy className="w-3.5 h-3.5" />
                <span>Copy</span>
              </>
            )}
          </button>
        </div>
        <div className="p-3 overflow-x-auto font-mono text-black dark:text-neutral-100 font-medium">
          <pre>
            <code className={className} {...props}>
              {children}
            </code>
          </pre>
        </div>
      </div>
    );
  };

  // Custom Image component with zoom, caption, and fallback
  const MarkdownImage = ({ src, alt, ...props }: any) => {
    const [hasError, setHasError] = useState(false);
    const [isLoading, setIsLoading] = useState(true);

    if (!src || hasError) {
      return (
        <div className="my-3 p-3 rounded-lg border border-neutral-300 dark:border-neutral-800 bg-neutral-100/70 dark:bg-[#141414] text-xs flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 text-neutral-600 dark:text-neutral-400">
            <ImageIcon className="w-4 h-4 shrink-0 text-neutral-500" />
            <span className="font-medium italic">{alt || 'Visual diagram / illustration'}</span>
          </div>
          {src && (
            <a
              href={src}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-blue-600 dark:text-blue-400 hover:underline font-medium text-[11px]"
            >
              <span>View Image</span>
              <ExternalLink className="w-3 h-3" />
            </a>
          )}
        </div>
      );
    }

    return (
      <figure className="my-4 group/img relative inline-block max-w-full">
        <div className="relative overflow-hidden rounded-xl border border-neutral-200 dark:border-neutral-800 bg-neutral-100 dark:bg-[#121212] shadow-sm">
          {isLoading && (
            <div className="h-48 w-full flex items-center justify-center bg-neutral-200/50 dark:bg-[#181818] animate-pulse text-xs text-neutral-400">
              <span>Loading media...</span>
            </div>
          )}
          <img
            src={src}
            alt={alt || 'Visual Media'}
            loading="lazy"
            onLoad={() => setIsLoading(false)}
            onError={() => setHasError(true)}
            className={`max-h-[460px] w-auto max-w-full object-contain rounded-xl transition-all duration-300 cursor-zoom-in ${
              isLoading ? 'hidden' : 'block hover:scale-[1.01]'
            }`}
            onClick={() => setZoomedImage({ src, alt: alt || 'Enlarged Image' })}
            {...props}
          />
          {/* Zoom hover button */}
          {!isLoading && (
            <button
              type="button"
              onClick={() => setZoomedImage({ src, alt: alt || 'Enlarged Image' })}
              className="absolute top-2 right-2 p-1.5 rounded-lg bg-black/60 hover:bg-black/80 text-white opacity-0 group-hover/img:opacity-100 transition-opacity backdrop-blur-sm"
              title="Click to expand"
            >
              <Maximize2 className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
        {alt && (
          <figcaption className="mt-1.5 text-center text-xs text-neutral-500 dark:text-neutral-400 font-medium">
            {alt}
          </figcaption>
        )}
      </figure>
    );
  };

  // ----------------------------------------------------
  // USER MESSAGE RENDERING
  // ----------------------------------------------------
  if (isUser) {
    return (
      <div className="py-3 flex flex-col items-end w-full group/user">
        {isEditing ? (
          <div className="w-full max-w-[85%] sm:max-w-[80%] rounded-2xl p-3 bg-neutral-100 dark:bg-[#161616] border border-neutral-300 dark:border-neutral-700 shadow-md">
            <textarea
              ref={editTextareaRef}
              value={editContent}
              onChange={(e) => setEditContent(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={3}
              className="w-full bg-transparent text-neutral-900 dark:text-neutral-100 text-sm leading-relaxed outline-none resize-none placeholder-neutral-400 font-sans"
              placeholder="Edit your message..."
            />
            <div className="flex items-center justify-between pt-2 border-t border-neutral-200 dark:border-neutral-800 text-xs">
              <span className="text-[11px] text-neutral-500 dark:text-neutral-400">
                Press <kbd className="px-1 py-0.5 rounded bg-neutral-200 dark:bg-neutral-800 font-mono">Enter</kbd> to save, <kbd className="px-1 py-0.5 rounded bg-neutral-200 dark:bg-neutral-800 font-mono">Esc</kbd> to cancel
              </span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleCancelEdit}
                  className="px-3 py-1.5 rounded-lg border border-neutral-300 dark:border-neutral-700 text-neutral-700 dark:text-neutral-300 hover:bg-neutral-200 dark:hover:bg-neutral-800 font-medium transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleSaveEdit}
                  disabled={!editContent.trim()}
                  className="px-3.5 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium transition-colors disabled:opacity-50"
                >
                  Save &amp; Submit
                </button>
              </div>
            </div>
          </div>
        ) : (
          <>
            {/* User message bubble */}
            <div className="max-w-[85%] sm:max-w-[75%] rounded-2xl px-4 py-2.5 bg-[#1c3d73] dark:bg-[#1a365d] text-white text-sm leading-relaxed whitespace-pre-wrap select-text shadow-sm font-sans">
              {message.content}
            </div>

            {/* User action bar (Copy, Share, See versions, Edit) */}
            <div className="relative flex items-center gap-1.5 mt-1.5 text-neutral-400 dark:text-neutral-500">
              {/* Copy button */}
              <button
                type="button"
                onClick={handleCopy}
                className="p-1.5 rounded-lg hover:text-neutral-200 hover:bg-neutral-800/60 transition-colors"
                title={copied ? 'Copied!' : 'Copy'}
              >
                {copied ? (
                  <Check className="w-4 h-4 text-emerald-400" />
                ) : (
                  <Copy className="w-4 h-4" />
                )}
              </button>

              {/* Share button */}
              <button
                type="button"
                onClick={handleShare}
                className="p-1.5 rounded-lg hover:text-neutral-200 hover:bg-neutral-800/60 transition-colors"
                title={shared ? 'Link Copied!' : 'Share'}
              >
                {shared ? (
                  <Check className="w-4 h-4 text-emerald-400" />
                ) : (
                  <Share2 className="w-4 h-4" />
                )}
              </button>

              {/* History / See versions button */}
              <div className="relative" ref={versionsMenuRef}>
                <button
                  type="button"
                  onClick={() => setShowVersionsMenu(!showVersionsMenu)}
                  className={`p-1.5 rounded-lg transition-colors relative group/vbtn ${
                    showVersionsMenu || hasMultipleVersions
                      ? 'text-neutral-200 bg-neutral-800/70'
                      : 'hover:text-neutral-200 hover:bg-neutral-800/60'
                  }`}
                  title="See versions"
                >
                  <History className="w-4 h-4" />
                  {/* Tooltip */}
                  <span className="pointer-events-none absolute -top-8 left-1/2 -translate-x-1/2 px-2 py-0.5 rounded bg-neutral-800 text-white text-[11px] font-medium whitespace-nowrap opacity-0 group-hover/vbtn:opacity-100 transition-opacity shadow">
                    See versions
                  </span>
                </button>

                {/* Versions Dropdown Popover */}
                {showVersionsMenu && (
                  <div className="absolute right-0 top-8 z-30 w-64 rounded-xl border border-neutral-700 bg-[#161616] text-neutral-100 shadow-xl p-2.5 text-xs animate-in fade-in zoom-in-95">
                    <div className="flex items-center justify-between pb-2 mb-2 border-b border-neutral-800">
                      <span className="font-semibold text-neutral-200 flex items-center gap-1.5">
                        <History className="w-3.5 h-3.5 text-neutral-400" />
                        <span>Message Versions</span>
                      </span>
                      <span className="text-[11px] text-neutral-400 font-mono">
                        {currentVerIndex + 1} / {Math.max(versions.length, 1)}
                      </span>
                    </div>

                    <div className="max-h-48 overflow-y-auto space-y-1.5">
                      {versions.length > 0 ? (
                        versions.map((ver, idx) => {
                          const isActive = idx === currentVerIndex;
                          return (
                            <button
                              key={idx}
                              type="button"
                              onClick={() => {
                                if (onSelectVersion) onSelectVersion(idx);
                                setShowVersionsMenu(false);
                              }}
                              className={`w-full text-left p-2 rounded-lg transition-colors flex flex-col gap-0.5 ${
                                isActive
                                  ? 'bg-blue-600/20 border border-blue-500/40 text-blue-200'
                                  : 'hover:bg-neutral-800 text-neutral-300'
                              }`}
                            >
                              <div className="flex items-center justify-between text-[11px]">
                                <span className="font-semibold">Version {ver.version || idx + 1}</span>
                                {isActive && (
                                  <span className="px-1.5 py-0.2 rounded bg-blue-500/30 text-blue-300 font-medium text-[10px]">
                                    Active
                                  </span>
                                )}
                              </div>
                              <p className="text-neutral-400 line-clamp-2 text-[11px] leading-tight mt-0.5">
                                {ver.content}
                              </p>
                            </button>
                          );
                        })
                      ) : (
                        <div className="p-2 text-center text-neutral-400 text-[11px]">
                          This is the initial version of your message.
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* Version quick pager < 1/2 > if multiple versions exist */}
              {hasMultipleVersions && (
                <div className="flex items-center gap-0.5 px-1 py-0.5 rounded-lg bg-neutral-800/60 text-[11px] font-mono text-neutral-300">
                  <button
                    type="button"
                    onClick={handlePrevVersion}
                    disabled={currentVerIndex === 0}
                    className="p-0.5 hover:text-white disabled:opacity-30 disabled:hover:text-neutral-300"
                    title="Previous version"
                  >
                    <ChevronLeft className="w-3.5 h-3.5" />
                  </button>
                  <span className="px-1 text-[10px]">
                    {currentVerIndex + 1}/{versions.length}
                  </span>
                  <button
                    type="button"
                    onClick={handleNextVersion}
                    disabled={currentVerIndex >= versions.length - 1}
                    className="p-0.5 hover:text-white disabled:opacity-30 disabled:hover:text-neutral-300"
                    title="Next version"
                  >
                    <ChevronRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              )}

              {/* Edit button */}
              <button
                type="button"
                onClick={() => {
                  setEditContent(message.content);
                  setIsEditing(true);
                }}
                className="p-1.5 rounded-lg hover:text-neutral-200 hover:bg-neutral-800/60 transition-colors"
                title="Edit message"
              >
                <Pencil className="w-4 h-4" />
              </button>
            </div>
          </>
        )}
      </div>
    );
  }

  // ----------------------------------------------------
  // ASSISTANT MESSAGE RENDERING
  // ----------------------------------------------------
  return (
    <div className="py-3 w-full group">
      {/* Lightbox Zoom Modal */}
      {zoomedImage && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-sm p-4 animate-in fade-in duration-200"
          onClick={() => setZoomedImage(null)}
        >
          <div className="relative max-w-4xl max-h-[90vh] flex flex-col items-center">
            <button
              type="button"
              onClick={() => setZoomedImage(null)}
              className="absolute -top-10 right-0 p-1.5 text-neutral-400 hover:text-white bg-white/10 hover:bg-white/20 rounded-full transition-colors"
              title="Close"
            >
              <X className="w-5 h-5" />
            </button>
            <img
              src={zoomedImage.src}
              alt={zoomedImage.alt}
              className="max-h-[80vh] w-auto max-w-full rounded-lg object-contain shadow-2xl"
              onClick={(e) => e.stopPropagation()}
            />
            {zoomedImage.alt && (
              <p className="mt-3 text-sm text-neutral-200 text-center font-medium bg-black/60 px-4 py-1.5 rounded-full">
                {zoomedImage.alt}
              </p>
            )}
          </div>
        </div>
      )}

      {/* Human In The Loop Action Confirmation Banner */}
      {message.confirmation_required && message.pending_action && onConfirmAction && (
        <div className="my-3 p-3.5 rounded-lg border border-neutral-300 dark:border-neutral-700 bg-neutral-50 dark:bg-[#111111] text-xs">
          <div className="font-semibold text-neutral-900 dark:text-neutral-100 flex items-center gap-1.5 mb-1">
            <span>Action Confirmation Required</span>
          </div>
          <p className="text-neutral-600 dark:text-neutral-400 mb-3">
            The multi-agent workflow prepared the following action for execution:
          </p>
          <div className="p-2.5 rounded bg-white dark:bg-[#181818] border border-neutral-200 dark:border-neutral-800 font-mono text-[11px] mb-3">
            <div>
              <span className="text-neutral-500">Action:</span>{' '}
              <span className="font-semibold text-neutral-900 dark:text-neutral-100">
                {message.pending_action.action}
              </span>
            </div>
            {message.pending_action.recipient && (
              <div>
                <span className="text-neutral-500">Recipient:</span> {message.pending_action.recipient}
              </div>
            )}
            {message.pending_action.subject && (
              <div>
                <span className="text-neutral-500">Subject:</span> {message.pending_action.subject}
              </div>
            )}
            {message.pending_action.title && (
              <div>
                <span className="text-neutral-500">Event:</span> {message.pending_action.title}
              </div>
            )}
            {message.pending_action.date && (
              <div>
                <span className="text-neutral-500">Date/Time:</span> {message.pending_action.date} {message.pending_action.time || ''}
              </div>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => onConfirmAction(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-black dark:bg-white text-white dark:text-black font-medium text-xs hover:opacity-90 transition-opacity"
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Approve &amp; Execute</span>
            </button>
            <button
              type="button"
              onClick={() => onConfirmAction(false)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded border border-neutral-300 dark:border-neutral-700 text-neutral-700 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors text-xs"
            >
              <XCircle className="w-3.5 h-3.5" />
              <span>Reject / Cancel</span>
            </button>
          </div>
        </div>
      )}

      {/* Main Message Content */}
      <div className="text-black dark:text-[#E0E0E0] text-sm leading-relaxed prose dark:prose-invert max-w-none">
        {message.content ? (
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              code: CodeBlock,
              img: MarkdownImage,
              p: ({ children }) => <p className="my-2 text-black dark:text-[#E0E0E0] leading-relaxed">{children}</p>,
              strong: ({ children }) => <strong className="font-bold text-black dark:text-white">{children}</strong>,
              h1: ({ children }) => <h1 className="text-xl font-bold mt-5 mb-2.5 text-black dark:text-white">{children}</h1>,
              h2: ({ children }) => <h2 className="text-lg font-bold mt-4 mb-2 text-black dark:text-white">{children}</h2>,
              h3: ({ children }) => <h3 className="text-base font-semibold mt-3 mb-1.5 text-black dark:text-white">{children}</h3>,
              ul: ({ children }) => <ul className="list-disc pl-5 my-2.5 space-y-1 text-black dark:text-[#E0E0E0]">{children}</ul>,
              ol: ({ children }) => <ol className="list-decimal pl-5 my-2.5 space-y-1 text-black dark:text-[#E0E0E0]">{children}</ol>,
              li: ({ children }) => <li className="my-0.5 text-black dark:text-[#E0E0E0]">{children}</li>,
              blockquote: ({ children }) => (
                <blockquote className="border-l-2 border-neutral-700 dark:border-neutral-500 pl-3 my-2 italic text-black dark:text-neutral-300">
                  {children}
                </blockquote>
              ),
              table: ({ children }) => (
                <div className="overflow-x-auto my-3 border border-neutral-300 dark:border-neutral-800 rounded">
                  <table className="w-full text-xs text-left divide-y divide-neutral-300 dark:divide-neutral-800 text-black dark:text-neutral-200">
                    {children}
                  </table>
                </div>
              ),
              thead: ({ children }) => (
                <thead className="bg-neutral-200/80 dark:bg-[#141414] font-bold text-black dark:text-neutral-100">
                  {children}
                </thead>
              ),
              th: ({ children }) => <th className="p-2 border-r border-neutral-300 dark:border-neutral-800 last:border-r-0 font-bold">{children}</th>,
              td: ({ children }) => <td className="p-2 border-r border-neutral-300 dark:border-neutral-800 last:border-r-0">{children}</td>,
              a: ({ href, children }) => (
                <a
                  href={href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 font-medium text-blue-600 dark:text-blue-400 hover:text-blue-500 underline underline-offset-2 hover:opacity-90 transition-opacity"
                >
                  <span>{children}</span>
                  <ExternalLink className="w-3 h-3 inline-block shrink-0" />
                </a>
              ),
            }}
          >
            {message.content}
          </ReactMarkdown>
        ) : message.status === 'streaming' ? (
          <div className="flex items-center gap-2.5 text-xs text-neutral-800 dark:text-neutral-300 font-medium italic py-2">
            <span className="inline-block w-2 h-2 rounded-full bg-blue-500 animate-ping" />
            <span>
              {message.current_agent === 'research'
                ? '🔍 Research Agent is searching web & media repositories...'
                : message.current_agent === 'writer'
                ? '✍️ Writer Agent is synthesizing the report & formatting media...'
                : message.current_agent === 'validator'
                ? '🛡️ Validator Agent is auditing response quality...'
                : message.current_agent === 'coding'
                ? '💻 Coding Agent is executing code...'
                : message.current_agent === 'database'
                ? '🗄️ Database Agent is querying records...'
                : message.current_agent === 'supervisor'
                ? '🧠 Supervisor Agent is analyzing and formulating execution plan...'
                : message.current_agent
                ? `⚡ ${message.current_agent} Agent is working...`
                : 'Thinking and orchestrating agents...'}
            </span>
          </div>
        ) : null}

      </div>

      {/* Action Buttons: Copy, Regenerate */}
      {message.content && message.status !== 'streaming' && (
        <div className="flex items-center gap-3 mt-3 pt-2 text-xs text-neutral-800 dark:text-neutral-400 font-medium">
          <button
            type="button"
            onClick={handleCopy}
            className="flex items-center gap-1 hover:text-black dark:hover:text-white transition-colors"
            title="Copy response"
          >
            {copied ? (
              <>
                <Check className="w-3.5 h-3.5 text-black dark:text-white" />
                <span>Copied</span>
              </>
            ) : (
              <>
                <Copy className="w-3.5 h-3.5" />
                <span>Copy</span>
              </>
            )}
          </button>

          {isLatestAssistant && onRegenerate && (
            <button
              type="button"
              onClick={onRegenerate}
              className="flex items-center gap-1 hover:text-black dark:hover:text-white transition-colors"
              title="Regenerate response"
            >
              <RotateCw className="w-3.5 h-3.5" />
              <span>Regenerate</span>
            </button>
          )}
        </div>
      )}
    </div>
  );
};
