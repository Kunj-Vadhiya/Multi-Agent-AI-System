'use client';

import React, { useState } from 'react';
import { ChevronDown, ChevronRight, Check, Loader2, Circle, AlertCircle } from 'lucide-react';
import { AgentHistoryItem } from '@/lib/types';

interface AgentActivityProps {
  status?: string;
  currentAgent?: string;
  plan?: string[];
  agentHistory?: AgentHistoryItem[];
  isStreaming?: boolean;
}

export const AgentActivity: React.FC<AgentActivityProps> = ({
  status,
  currentAgent,
  plan,
  agentHistory = [],
  isStreaming = false,
}) => {
  const [isOpen, setIsOpen] = useState(false);

  // Default agent stages for full lifecycle visibility
  const baseAgents = [
    { key: 'supervisor', label: 'Supervisor', desc: 'Task planned and coordinated' },
    { key: 'research_agent', label: 'Research Agent', desc: 'Retrieved relevant information & tools' },
    { key: 'analysis_agent', label: 'Analysis Agent', desc: 'Analyzed findings & structured data' },
    { key: 'writer_agent', label: 'Writer Agent', desc: 'Synthesized final response' },
    { key: 'validator_agent', label: 'Validator Agent', desc: 'Audited quality and verified output' },
  ];

  // Determine stage status
  const getAgentStatus = (agentKey: string) => {
    // Check if recorded in agentHistory
    const recorded = agentHistory.find(
      (h) => h.agent.toLowerCase() === agentKey.toLowerCase() || h.agent.toLowerCase().includes(agentKey.toLowerCase())
    );
    if (recorded) {
      if (recorded.status === 'completed') return 'completed';
      if (recorded.status === 'failed') return 'failed';
      if (recorded.status === 'running') return 'running';
    }

    if (currentAgent && currentAgent.toLowerCase().includes(agentKey.replace('_agent', ''))) {
      return isStreaming ? 'running' : 'completed';
    }

    if (!isStreaming && status === 'completed') {
      return 'completed';
    }

    return 'pending';
  };

  const getStatusIcon = (st: string) => {
    switch (st) {
      case 'completed':
        return <Check className="w-3.5 h-3.5 text-neutral-800 dark:text-neutral-200" />;
      case 'running':
        return <Loader2 className="w-3.5 h-3.5 animate-spin text-neutral-800 dark:text-neutral-200" />;
      case 'failed':
        return <AlertCircle className="w-3.5 h-3.5 text-red-500" />;
      default:
        return <Circle className="w-3.5 h-3.5 text-neutral-400 dark:text-neutral-600" />;
    }
  };

  const completedCount = baseAgents.filter((a) => getAgentStatus(a.key) === 'completed').length;
  const isWorkflowActive = isStreaming && status !== 'completed';

  return (
    <div className="my-2 border border-neutral-200 dark:border-neutral-800 rounded-lg bg-neutral-50 dark:bg-neutral-950/40 text-xs overflow-hidden transition-all">
      {/* Header bar: minimal and clickable */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-3 py-2 flex items-center justify-between hover:bg-neutral-100 dark:hover:bg-neutral-900 transition-colors text-left"
        aria-expanded={isOpen}
      >
        <div className="flex items-center gap-2">
          {isWorkflowActive ? (
            <span className="flex h-2 w-2 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-neutral-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-neutral-800 dark:bg-neutral-200"></span>
            </span>
          ) : (
            <Check className="w-3.5 h-3.5 text-neutral-700 dark:text-neutral-300" />
          )}

          <span className="font-semibold text-black dark:text-neutral-200">
            {isWorkflowActive ? 'Agent Activity in Progress...' : 'Agent Workflow Completed'}
          </span>

          <span className="text-[11px] text-neutral-700 dark:text-neutral-400 font-mono font-medium">
            ({completedCount}/{baseAgents.length})
          </span>
        </div>

        <div className="flex items-center gap-1.5 text-neutral-700 dark:text-neutral-400 text-[11px] font-medium">
          <span>{isOpen ? 'Hide details' : 'View details'}</span>
          {isOpen ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
        </div>
      </button>

      {/* Expanded high-level steps (Concise, no chain of thought) */}
      {isOpen && (
        <div className="px-3 pb-3 pt-1 border-t border-neutral-300 dark:border-neutral-800/60 divide-y divide-neutral-200 dark:divide-neutral-900">
          {baseAgents.map((agent) => {
            const st = getAgentStatus(agent.key);
            return (
              <div key={agent.key} className="py-2 flex items-start gap-2.5">
                <div className="mt-0.5">{getStatusIcon(st)}</div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <span
                      className={`font-semibold ${
                        st === 'completed'
                          ? 'text-black dark:text-neutral-100'
                          : st === 'running'
                          ? 'text-black dark:text-white font-bold'
                          : 'text-neutral-600 dark:text-neutral-400'
                      }`}
                    >
                      {agent.label}
                    </span>
                    <span className="text-[10px] uppercase tracking-wider text-neutral-700 dark:text-neutral-400 font-mono font-bold">
                      {st}
                    </span>
                  </div>
                  <p className="text-[11px] text-neutral-900 dark:text-neutral-300 mt-0.5">
                    {st === 'running' ? 'Active step in execution...' : agent.desc}
                  </p>
                </div>
              </div>
            );
          })}

          {/* Subtask plan if available from Supervisor */}
          {plan && plan.length > 0 && (
            <div className="pt-2 mt-1">
              <span className="font-bold text-black dark:text-neutral-200 block text-[11px] mb-1">
                Execution Plan
              </span>
              <ul className="space-y-1 pl-4 list-disc text-neutral-900 dark:text-neutral-300 text-[11px]">
                {plan.map((item, idx) => (
                  <li key={idx} className="leading-snug">{item}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
