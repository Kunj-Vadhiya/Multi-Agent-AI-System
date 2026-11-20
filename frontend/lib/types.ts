export interface ThreadSummary {
  thread_id: string;
  title: string;
  message_count: number;
  updated_at?: string;
  current_agent?: string | null;
  workflow_status?: string;
}

export interface MessageVersion {
  version: number;
  content: string;
  timestamp: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp?: string;
  versions?: MessageVersion[];
  currentVersionIndex?: number;
  plan?: string[];
  current_agent?: string;
  agent_history?: AgentHistoryItem[];
  retrieved_documents?: RetrievedDocument[];
  validation_result?: ValidationResult;
  pending_action?: PendingAction;
  confirmation_required?: boolean;
  code_results?: Record<string, any>;
  database_results?: Record<string, any>;
  document_results?: Record<string, any>;
  email_results?: Record<string, any>;
  calendar_results?: Record<string, any>;
  status?: 'sending' | 'streaming' | 'completed' | 'error';
  error_message?: string;
}

export interface AgentHistoryItem {
  agent: string;
  status: 'running' | 'completed' | 'failed' | 'pending';
  summary?: string;
  detail?: string;
  timestamp?: string;
}

export interface RetrievedDocument {
  document_id?: string;
  filename: string;
  chunk_id?: number;
  page?: number;
  score?: number;
  snippet?: string;
  metadata?: Record<string, any>;
}

export interface ValidationResult {
  status: 'PASS' | 'FAIL' | string;
  issues?: string[];
  feedback?: string;
}

export interface PendingAction {
  action: string;
  recipient?: string;
  subject?: string;
  title?: string;
  date?: string;
  time?: string;
  details?: Record<string, any>;
}

export interface DocumentItem {
  document_id: string;
  filename: string;
  chunk_count: number;
  uploaded_at?: string;
}

export interface DocumentUploadResponse {
  document_id: string;
  filename: string;
  chunks_created: number;
  status: string;
}

export interface AppSettings {
  theme: 'light' | 'dark';
  enterSendsMessage: boolean;
  apiUrl: string;
}
