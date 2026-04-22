import { useEffect, useRef, useState, useCallback } from 'react';
import { useAppStore } from '../stores/appStore';
import { getScrapeJob } from '../api/scrape';

interface WSProgress {
  percent: number;
  message: string;
}

export function useWebSocket(jobId: string | null) {
  const [status, setStatus] = useState<'connecting' | 'open' | 'closed'>('closed');
  const [progress, setProgress] = useState<WSProgress>({ percent: 0, message: '' });
  const [completed, setCompleted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const doneRef = useRef(false);
  const { updateJobProgress, completeJob, failJob } = useAppStore();

  // Polling fallback: check job status via REST if WS isn't delivering
  const startPolling = useCallback(
    (id: string) => {
      if (pollRef.current) return;
      pollRef.current = setInterval(async () => {
        if (doneRef.current) {
          if (pollRef.current) clearInterval(pollRef.current);
          return;
        }
        try {
          const { data: job } = await getScrapeJob(id);
          setProgress({ percent: job.progress_percent, message: job.progress_message || '' });
          if (job.status === 'completed') {
            doneRef.current = true;
            setCompleted(true);
            completeJob(id);
            if (pollRef.current) clearInterval(pollRef.current);
          } else if (job.status === 'failed') {
            doneRef.current = true;
            setError(job.error_message || 'Scraping failed');
            failJob(id, job.error_message || 'Scraping failed');
            if (pollRef.current) clearInterval(pollRef.current);
          }
        } catch {
          // Ignore poll errors
        }
      }, 3000);
    },
    [completeJob, failJob],
  );

  useEffect(() => {
    if (!jobId) return;

    doneRef.current = false;
    setStatus('connecting');
    setCompleted(false);
    setError(null);
    setProgress({ percent: 0, message: 'Starting...' });

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${window.location.host}/api/scrape/ws/${jobId}`);
    wsRef.current = ws;

    ws.onopen = () => {
      setStatus('open');
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      switch (data.event) {
        case 'start':
          setProgress({ percent: 0, message: `Starting ${data.scraper_type}...` });
          break;
        case 'progress':
          setProgress({ percent: data.percent, message: data.message });
          updateJobProgress(jobId, data.percent, data.message);
          break;
        case 'complete':
          doneRef.current = true;
          setCompleted(true);
          completeJob(jobId);
          break;
        case 'error':
          doneRef.current = true;
          setError(data.message);
          failJob(jobId, data.message);
          break;
      }
    };

    ws.onclose = () => {
      setStatus('closed');
      // If job isn't done yet, start polling as fallback
      if (!doneRef.current) {
        startPolling(jobId);
      }
    };

    ws.onerror = () => {
      // WebSocket failed to connect — fall back to polling immediately
      if (!doneRef.current) {
        startPolling(jobId);
      }
    };

    // Also start polling after a short delay as a safety net
    // (covers the race where the task completes before WS connects)
    const safetyTimeout = setTimeout(() => {
      if (!doneRef.current) {
        startPolling(jobId);
      }
    }, 5000);

    return () => {
      ws.close();
      wsRef.current = null;
      clearTimeout(safetyTimeout);
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [jobId]);

  return { status, progress, completed, error };
}
