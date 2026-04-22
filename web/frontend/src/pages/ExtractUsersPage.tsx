import { useState, useEffect } from 'react';
import { Loader2 } from 'lucide-react';
import ProgressPanel from '../components/scrape/ProgressPanel';
import UsersTable from '../components/results/UsersTable';
import { useWebSocket } from '../hooks/useWebSocket';
import { useAppStore } from '../stores/appStore';
import { extractUsers, getScrapeResult } from '../api/scrape';
import type { ExtractUsersResult, ScrapeJob } from '../types';

export default function ExtractUsersPage() {
  const { sessions, loadSessions } = useAppStore();
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [url, setUrl] = useState('');
  const [postsLimit, setPostsLimit] = useState(5);
  const [scrapeProfiles, setScrapeProfiles] = useState(false);

  const [jobId, setJobId] = useState<string | null>(null);
  const [startError, setStartError] = useState<string | null>(null);
  const ws = useWebSocket(jobId);
  const isRunning = !!jobId && !ws.completed && !ws.error;

  const [result, setResult] = useState<ExtractUsersResult | null>(null);
  const [resultError, setResultError] = useState<string | null>(null);

  useEffect(() => {
    loadSessions();
  }, []);

  useEffect(() => {
    if (jobId && ws.completed) {
      getScrapeResult(jobId)
        .then(({ data }) => setResult(data.result_data as unknown as ExtractUsersResult))
        .catch((e) => setResultError(e.response?.data?.detail || 'Failed to load result'));
    }
  }, [jobId, ws.completed]);

  const toggleSession = (id: string) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id]
    );
  };

  const handleSubmit = async () => {
    if (!url.trim() || selectedIds.length === 0) return;
    setResult(null);
    setResultError(null);
    setStartError(null);
    setJobId(null);
    try {
      const { data } = await extractUsers(selectedIds, url.trim(), postsLimit, scrapeProfiles);
      setJobId(data.id);
    } catch (e: any) {
      setStartError(e.response?.data?.detail || e.message);
    }
  };

  return (
    <div className="max-w-4xl space-y-4">
      <h2 className="text-2xl font-bold">Extract Users from Posts</h2>
      <p className="text-sm text-gray-500 dark:text-gray-400">
        Scrape a company's posts, then extract users who reacted and reposted.
        Select multiple sessions to rotate between them and avoid rate limits.
      </p>

      <div className="bg-white dark:bg-gray-800 rounded-lg p-5 border border-gray-200 dark:border-gray-700 space-y-4">
        {/* Session multi-select */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Sessions to use
            <span className="ml-1 text-xs font-normal text-gray-400">
              (select multiple to rotate and avoid rate limits)
            </span>
          </label>
          {sessions.length === 0 ? (
            <p className="text-sm text-gray-400">No sessions available. Create one first.</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {sessions.map((s) => {
                const selected = selectedIds.includes(s.id);
                return (
                  <button
                    key={s.id}
                    type="button"
                    onClick={() => toggleSession(s.id)}
                    className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${
                      selected
                        ? 'bg-blue-600 border-blue-600 text-white'
                        : 'bg-white dark:bg-gray-800 border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-400 hover:border-blue-400'
                    }`}
                  >
                    {s.name}
                    {s.is_active && <span className="ml-1 text-xs opacity-70">(verified)</span>}
                  </button>
                );
              })}
            </div>
          )}
          {selectedIds.length > 1 && (
            <p className="text-xs text-green-600 dark:text-green-400 mt-1">
              {selectedIds.length} sessions selected — will rotate between them
            </p>
          )}
        </div>

        {/* Company URL */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Company / Showcase Page URL
          </label>
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://www.linkedin.com/company/microsoft/"
            required
            className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-800 focus:ring-2 focus:ring-blue-500 outline-none"
          />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Posts to process
            </label>
            <input
              type="number"
              value={postsLimit}
              onChange={(e) => setPostsLimit(Number(e.target.value))}
              min={1}
              max={50}
              className="w-32 border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-800 focus:ring-2 focus:ring-blue-500 outline-none"
            />
          </div>

          <div className="flex items-center gap-3 pt-5">
            <button
              type="button"
              onClick={() => setScrapeProfiles(!scrapeProfiles)}
              className={`w-10 h-6 rounded-full transition-colors ${
                scrapeProfiles ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600'
              }`}
            >
              <div
                className={`w-4 h-4 bg-white rounded-full transition-transform mx-1 ${
                  scrapeProfiles ? 'translate-x-4' : ''
                }`}
              />
            </button>
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Scrape full profiles
              </p>
              <p className="text-xs text-gray-400">Slower — scrapes each user's LinkedIn profile</p>
            </div>
          </div>
        </div>

        <button
          onClick={handleSubmit}
          disabled={isRunning || selectedIds.length === 0 || !url.trim()}
          className="px-5 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg flex items-center gap-2 transition-colors"
        >
          {isRunning && <Loader2 size={16} className="animate-spin" />}
          Extract Users
        </button>
      </div>

      {startError && <p className="text-sm text-red-500">{startError}</p>}

      {jobId && (
        <ProgressPanel
          percent={ws.progress.percent}
          message={ws.progress.message}
          error={ws.error}
          completed={ws.completed}
        />
      )}

      {resultError && <p className="text-sm text-red-500">{resultError}</p>}
      {result && <UsersTable data={result} />}
    </div>
  );
}
