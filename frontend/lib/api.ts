import {
  ChatMessage,
  DocumentItem,
  DocumentUploadResponse,
  ThreadSummary,
} from './types';

// Default API base URL from env or fallback to local FastAPI instance
const DEFAULT_API_URL =
  process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export function getApiBaseUrl(): string {
  if (typeof window !== 'undefined') {
    const saved = localStorage.getItem('multiagent_api_url');
    if (saved && saved.trim()) {
      return saved.trim().replace(/\/+$/, '');
    }
  }
  return DEFAULT_API_URL.replace(/\/+$/, '');
}

export function setApiBaseUrl(url: string): void {
  if (typeof window !== 'undefined') {
    localStorage.setItem('multiagent_api_url', url.trim().replace(/\/+$/, ''));
  }
}

/**
 * Health check endpoint
 */
export async function checkHealth(): Promise<{ status: string }> {
  const baseUrl = getApiBaseUrl();
  const response = await fetch(`${baseUrl}/health`, {
    headers: { Accept: 'application/json' },
  });
  if (!response.ok) {
    throw new Error(`API health check failed with status: ${response.status}`);
  }
  return response.json();
}

/**
 * List all persistent threads from FastAPI backend
 */
export async function getThreads(): Promise<ThreadSummary[]> {
  const baseUrl = getApiBaseUrl();
  const response = await fetch(`${baseUrl}/threads`, {
    headers: { Accept: 'application/json' },
  });
  if (!response.ok) {
    throw new Error(`Failed to fetch threads: ${response.statusText}`);
  }
  const data = await response.json();
  return data.threads || [];
}

/**
 * Create a new thread
 */
