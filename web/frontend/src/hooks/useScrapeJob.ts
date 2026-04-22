import { useState } from 'react';
import { useWebSocket } from './useWebSocket';
import { useAppStore } from '../stores/appStore';
import type { ScrapeJob } from '../types';

export function useScrapeJob() {
  const activeSessionId = useAppStore((s) => s.activeSessionId);
  const addActiveJob = useAppStore((s) => s.addActiveJob);
  const [jobId, setJobId] = useState<string | null>(null);
  const [startError, setStartError] = useState<string | null>(null);
  const ws = useWebSocket(jobId);

  const startScrape = async (
    apiFn: (sessionId: string, ...args: any[]) => Promise<{ data: ScrapeJob }>,
    ...args: any[]
  ) => {
    if (!activeSessionId) {
      setStartError('No session selected. Please create or select a session first.');
      return;
    }
    setStartError(null);
    setJobId(null);
    try {
      const { data } = await apiFn(activeSessionId, ...args);
      addActiveJob(data);
      setJobId(data.id);
    } catch (e: any) {
      setStartError(e.response?.data?.detail || e.message);
    }
  };

  const reset = () => {
    setJobId(null);
    setStartError(null);
  };

  return { startScrape, jobId, startError, reset, ...ws };
}
