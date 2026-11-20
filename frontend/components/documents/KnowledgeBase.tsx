'use client';

import React, { useEffect, useState } from 'react';
import { X, FileText, Trash2, Database, RefreshCw, Loader2 } from 'lucide-react';
import { DocumentItem } from '@/lib/types';
import { getDocuments, deleteDocument } from '@/lib/api';
import { DocumentUpload } from './DocumentUpload';

interface KnowledgeBaseProps {
  isOpen: boolean;
  onClose: () => void;
  onDocumentsChanged?: () => void;
}

export const KnowledgeBase: React.FC<KnowledgeBaseProps> = ({
  isOpen,
  onClose,
  onDocumentsChanged,
}) => {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [totalChunks, setTotalChunks] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const fetchDocs = async () => {
    setIsLoading(true);
    try {
      const data = await getDocuments();
      setDocuments(data.documents || []);
      setTotalChunks(data.total_chunks || 0);
      if (onDocumentsChanged) {
        onDocumentsChanged();
      }
    } catch (err) {
      console.error('Error fetching documents:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchDocs();
    }
  }, [isOpen]);

  const handleDelete = async (docId: string) => {
    setDeletingId(docId);
    try {
      await deleteDocument(docId);
      await fetchDocs();
    } catch (err) {
      console.error('Error deleting document:', err);
    } finally {
      setDeletingId(null);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-150">
      <div
        className="w-full max-w-lg rounded-2xl border border-neutral-200 dark:border-[#222222] bg-white dark:bg-[#0D0D0D] shadow-2xl overflow-hidden flex flex-col max-h-[85vh]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="p-4 border-b border-neutral-200 dark:border-neutral-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-md bg-neutral-100 dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800">
              <Database className="w-4 h-4 text-neutral-800 dark:text-neutral-200" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">
                Knowledge Base
              </h2>
              <p className="text-[11px] text-neutral-500">
                Manage documents indexed for RAG retrieval
              </p>
            </div>
          </div>

          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={fetchDocs}
              disabled={isLoading}
              title="Refresh documents"
              className="p-1.5 rounded text-neutral-500 hover:text-black dark:hover:text-white transition-colors"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            </button>
            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded text-neutral-500 hover:text-black dark:hover:text-white transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Modal Content */}
        <div className="p-4 overflow-y-auto space-y-4">
          {/* Upload Section */}
          <DocumentUpload onUploadSuccess={fetchDocs} />

          {/* Stats Bar */}
          <div className="flex items-center justify-between text-xs px-1 text-neutral-500">
            <span>Your Documents</span>
            <span className="font-mono text-[11px]">
              {documents.length} docs · {totalChunks} chunks
            </span>
          </div>

          {/* Documents List */}
          <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 divide-y divide-neutral-200 dark:divide-neutral-800/80 bg-white dark:bg-[#111111] overflow-hidden">
            {isLoading && documents.length === 0 ? (
              <div className="p-6 text-center text-xs text-neutral-400">
                <Loader2 className="w-4 h-4 animate-spin mx-auto mb-2 text-neutral-500" />
                Loading documents...
              </div>
            ) : documents.length === 0 ? (
              <div className="p-6 text-center text-xs text-neutral-400 dark:text-neutral-600">
                No documents in knowledge base yet.
              </div>
            ) : (
              documents.map((doc) => (
                <div
                  key={doc.document_id}
                  className="p-3 flex items-center justify-between hover:bg-neutral-50 dark:hover:bg-[#151515] transition-colors"
                >
                  <div className="flex items-center gap-2.5 truncate pr-3">
                    <FileText className="w-4 h-4 text-neutral-500 shrink-0" />
                    <div className="truncate">
                      <div className="text-xs font-medium text-neutral-900 dark:text-neutral-100 truncate">
                        {doc.filename}
                      </div>
                      <div className="text-[11px] text-neutral-400 font-mono mt-0.5">
                        {doc.chunk_count} chunks · Indexed
                      </div>
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={() => handleDelete(doc.document_id)}
                    disabled={deletingId === doc.document_id}
                    title="Delete document"
                    className="p-1.5 text-neutral-400 hover:text-red-500 rounded transition-colors"
                  >
                    {deletingId === doc.document_id ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Trash2 className="w-3.5 h-3.5" />
                    )}
                  </button>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Modal Footer */}
        <div className="p-3 border-t border-neutral-200 dark:border-neutral-800 bg-neutral-50/50 dark:bg-[#0A0A0A] flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-3.5 py-1.5 rounded-lg border border-neutral-300 dark:border-neutral-700 text-xs font-medium text-neutral-700 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