export async function createThread(title?: string): Promise<{ thread_id: string; title: string }> {
  const baseUrl = getApiBaseUrl();
  const response = await fetch(`${baseUrl}/threads`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify({ title: title || 'New Conversation' }),
  });
  if (!response.ok) {
    throw new Error(`Failed to create thread: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Retrieve messages and state for a specific thread
 */
export async function getThread(threadId: string): Promise<{
  thread_id: string;
  messages: Array<{ role: 'user' | 'assistant' | 'system'; content: string }>;
  plan?: string[];
  current_agent?: string;
  agent_history?: any[];
  retrieved_documents?: any[];
  validation_result?: any;
  pending_action?: any;
  confirmation_required?: boolean;
  workflow_status?: string;
}> {
  const baseUrl = getApiBaseUrl();
  const response = await fetch(`${baseUrl}/threads/${encodeURIComponent(threadId)}`, {
    headers: { Accept: 'application/json' },
  });
  if (!response.ok) {
    throw new Error(`Failed to fetch thread ${threadId}: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Rename a thread title
 */
export async function renameThread(
  threadId: string,
  title: string
): Promise<{ status: string; thread_id: string; title: string }> {
  const baseUrl = getApiBaseUrl();
  const response = await fetch(`${baseUrl}/threads/${encodeURIComponent(threadId)}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify({ title }),
  });
  if (!response.ok) {
    throw new Error(`Failed to rename thread: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Delete a thread and its checkpoints
 */
export async function deleteThread(threadId: string): Promise<{ status: string; thread_id: string }> {
  const baseUrl = getApiBaseUrl();
  const response = await fetch(`${baseUrl}/threads/${encodeURIComponent(threadId)}`, {
    method: 'DELETE',
    headers: { Accept: 'application/json' },
  });
  if (!response.ok) {
    throw new Error(`Failed to delete thread: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Send a chat message synchronously
 */
export async function sendMessage(
  message: string,
  threadId?: string,
  confirmAction?: boolean,
  historyMessages?: Array<{ role: string; content: string }>
): Promise<{
  thread_id: string;
  thread_title?: string;
  response: string;
  status: string;
  plan?: string[];
  current_agent?: string;
  agent_history?: any[];
  retrieved_documents?: any[];
  validation_result?: any;
  pending_action?: any;
  confirmation_required?: boolean;
  agent_logs?: any[];
}> {
  const baseUrl = getApiBaseUrl();
  const payload: Record<string, any> = { message };
  if (threadId) payload.thread_id = threadId;
  if (confirmAction !== undefined) payload.confirm_action = confirmAction;
  if (historyMessages && historyMessages.length > 0) payload.messages = historyMessages;

  const response = await fetch(`${baseUrl}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorBody = await response.text();
    let message = 'An error occurred during agent execution.';
    try {
      const parsed = JSON.parse(errorBody);
      if (parsed.detail) message = parsed.detail;
    } catch {}
    throw new Error(message);
  }

  return response.json();
}

/**
 * Stream a chat message using Server-Sent Events (SSE)
 */
export async function streamMessage(
  message: string,
  threadId: string | undefined,
  onUpdate: (data: {
    event: string;
    thread_id?: string;
    thread_title?: string;
    agent?: string;
    current_agent?: string;
    status?: string;
    plan?: string[];
    response?: string;
    retrieved_documents?: any[];
    validation_result?: any;
    pending_action?: any;
    confirmation_required?: boolean;
    agent_history?: any[];
  }) => void,
  confirmAction?: boolean,
  historyMessages?: Array<{ role: string; content: string }>
): Promise<any> {
  const baseUrl = getApiBaseUrl();
  const payload: Record<string, any> = { message };
  if (threadId) payload.thread_id = threadId;
  if (confirmAction !== undefined) payload.confirm_action = confirmAction;
  if (historyMessages && historyMessages.length > 0) payload.messages = historyMessages;

  const response = await fetch(`${baseUrl}/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok || !response.body) {
    // If stream endpoint fails or is unsupported, fallback cleanly to standard POST /chat
    const standardRes = await sendMessage(message, threadId, confirmAction, historyMessages);

    onUpdate({
      event: 'done',
      thread_title: standardRes.thread_title,
      response: standardRes.response,
      status: standardRes.status,
      plan: standardRes.plan,
      current_agent: standardRes.current_agent,
      agent_history: standardRes.agent_history,
      retrieved_documents: standardRes.retrieved_documents,
      validation_result: standardRes.validation_result,
      pending_action: standardRes.pending_action,
      confirmation_required: standardRes.confirmation_required,
    });
    return standardRes;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';
  let finalResult: any = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const lines = buffer.split('\n\n');
    buffer = lines.pop() || '';

    for (const chunk of lines) {
      const trimmed = chunk.trim();
      if (!trimmed.startsWith('data:')) continue;
      const dataStr = trimmed.replace(/^data:\s*/, '');
      if (dataStr === '[DONE]') continue;

      try {
        const parsed = JSON.parse(dataStr);
        onUpdate(parsed);
        if (parsed.event === 'done') {
          finalResult = parsed;
        }
      } catch (err) {
        console.warn('Failed to parse SSE line:', dataStr, err);
      }
    }
  }

  return finalResult;
}

/**
 * List all indexed documents in the RAG Knowledge Base
 */
export async function getDocuments(): Promise<{
  total_documents: number;
  total_chunks: number;
  documents: DocumentItem[];
}> {
  const baseUrl = getApiBaseUrl();
  const response = await fetch(`${baseUrl}/documents`, {
    headers: { Accept: 'application/json' },
  });
  if (!response.ok) {
    throw new Error(`Failed to fetch documents: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Upload a document (.pdf, .txt, .md) to RAG Knowledge Base
 */
export async function uploadDocument(file: File): Promise<DocumentUploadResponse> {
  const baseUrl = getApiBaseUrl();
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${baseUrl}/documents/upload`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const errorBody = await response.text();
    let msg = 'Failed to upload document.';
    try {
      const parsed = JSON.parse(errorBody);
      if (parsed.detail) msg = parsed.detail;
    } catch {}
    throw new Error(msg);
  }

  return response.json();
}

/**
 * Delete a document from the RAG Knowledge Base
 */
export async function deleteDocument(
  documentId: string
): Promise<{ status: string; document_id: string; deleted_chunks: number }> {
  const baseUrl = getApiBaseUrl();
  const response = await fetch(`${baseUrl}/documents/${encodeURIComponent(documentId)}`, {
    method: 'DELETE',
    headers: { Accept: 'application/json' },
  });
  if (!response.ok) {
    throw new Error(`Failed to delete document: ${response.statusText}`);
  }
  return response.json();
}
