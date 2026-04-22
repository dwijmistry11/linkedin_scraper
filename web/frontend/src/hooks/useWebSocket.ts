import { useEffect, useRef, useState } from 'react';
import { useAppStore } from '../stores/appStore';

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
  const { updateJobProgress, completeJob, failJob } = useAppStore();

  useEffect(() => {
    if (!jobId) return;

    setStatus('connecting');
    setCompleted(false);
    setError(null);
    setProgress({ percent: 0, message: '' });

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${window.location.host}/api/ws/scrape/${jobId}`);
    wsRef.current = ws;

    ws.onopen = () => setStatus('open');

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      switch (data.event) {
        case 'progress':
          setProgress({ percent: data.percent, message: data.message });
          updateJobProgress(jobId, data.percent, data.message);
          break;
        case 'complete':
          setCompleted(true);
          completeJob(jobId);
          break;
        case 'error':
          setError(data.message);
          failJob(jobId, data.message);
          break;
      }
    };

    ws.onclose = () => setStatus('closed');

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [jobId]);

  return { status, progress, completed, error };
}
