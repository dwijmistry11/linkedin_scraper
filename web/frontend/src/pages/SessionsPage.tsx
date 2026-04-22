import { useEffect, useState } from 'react';
import { Loader2, Plus, Trash2, CheckCircle, XCircle } from 'lucide-react';
import { useAppStore } from '../stores/appStore';
import * as sessionsApi from '../api/sessions';

export default function SessionsPage() {
  const { sessions, loadSessions, activeSessionId, setActiveSession } = useAppStore();
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState('');
  const [cookie, setCookie] = useState('');
  const [creating, setCreating] = useState(false);
  const [verifying, setVerifying] = useState<string | null>(null);

  useEffect(() => {
    loadSessions();
  }, []);

  const handleCreate = async () => {
    if (!name.trim()) return;
    setCreating(true);
    try {
      await sessionsApi.createSession(name.trim(), cookie.trim() || undefined);
      await loadSessions();
      setName('');
      setCookie('');
      setShowCreate(false);
    } catch (e) {
      alert('Failed to create session');
    }
    setCreating(false);
  };

  const [verifyError, setVerifyError] = useState<string | null>(null);

  const handleVerify = async (id: string) => {
    setVerifying(id);
    setVerifyError(null);
    try {
      const { data } = await sessionsApi.verifySession(id);
      await loadSessions();
      if (!data.authenticated) {
        setVerifyError('Session is not authenticated. The cookie may be expired or invalid.');
      }
    } catch (e: any) {
      setVerifyError(e.response?.data?.detail || e.message || 'Verification failed');
    }
    setVerifying(null);
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this session?')) return;
    await sessionsApi.deleteSession(id);
    if (activeSessionId === id) setActiveSession(null);
    await loadSessions();
  };

  return (
    <div className="max-w-3xl space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Sessions</h2>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-lg transition-colors"
        >
          <Plus size={16} /> New Session
        </button>
      </div>

      {verifyError && (
        <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg flex items-start justify-between">
          <p className="text-sm text-red-700 dark:text-red-400">{verifyError}</p>
          <button onClick={() => setVerifyError(null)} className="text-red-400 hover:text-red-600 ml-2 text-xs">dismiss</button>
        </div>
      )}

      {showCreate && (
        <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700 space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Session Name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Work Account"
              className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-800 focus:ring-2 focus:ring-blue-500 outline-none"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              li_at Cookie (optional)
            </label>
            <input
              type="text"
              value={cookie}
              onChange={(e) => setCookie(e.target.value)}
              placeholder="Paste your li_at cookie value"
              className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-800 focus:ring-2 focus:ring-blue-500 outline-none font-mono text-xs"
            />
            <p className="mt-1 text-xs text-gray-400">
              Find this in your browser DevTools under Application &gt; Cookies &gt; linkedin.com &gt; li_at
            </p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleCreate}
              disabled={creating || !name.trim()}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm rounded-lg flex items-center gap-2"
            >
              {creating && <Loader2 size={14} className="animate-spin" />}
              Create
            </button>
            <button
              onClick={() => setShowCreate(false)}
              className="px-4 py-2 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 text-sm rounded-lg"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {sessions.length === 0 ? (
        <p className="text-sm text-gray-400">No sessions yet. Create one to start scraping.</p>
      ) : (
        <div className="space-y-2">
          {sessions.map((s) => (
            <div
              key={s.id}
              className={`bg-white dark:bg-gray-800 rounded-lg p-4 border transition-colors ${
                s.id === activeSessionId
                  ? 'border-blue-400 dark:border-blue-600'
                  : 'border-gray-200 dark:border-gray-700'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setActiveSession(s.id)}
                    className={`text-sm font-medium ${
                      s.id === activeSessionId
                        ? 'text-blue-600 dark:text-blue-400'
                        : 'text-gray-700 dark:text-gray-300 hover:text-blue-600'
                    }`}
                  >
                    {s.name}
                  </button>
                  {s.is_active ? (
                    <CheckCircle size={16} className="text-green-500" />
                  ) : (
                    <XCircle size={16} className="text-gray-400" />
                  )}
                  {s.id === activeSessionId && (
                    <span className="text-xs px-1.5 py-0.5 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 rounded">
                      Active
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleVerify(s.id)}
                    disabled={verifying === s.id}
                    className="text-xs px-2 py-1 text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded flex items-center gap-1"
                  >
                    {verifying === s.id ? <Loader2 size={12} className="animate-spin" /> : null}
                    Verify
                  </button>
                  <button
                    onClick={() => handleDelete(s.id)}
                    className="text-xs p-1 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
              {s.last_verified_at && (
                <p className="text-xs text-gray-400 mt-1">
                  Last verified: {new Date(s.last_verified_at).toLocaleString()}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
