import { useEffect } from 'react';
import { Menu, Loader2 } from 'lucide-react';
import { useAppStore } from '../../stores/appStore';

export default function Header({ onMenuClick }: { onMenuClick: () => void }) {
  const { sessions, activeSessionId, setActiveSession, loadSessions, activeJobs } = useAppStore();
  const runningCount = Object.values(activeJobs).filter((j) => j.status === 'running').length;

  useEffect(() => {
    loadSessions();
  }, []);

  return (
    <header className="h-14 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 flex items-center px-4 gap-3 shrink-0">
      <button onClick={onMenuClick} className="lg:hidden p-1 text-gray-500 hover:text-gray-700">
        <Menu size={20} />
      </button>

      <div className="flex-1" />

      {runningCount > 0 && (
        <div className="flex items-center gap-1.5 text-sm text-blue-600 dark:text-blue-400">
          <Loader2 size={16} className="animate-spin" />
          {runningCount} job{runningCount > 1 ? 's' : ''} running
        </div>
      )}

      <select
        value={activeSessionId || ''}
        onChange={(e) => setActiveSession(e.target.value || null)}
        className="text-sm border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-1.5 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300"
      >
        <option value="">No session</option>
        {sessions.map((s) => (
          <option key={s.id} value={s.id}>
            {s.name} {s.is_active ? '' : '(unverified)'}
          </option>
        ))}
      </select>
    </header>
  );
}
