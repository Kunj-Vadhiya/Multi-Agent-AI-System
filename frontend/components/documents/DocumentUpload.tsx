'use client';

import React, { useState, useRef } from 'react';
import { UploadCloud, Check, Loader2, AlertCircle } from 'lucide-react';
import { uploadDocument } from '@/lib/api';

interface DocumentUploadProps {
  onUploadSuccess: () => void;
}

export const DocumentUpload: React.FC<DocumentUploadProps> = ({ onUploadSuccess }) => {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) {
      await processUpload(file);
    }
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      await processUpload(file);
    }
  };

  const processUpload = async (file: File) => {
    const allowed = ['.pdf', '.txt', '.text', '.md', '.markdown'];
    const ext = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!allowed.includes(ext)) {
      setErrorMessage(`Unsupported format '${ext}'. Allowed: .pdf, .txt, .md`);
      return;
    }

    setIsUploading(true);
    setErrorMessage(null);
    setStatusMessage('Uploading and extracting text...');

    try {
      setTimeout(() => setStatusMessage('Chunking text & computing embeddings...'), 500);
      const res = await uploadDocument(file);
      setStatusMessage(`Indexed ${res.chunks_created} chunks into RAG store.`);
      setTimeout(() => {
        setStatusMessage(null);
        setIsUploading(false);
        onUploadSuccess();
      }, 1200);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to upload document');
      setIsUploading(false);
    } finally {
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  return (
    <div className="w-full">
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileChange}
        accept=".pdf,.txt,.text,.md,.markdown"
        className="hidden"
      />

      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => !isUploading && fileInputRef.current?.click()}
        className={`border-2 border-dashed rounded-xl p-5 text-center cursor-pointer transition-all ${
          isDragging
            ? 'border-black dark:border-white bg-neutral-100 dark:bg-neutral-900'
            : 'border-neutral-300 dark:border-neutral-800 hover:border-neutral-400 dark:hover:border-neutral-700 bg-neutral-50/50 dark:bg-[#0A0A0A]'
        }`}
      >
        <div className="flex flex-col items-center justify-center space-y-2">
          {isUploading ? (
            <Loader2 className="w-6 h-6 animate-spin text-neutral-800 dark:text-neutral-200" />
          ) : (
            <UploadCloud className="w-6 h-6 text-neutral-500" />
          )}

          <div className="text-xs">
            <span className="font-semibold text-neutral-900 dark:text-neutral-100">
              Click to upload
            </span>{' '}
            <span className="text-neutral-500">or drag and drop</span>
          </div>

          <p className="text-[11px] text-neutral-400 dark:text-neutral-500">
            PDF, TXT, or Markdown documents (vectorized for RAG)
          </p>
        </div>
      </div>

      {statusMessage && (
        <div className="mt-2.5 p-2 rounded bg-neutral-100 dark:bg-[#151515] text-xs text-neutral-700 dark:text-neutral-300 flex items-center gap-2">
          <Check className="w-3.5 h-3.5 text-neutral-900 dark:text-white" />
          <span>{statusMessage}</span>
        </div>
      )}

      {errorMessage && (
        <div className="mt-2.5 p-2 rounded bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 text-xs text-red-600 dark:text-red-400 flex items-center gap-2">
          <AlertCircle className="w-3.5 h-3.5" />
          <span>{errorMessage}</span>
        </div>
      )}
    </div>
  );
};
