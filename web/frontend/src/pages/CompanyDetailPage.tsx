import { useEffect, useState, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, Play, Pause, RotateCcw, Loader2, ExternalLink } from 'lucide-react';
import { getCompany, getCompanyPosts, getCompanyUsers, getCompanyRuns, startScrape, pauseScrape, resumeScrape, getScrapeRun } from '../api/companies';
import { useAppStore } from '../stores/appStore';
import type { CRMCompany, ScrapeRun, CompanyPost, DiscoveredUser } from '../types';
import { getLinkedInUrl, getDisplayName } from '../types';

type Tab = 'overview' | 'posts' | 'users' | 'runs';

export default function CompanyDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { sessions, loadSessions } = useAppStore();
  const [company, setCompany] = useState<CRMCompany | null>(null);
  const [posts, setPosts] = useState<CompanyPost[]>([]);
  const [users, setUsers] = useState<DiscoveredUser[]>([]);
  const [runs, setRuns] = useState<ScrapeRun[]>([]);
  const [tab, setTab] = useState<Tab>('overview');
  const [selectedSessions, setSelectedSessions] = useState<string[]>([]);
  const [activeRun, setActiveRun] = useState<ScrapeRun | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { loadSessions(); }, []);

  const loadData = useCallback(async () => {
    if (!id) return;
    try {
      const [compRes, postRes, userRes, runRes] = await Promise.all([
        getCompany(id), getCompanyPosts(id), getCompanyUsers(id), getCompanyRuns(id),
      ]);
      setCompany(compRes.data.company);
      setPosts(postRes.data.posts || []);
      setUsers(userRes.data.users || []);
      const allRuns = (runRes.data.runs || []) as ScrapeRun[];
      setRuns(allRuns);
      const running = allRuns.find((r: ScrapeRun) => r.status === 'running' || r.status === 'paused');
      setActiveRun(running || null);
    } catch {}
  }, [id]);

  useEffect(() => { loadData(); }, [loadData]);

  // Poll active run for progress
  useEffect(() => {
    if (!activeRun || activeRun.status === 'completed' || activeRun.status === 'failed') return;
    const interval = setInterval(async () => {
      try {
        const { data } = await getScrapeRun(activeRun.id);
        const run = data.run as ScrapeRun;
        setActiveRun(run);
        if (run.status === 'completed' || run.status === 'failed') {
          loadData();
        }
      } catch {}
    }, 3000);
    return () => clearInterval(interval);
  }, [activeRun?.id, activeRun?.status]);

  const handleStart = async () => {
    if (!id || selectedSessions.length === 0) return;
    setError(null);
    try {
      const { data } = await startScrape(id, selectedSessions);
      setActiveRun(data.run);
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Failed to start scrape');
    }
  };

  const handlePause = async () => {
    if (!activeRun) return;
    try { await pauseScrape(activeRun.id); setActiveRun({ ...activeRun, status: 'paused' }); } catch {}
  };

  const handleResume = async () => {
    if (!activeRun || selectedSessions.length === 0) return;
    try { await resumeScrape(activeRun.id, selectedSessions); setActiveRun({ ...activeRun, status: 'running' }); } catch {}
  };

  const toggleSession = (sid: string) => {
    setSelectedSessions((prev) => prev.includes(sid) ? prev.filter((s) => s !== sid) : [...prev, sid]);
  };

  if (!id) return null;
  const companyUrl = company ? getLinkedInUrl(company.linkedinUrl) : '';

  return (
    <div className="max-w-5xl space-y-4">
      <Link to="/companies" className="flex items-center gap-1 text-sm text-blue-600 dark:text-blue-400 hover:underline">
        <ArrowLeft size={14} /> Back to Companies
      </Link>

      {/* Header */}
      {company && (
        <div className="bg-white dark:bg-gray-800 rounded-lg p-5 border border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-bold">{company.name || 'Company'}</h2>
              {companyUrl && (
                <a href={companyUrl} target="_blank" rel="noopener noreferrer" className="text-sm text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1">
                  {companyUrl} <ExternalLink size={12} />
                </a>
              )}
            </div>
            <div className="text-right text-sm text-gray-400">
              <p>Posts: {posts.length}</p>
              <p>Users: {users.length}</p>
              <p>Runs: {runs.length}</p>
            </div>
          </div>
        </div>
      )}

      {/* Scrape Controls */}
      <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700 space-y-3">
        <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">Scrape Controls</h3>

        {/* Session picker */}
        <div>
          <p className="text-xs text-gray-400 mb-2">Select sessions to use:</p>
          <div className="flex flex-wrap gap-2">
            {sessions.map((s) => (
              <button
                key={s.id}
                onClick={() => toggleSession(s.id)}
                className={`px-3 py-1.5 text-xs rounded-lg border transition-colors ${
                  selectedSessions.includes(s.id)
                    ? 'bg-blue-600 border-blue-600 text-white'
                    : 'bg-white dark:bg-gray-800 border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-400'
                }`}
              >
                {s.name}
              </button>
            ))}
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-3">
          {(!activeRun || activeRun.status === 'completed' || activeRun.status === 'failed') && (
            <button onClick={handleStart} disabled={selectedSessions.length === 0} className="px-4 py-2 bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white text-sm rounded-lg flex items-center gap-2">
              <Play size={14} /> Start Scraping
            </button>
          )}
          {activeRun?.status === 'running' && (
            <button onClick={handlePause} className="px-4 py-2 bg-yellow-600 hover:bg-yellow-700 text-white text-sm rounded-lg flex items-center gap-2">
              <Pause size={14} /> Pause
            </button>
          )}
          {activeRun?.status === 'paused' && (
            <button onClick={handleResume} disabled={selectedSessions.length === 0} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm rounded-lg flex items-center gap-2">
              <RotateCcw size={14} /> Resume
            </button>
          )}
        </div>
        {error && <p className="text-sm text-red-500">{error}</p>}

        {/* Live progress */}
        {activeRun && activeRun.status !== 'completed' && activeRun.status !== 'failed' && (
          <div className="space-y-2 pt-2">
            <div className="flex justify-between text-sm">
              <span className="text-gray-500">
                {activeRun.status === 'paused' ? 'Paused' : activeRun.progressMessage || activeRun.phase || 'Starting...'}
              </span>
              <span className="text-gray-400">{activeRun.progressPercent || 0}%</span>
            </div>
            <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
              <div className={`h-2 rounded-full transition-all duration-500 ${activeRun.status === 'paused' ? 'bg-yellow-500' : 'bg-blue-600'}`} style={{ width: `${activeRun.progressPercent || 0}%` }} />
            </div>
            <div className="grid grid-cols-4 gap-2 text-xs text-gray-400">
              <span>Posts: {activeRun.postsProcessed || 0}/{activeRun.totalPostsFound || '?'}</span>
              <span>Users: {activeRun.totalUsersFound || 0}</span>
              <span>Profiles: {activeRun.profilesScraped || 0}/{activeRun.profilesToScrape || '?'}</span>
              <span>Phase: {activeRun.phase}</span>
            </div>
          </div>
        )}

        {activeRun?.status === 'completed' && (
          <p className="text-sm text-green-600">Last run completed. Posts: {activeRun.totalPostsFound}, Users: {activeRun.totalUsersFound}, Profiles: {activeRun.profilesScraped}</p>
        )}
        {activeRun?.status === 'failed' && (
          <p className="text-sm text-red-500">Last run failed: {activeRun.errorMessage}</p>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-200 dark:border-gray-700">
        {(['overview', 'posts', 'users', 'runs'] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm capitalize transition-colors ${
              tab === t
                ? 'border-b-2 border-blue-600 text-blue-600 font-medium'
                : 'text-gray-400 hover:text-gray-600'
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === 'overview' && (
        <div className="grid grid-cols-3 gap-3">
          <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700 text-center">
            <p className="text-3xl font-bold text-blue-600">{posts.length}</p>
            <p className="text-xs text-gray-500 mt-1">Posts Found</p>
          </div>
          <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700 text-center">
            <p className="text-3xl font-bold text-green-600">{users.length}</p>
            <p className="text-xs text-gray-500 mt-1">Users Discovered</p>
          </div>
          <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700 text-center">
            <p className="text-3xl font-bold text-purple-600">{users.filter(u => u.profileScrapedAt).length}</p>
            <p className="text-xs text-gray-500 mt-1">Profiles Scraped</p>
          </div>
        </div>
      )}

      {tab === 'posts' && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 dark:border-gray-700 text-left text-gray-500">
                <th className="pb-2 font-medium">Post</th>
                <th className="pb-2 font-medium">Reactions</th>
                <th className="pb-2 font-medium">Comments</th>
                <th className="pb-2 font-medium">Reposts</th>
                <th className="pb-2 font-medium">Last Scraped</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
              {posts.map((p) => (
                <tr key={p.id}>
                  <td className="py-2 max-w-xs truncate">{p.postText || p.urn}</td>
                  <td className="py-2">{p.reactionsCount ?? '-'}</td>
                  <td className="py-2">{p.commentsCount ?? '-'}</td>
                  <td className="py-2">{p.repostsCount ?? '-'}</td>
                  <td className="py-2 text-xs text-gray-400">{p.lastScrapedAt ? new Date(p.lastScrapedAt).toLocaleDateString() : 'Never'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {posts.length === 0 && <p className="text-sm text-gray-400 text-center py-4">No posts yet. Start a scrape to discover posts.</p>}
        </div>
      )}

      {tab === 'users' && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 dark:border-gray-700 text-left text-gray-500">
                <th className="pb-2 font-medium">Name</th>
                <th className="pb-2 font-medium">Title</th>
                <th className="pb-2 font-medium">Profile</th>
                <th className="pb-2 font-medium">Profile Scraped</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
              {users.map((u) => (
                <tr key={u.id}>
                  <td className="py-2 font-medium">{getDisplayName(u.name)}</td>
                  <td className="py-2 text-gray-500 max-w-xs truncate">{u.jobTitle || '-'}</td>
                  <td className="py-2">
                    {getLinkedInUrl(u.linkedinUrl) ? (
                      <a href={getLinkedInUrl(u.linkedinUrl)} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline text-xs">View</a>
                    ) : '-'}
                  </td>
                  <td className="py-2 text-xs">
                    {u.profileScrapedAt ? (
                      <span className="text-green-600">{new Date(u.profileScrapedAt).toLocaleDateString()}</span>
                    ) : (
                      <span className="text-gray-400">Not yet</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {users.length === 0 && <p className="text-sm text-gray-400 text-center py-4">No users yet. Start a scrape to discover users.</p>}
        </div>
      )}

      {tab === 'runs' && (
        <div className="space-y-2">
          {runs.map((r) => (
            <div key={r.id} className="bg-white dark:bg-gray-800 rounded-lg p-3 border border-gray-200 dark:border-gray-700">
              <div className="flex items-center justify-between">
                <div>
                  <span className={`text-xs px-1.5 py-0.5 rounded ${
                    r.status === 'completed' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' :
                    r.status === 'failed' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' :
                    r.status === 'paused' ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400' :
                    r.status === 'running' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400' :
                    'bg-gray-100 text-gray-700'
                  }`}>{r.status}</span>
                  <span className="text-xs text-gray-400 ml-2">{r.phase}</span>
                </div>
                <span className="text-xs text-gray-400">{new Date(r.createdAt).toLocaleString()}</span>
              </div>
              <div className="text-xs text-gray-400 mt-1">
                Posts: {r.postsProcessed || 0}/{r.totalPostsFound || 0} | Users: {r.totalUsersFound || 0} | Profiles: {r.profilesScraped || 0}
              </div>
              {r.errorMessage && <p className="text-xs text-red-500 mt-1">{r.errorMessage}</p>}
            </div>
          ))}
          {runs.length === 0 && <p className="text-sm text-gray-400 text-center py-4">No runs yet.</p>}
        </div>
      )}
    </div>
  );
}
