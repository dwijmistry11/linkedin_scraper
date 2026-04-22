import { create } from 'zustand';
import type { Session, ScrapeJob, AppSettings } from '../types';
import { fetchSessions } from '../api/sessions';
import api from '../api/client';

interface AppState {
  // Sessions
  sessions: Session[];
  activeSessionId: string | null;
  setActiveSession: (id: string | null) => void;
  loadSessions: () => Promise<void>;

  // Active scrape jobs (in-flight)
  activeJobs: Record<string, ScrapeJob>;
  addActiveJob: (job: ScrapeJob) => void;
  updateJobProgress: (jobId: string, percent: number, message: string) => void;
  completeJob: (jobId: string) => void;
  failJob: (jobId: string, error: string) => void;

  // Settings
  settings: AppSettings | null;
  loadSettings: () => Promise<void>;
}

export const useAppStore = create<AppState>((set, get) => ({
  sessions: [],
  activeSessionId: null,

  setActiveSession: (id) => set({ activeSessionId: id }),

  loadSessions: async () => {
    const { data } = await fetchSessions();
    set({ sessions: data });
    // Auto-select first session if none selected
    if (!get().activeSessionId && data.length > 0) {
      set({ activeSessionId: data[0].id });
    }
  },

  activeJobs: {},

  addActiveJob: (job) =>
    set((s) => ({ activeJobs: { ...s.activeJobs, [job.id]: job } })),

  updateJobProgress: (jobId, percent, message) =>
    set((s) => {
      const existing = s.activeJobs[jobId];
      if (!existing) return s;
      return {
        activeJobs: {
          ...s.activeJobs,
          [jobId]: { ...existing, progress_percent: percent, progress_message: message, status: 'running' },
        },
      };
    }),

  completeJob: (jobId) =>
    set((s) => {
      const { [jobId]: _, ...rest } = s.activeJobs;
      return { activeJobs: rest };
    }),

  failJob: (jobId, error) =>
    set((s) => {
      const existing = s.activeJobs[jobId];
      if (!existing) return s;
      return {
        activeJobs: {
          ...s.activeJobs,
          [jobId]: { ...existing, status: 'failed', error_message: error },
        },
      };
    }),

  settings: null,

  loadSettings: async () => {
    const { data } = await api.get<AppSettings>('/settings');
    set({ settings: data });
  },
}));
