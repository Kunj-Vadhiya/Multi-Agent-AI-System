'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { TopBar } from '@/components/chat/TopBar';
import { Sidebar } from '@/components/sidebar/Sidebar';
import { ChatWindow } from '@/components/chat/ChatWindow';
import { MessageInput } from '@/components/chat/MessageInput';
import { KnowledgeBase } from '@/components/documents/KnowledgeBase';
import { Settings } from '@/components/settings/Settings';
import { ChatMessage, ThreadSummary } from '@/lib/types';
import {
  getThreads,
  getThread,
  createThread,
  renameThread,
  deleteThread,
  streamMessage,
  getDocuments,
} from '@/lib/api';

export default function WorkspacePage() {
  const [threads, setThreads] = useState<ThreadSummary[]>([]);
  const [activeThreadId, setActiveThreadId] = useState<string | undefined>(undefined);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingThreads, setIsLoadingThreads] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Modals & Drawers
  const [isKnowledgeBaseOpen, setIsKnowledgeBaseOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
  const [documentCount, setDocumentCount] = useState(0);

  // Movable / Resizable Sidebar state
  const [sidebarWidth, setSidebarWidth] = useState(260);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isDrawerOpen, setIsDrawerOpen] = useState(true);

  // Preferences
  const [enterSendsMessage, setEnterSendsMessage] = useState(true);

  // Load preferences and sidebar layout from localStorage
  useEffect(() => {
    try {
      const storedEnter = localStorage.getItem('enter_sends_message');
      if (storedEnter !== null) {
        setEnterSendsMessage(storedEnter === 'true');
      }
      const storedWidth = localStorage.getItem('sidebar_width');
      if (storedWidth) {
        const parsed = parseInt(storedWidth, 10);
        if (!isNaN(parsed) && parsed >= 180 && parsed <= 650) {
          setSidebarWidth(parsed);
        }
      }
      const storedCollapsed = localStorage.getItem('sidebar_collapsed');
      if (storedCollapsed !== null) {
        setIsSidebarCollapsed(storedCollapsed === 'true');
      }
      const storedDrawer = localStorage.getItem('chat_drawer_open');
      if (storedDrawer !== null) {
        setIsDrawerOpen(storedDrawer === 'true');
      }
    } catch {}
  }, []);

  const handleWidthChange = (newWidth: number) => {
    setSidebarWidth(newWidth);
    try {
      localStorage.setItem('sidebar_width', String(newWidth));
    } catch {}
  };

  const handleToggleSidebar = () => {
    setIsDrawerOpen((prev) => {
      const next = !prev;
      try {
        localStorage.setItem('chat_drawer_open', String(next));
      } catch {}
      return next;
    });
  };

  const handleToggleCollapse = () => {
    setIsSidebarCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem('sidebar_collapsed', String(next));
      } catch {}
      return next;
    });
  };

  const handleToggleEnter = (val: boolean) => {
    setEnterSendsMessage(val);
    try {
      localStorage.setItem('enter_sends_message', String(val));
    } catch {}
  };

  // Fetch threads list
  const refreshThreads = useCallback(async () => {
    try {
      setIsLoadingThreads(true);
      const list = await getThreads();
      setThreads(list);
    } catch (err) {
      console.warn('Could not load threads:', err);
    } finally {
      setIsLoadingThreads(false);
    }
  }, []);

  // Fetch documents count
  const refreshDocumentsCount = useCallback(async () => {
    try {
      const res = await getDocuments();
      setDocumentCount(res.total_documents || 0);
    } catch (err) {
      console.warn('Could not load documents count:', err);
    }
  }, []);

  // Initial load
  useEffect(() => {
    refreshThreads();
    refreshDocumentsCount();
  }, [refreshThreads, refreshDocumentsCount]);

  // Keyboard shortcut Ctrl+N for new chat
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'n') {
        e.preventDefault();
        handleNewChat();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Start a new conversation
  const handleNewChat = () => {
    setActiveThreadId(undefined);
    setMessages([]);
    setErrorMessage(null);
  };

  // Select existing conversation
  const handleSelectThread = async (threadId: string) => {
    if (threadId === activeThreadId && messages.length > 0) return;
    setActiveThreadId(threadId);
    setErrorMessage(null);
    try {
      const data = await getThread(threadId);
      const mappedMessages: ChatMessage[] = (data.messages || []).map((m: any, idx: number) => ({
        id: `${threadId}_${idx}`,
        role: m.role,
        content: m.content || '',
        versions:
          m.role === 'user'
            ? [{ version: 1, content: m.content || '', timestamp: new Date().toISOString() }]
            : undefined,
        currentVersionIndex: m.role === 'user' ? 0 : undefined,
        plan: idx === (data.messages || []).length - 1 ? data.plan : undefined,
        current_agent: idx === (data.messages || []).length - 1 ? data.current_agent : undefined,
        agent_history: idx === (data.messages || []).length - 1 ? data.agent_history : undefined,
        retrieved_documents: idx === (data.messages || []).length - 1 ? data.retrieved_documents : undefined,
        validation_result: idx === (data.messages || []).length - 1 ? data.validation_result : undefined,
        pending_action: idx === (data.messages || []).length - 1 ? data.pending_action : undefined,
        confirmation_required: idx === (data.messages || []).length - 1 ? data.confirmation_required : undefined,
        status: 'completed',
      }));
      setMessages(mappedMessages);

    } catch (err: any) {
      console.error('Failed to load thread:', err);
      setErrorMessage(`Failed to load conversation: ${err.message || 'Unknown error'}`);
    }
  };

  // Rename a conversation
  const handleRenameThread = async (threadId: string, newTitle: string) => {
    try {
      await renameThread(threadId, newTitle);
      setThreads((prev) =>
        prev.map((t) => (t.thread_id === threadId ? { ...t, title: newTitle } : t))
      );
    } catch (err) {
      console.error('Failed to rename thread:', err);
    }
  };

  // Delete a conversation
  const handleDeleteThread = async (threadId: string) => {
    try {
      await deleteThread(threadId);
      setThreads((prev) => prev.filter((t) => t.thread_id !== threadId));
      if (activeThreadId === threadId) {
        handleNewChat();
      }
    } catch (err) {
      console.error('Failed to delete thread:', err);
    }
  };

  // Send message
  const handleSendMessage = async (text: string, confirmAction?: boolean) => {
    if (!text.trim() || isLoading) return;

    setErrorMessage(null);
    setIsLoading(true);

    const userMsgId = `user_${Date.now()}`;
    const assistantMsgId = `ai_${Date.now() + 1}`;

    const userMessage: ChatMessage = {
      id: userMsgId,
      role: 'user',
      content: text,
      timestamp: new Date().toISOString(),
      versions: [{ version: 1, content: text, timestamp: new Date().toISOString() }],
      currentVersionIndex: 0,
    };

    const initialAssistantMessage: ChatMessage = {
      id: assistantMsgId,
      role: 'assistant',
      content: '',
      status: 'streaming',
      agent_history: [],
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage, initialAssistantMessage]);

    try {
      let currentThread = activeThreadId;

      // Send complete conversation history so the backend remembers all chats and context
      const historyPayload = messages
        .filter((m) => m.content && m.status !== 'streaming' && (m.role === 'user' || m.role === 'assistant'))
        .map((m) => ({ role: m.role, content: m.content }));

      await streamMessage(
        text,
        currentThread,
        (update) => {
          if (update.event === 'started') {
            if (!currentThread && update.thread_id) {
              currentThread = update.thread_id;
              setActiveThreadId(update.thread_id);
            }
          } else if (update.event === 'agent_start' || update.event === 'agent_completed') {
            setMessages((prev) =>
              prev.map((msg) => {
                if (msg.id !== assistantMsgId) return msg;
                return {
                  ...msg,
                  current_agent: update.agent || msg.current_agent,
                  plan: update.plan || msg.plan,
                  agent_history: update.agent_history || msg.agent_history,
                };
              })
            );
          } else if (update.event === 'done') {
            const targetThreadId = update.thread_id || currentThread;
            if (update.thread_id && !currentThread) {
              currentThread = update.thread_id;
              setActiveThreadId(update.thread_id);
            }
            if (update.thread_title && targetThreadId) {
              setThreads((prev) =>
                prev.map((t) =>
                  t.thread_id === targetThreadId ? { ...t, title: update.thread_title! } : t
                )
              );
            }
            setMessages((prev) =>
              prev.map((msg) => {
                if (msg.id !== assistantMsgId) return msg;
                return {
                  ...msg,
                  content: update.response || msg.content,
                  status: 'completed',
                  plan: update.plan || msg.plan,
                  current_agent: update.current_agent || msg.current_agent,
                  agent_history: update.agent_history || msg.agent_history,
                  retrieved_documents: update.retrieved_documents || msg.retrieved_documents,
                  validation_result: update.validation_result || msg.validation_result,
                  pending_action: update.pending_action,
                  confirmation_required: update.confirmation_required,
                };
              })
            );
          }
        },
        confirmAction,
        historyPayload
      );

      // Refresh threads list so the new thread and message counts update
      refreshThreads();
    } catch (err: any) {
      console.error('Chat execution failed:', err);
      setErrorMessage(err.message || 'Something went wrong while executing the workflow.');
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMsgId ? { ...msg, status: 'error', error_message: err.message } : msg
        )
      );
    } finally {
      setIsLoading(false);
    }
  };

  // Handle editing a user message and re-running the conversation branch
  const handleEditMessage = async (messageIndex: number, newContent: string) => {
    if (isLoading || !newContent.trim()) return;

    const targetMsg = messages[messageIndex];
    if (!targetMsg || targetMsg.role !== 'user') return;

    // Track versions
    const existingVersions = targetMsg.versions && targetMsg.versions.length > 0
      ? targetMsg.versions
      : [{ version: 1, content: targetMsg.content, timestamp: targetMsg.timestamp || new Date().toISOString() }];

    const newVersion = {
      version: existingVersions.length + 1,
      content: newContent,
      timestamp: new Date().toISOString(),
    };
    const updatedVersions = [...existingVersions, newVersion];

    const updatedUserMsg: ChatMessage = {
      ...targetMsg,
      content: newContent,
      timestamp: new Date().toISOString(),
      versions: updatedVersions,
      currentVersionIndex: updatedVersions.length - 1,
    };

    // Rollback messages up to this edited turn
    const priorMessages = messages.slice(0, messageIndex);
    const newHistory = [...priorMessages, updatedUserMsg];

    const assistantMsgId = `ai_${Date.now()}`;
    const initialAssistantMsg: ChatMessage = {
      id: assistantMsgId,
      role: 'assistant',
      content: '',
      status: 'streaming',
      agent_history: [],
      timestamp: new Date().toISOString(),
    };

    setMessages([...newHistory, initialAssistantMsg]);
    setIsLoading(true);
    setErrorMessage(null);

    const backendHistory = newHistory.map((m) => ({
      role: m.role,
      content: m.content,
    }));

    try {
      let currentThread = activeThreadId;

      await streamMessage(
        newContent,
        currentThread,
        (update) => {
          if (update.event === 'started') {
            if (!currentThread && update.thread_id) {
              currentThread = update.thread_id;
              setActiveThreadId(update.thread_id);
            }
          } else if (update.event === 'agent_start' || update.event === 'agent_completed') {
            setMessages((prev) =>
              prev.map((msg) => {
                if (msg.id !== assistantMsgId) return msg;
                return {
                  ...msg,
                  current_agent: update.agent || msg.current_agent,
                  plan: update.plan || msg.plan,
                  agent_history: update.agent_history || msg.agent_history,
                };
              })
            );
          } else if (update.event === 'done') {
            const targetThreadId = update.thread_id || currentThread;
            if (update.thread_id && !currentThread) {
              currentThread = update.thread_id;
              setActiveThreadId(update.thread_id);
            }
            if (update.thread_title && targetThreadId) {
              setThreads((prev) =>
                prev.map((t) =>
                  t.thread_id === targetThreadId ? { ...t, title: update.thread_title! } : t
                )
              );
            }
            setMessages((prev) =>
              prev.map((msg) => {
                if (msg.id !== assistantMsgId) return msg;
                return {
                  ...msg,
                  content: update.response || msg.content,
                  status: 'completed',
                  plan: update.plan || msg.plan,
                  current_agent: update.current_agent || msg.current_agent,
                  agent_history: update.agent_history || msg.agent_history,
                  retrieved_documents: update.retrieved_documents || msg.retrieved_documents,
                  validation_result: update.validation_result || msg.validation_result,
                  pending_action: update.pending_action,
                  confirmation_required: update.confirmation_required,
                };
              })
            );
          }
        },
        undefined,
        backendHistory
      );

      refreshThreads();
    } catch (err: any) {
      console.error('Chat execution failed after edit:', err);
      setErrorMessage(err.message || 'Something went wrong while executing the workflow.');
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMsgId ? { ...msg, status: 'error', error_message: err.message } : msg
        )
      );
    } finally {
      setIsLoading(false);
    }
  };

  // Switch between recorded versions of a message
  const handleSelectMessageVersion = (messageIndex: number, versionIndex: number) => {
    setMessages((prev) =>
      prev.map((msg, idx) => {
        if (idx !== messageIndex) return msg;
        const ver = msg.versions?.[versionIndex];
        if (!ver) return msg;
        return {
          ...msg,
          content: ver.content,
          currentVersionIndex: versionIndex,
        };
      })
    );
  };

  // Human-in-the-loop confirmation handler
  const handleConfirmAction = (approved: boolean) => {
    handleSendMessage(approved ? 'Yes, approve action' : 'No, reject action', approved);
  };

  // Regenerate last assistant response
  const handleRegenerate = () => {
    // Find last user message
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === 'user') {
        const lastUserText = messages[i].content;
        // Truncate messages back to that point
        setMessages((prev) => prev.slice(0, i));
        handleSendMessage(lastUserText);
        break;
      }
    }
  };

  // Retry after error
  const handleRetryLast = () => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === 'user') {
        const lastUserText = messages[i].content;
        setMessages((prev) => prev.slice(0, i));
        handleSendMessage(lastUserText);
        break;
      }
    }
  };

  return (

    <div className="flex h-screen w-screen overflow-hidden bg-white dark:bg-black text-neutral-900 dark:text-neutral-100 font-sans">
      {/* Sidebar (Desktop resizable + Mobile drawer) */}
      <Sidebar
        threads={threads}
        activeThreadId={activeThreadId}
        onNewChat={handleNewChat}
        onSelectThread={handleSelectThread}
        onRenameThread={handleRenameThread}
        onDeleteThread={handleDeleteThread}
        onOpenKnowledgeBase={() => setIsKnowledgeBaseOpen(true)}
        onOpenSettings={() => setIsSettingsOpen(true)}
        isOpenMobile={isMobileSidebarOpen}
        onCloseMobile={() => setIsMobileSidebarOpen(false)}
        isLoadingThreads={isLoadingThreads}
        documentCount={documentCount}
        isOpen={isDrawerOpen}
        onToggle={handleToggleSidebar}
      />

      {/* Main Workspace Column */}
      <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden bg-white dark:bg-black">
        {/* Top Bar with Clickable System Logo to Toggle Sidebar */}
        <TopBar
          onOpenMobileSidebar={() => setIsMobileSidebarOpen(true)}
          onToggleSidebar={handleToggleSidebar}
          onOpenSettings={() => setIsSettingsOpen(true)}
          title="Multi-Agent AI"
        />

        {/* Chat Area */}
        <main className="flex-1 flex flex-col min-w-0 overflow-hidden relative">
          <ChatWindow
            messages={messages}
            isLoading={isLoading}
            onSelectPrompt={(prompt) => handleSendMessage(prompt)}
            onRegenerate={handleRegenerate}
            onConfirmAction={handleConfirmAction}
            onRetryLast={handleRetryLast}
            onEditMessage={handleEditMessage}
            onSelectMessageVersion={handleSelectMessageVersion}
            errorMessage={errorMessage}
          />


          {/* Sticky Input Area */}
          <MessageInput
            onSendMessage={(msg) => handleSendMessage(msg)}
            isLoading={isLoading}
            enterSendsMessage={enterSendsMessage}
            onDocumentUploaded={refreshDocumentsCount}
          />
        </main>
      </div>

      {/* Knowledge Base Modal */}
      <KnowledgeBase
        isOpen={isKnowledgeBaseOpen}
        onClose={() => setIsKnowledgeBaseOpen(false)}
        onDocumentsChanged={refreshDocumentsCount}
      />

      {/* Settings Modal */}
      <Settings
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        enterSendsMessage={enterSendsMessage}
        onToggleEnterSendsMessage={handleToggleEnter}
      />
    </div>
  );
}
