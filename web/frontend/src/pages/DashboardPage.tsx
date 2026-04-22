import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { User, Building2, Briefcase, FileText, History, KeyRound } from 'lucide-react';
import { useAppStore } from '../stores/appStore';
import { fetchHistory } from '../api/history';
import type { ScrapeJob } from '../types';

const quickActions = [
  { to: '/scrape/person', label: 'Scrape Person', icon: User, color: 'bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400' },
  { to: '/scrape/company', label: 'Scrape Company', icon: Building2, color: 'bg-green-50 dark:bg-green-900/20 text-green-600 dark:text-green-400' },
  { to: '/scrape/job', label: 'Scrape Job', icon: Briefcase, color: 'bg-purple-50 dark:bg-purple-900/20 text-purple-600 dark:text-purple-400' },
  { to: '/scrape/posts', label: 'Scrape Posts', icon: FileText, color: 'bg-orange-50 dark:bg-orange-900/20 text-orange-600 dark:text-orange-400' },
];

export default function DashboardPage() {
  const { sessions, activeSessionId } = useAppStore();
  const activeSession = sessions.find((s) => s.id === activeSessionId);
  const [recentJobs, setRecentJobs] = useState<ScrapeJob[]>([]);

  useEffect(() => {
    fetchHistory({ per_page: 5 }).then(({ data }) => setRecentJobs(data.items)).catch(() => {});
  }, []);

  return (
    <div className="max-w-4xl space-y-6">
      <h2 className="text-2xl font-bold">Dashboard</h2>

      {/* Session status */}
      <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-gray-500 dark:text-gray-400">Active Session</p>
            {activeSession ? (
              <p className="font-medium">
                {activeSession.name}
                <span className={`ml-2 text-xs px-1.5 py-0.5 rounded ${activeSession.is_active ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' : 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'}`}>
                  {activeSession.is_active ? 'Verified' : 'Unverified'}
                </span>
              </p>
            ) : (
              <p className="text-gray-400">No session selected</p>
            )}
          </div>
          <Link
            to="/sessions"
            className="text-sm text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1"
          >
            <KeyRound size={14} /> Manage
          </Link>
        </div>
      </div>

      {/* Quick actions */}
      <div>
        <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-3">Quick Actions</h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {quickActions.map((action) => {
            const Icon = action.icon;
            return (
              <Link
                key={action.to}
                to={action.to}
                className={`${action.color} rounded-lg p-4 flex flex-col items-center gap-2 hover:opacity-80 transition-opacity`}
              >
                <Icon size={24} />
                <span className="text-sm font-medium">{action.label}</span>
              </Link>
            );
          })}
        </div>
      </div>

      {/* Recent scrapes */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">Recent Scrapes</h3>
          <Link to="/history" className="text-sm text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1">
            <History size={14} /> View all
          </Link>
        </div>
        {recentJobs.length === 0 ? (
          <p className="text-sm text-gray-400">No scrapes yet. Get started with a quick action above!</p>
        ) : (
          <div className="space-y-2">
            {recentJobs.map((job) => (
              <Link
                key={job.id}
                to={`/history/${job.id}`}
                className="block bg-white dark:bg-gray-800 rounded-lg p-3 border border-gray-200 dark:border-gray-700 hover:border-blue-300 dark:hover:border-blue-600 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">{job.scrape_type}</span>
                  <span className={`text-xs px-1.5 py-0.5 rounded ${
                    job.status === 'completed' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' :
                    job.status === 'failed' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' :
                    'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
                  }`}>
                    {job.status}
                  </span>
                </div>
                <p className="text-xs text-gray-400 truncate mt-1">{job.input_url}</p>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
