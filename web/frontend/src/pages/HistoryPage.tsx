import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Trash2, Download } from 'lucide-react';
import { fetchHistory, deleteHistory, getExportUrl } from '../api/history';
import type { ScrapeJob } from '../types';

const typeColors: Record<string, string> = {
  person: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  company: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  job: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400',
  job_search: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400',
  company_posts: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
};

const statusColors: Record<string, string> = {
  completed: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  failed: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  running: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  pending: 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-400',
};

export default function HistoryPage() {
  const [jobs, setJobs] = useState<ScrapeJob[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [typeFilter, setTypeFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const perPage = 20;

  const load = () => {
    fetchHistory({ type: typeFilter || undefined, status: statusFilter || undefined, page, per_page: perPage })
      .then(({ data }) => {
        setJobs(data.items);
        setTotal(data.total);
      })
      .catch(() => {});
  };

  useEffect(load, [page, typeFilter, statusFilter]);

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this scrape result?')) return;
    try {
      await deleteHistory(id);
      load();
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Failed to delete');
    }
  };

  const totalPages = Math.ceil(total / perPage);

  return (
    <div className="max-w-5xl space-y-4">
      <h2 className="text-2xl font-bold">Scrape History</h2>

      {/* Filters */}
      <div className="flex gap-3">
        <select
          value={typeFilter}
          onChange={(e) => { setTypeFilter(e.target.value); setPage(1); }}
          className="text-sm border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-1.5 bg-white dark:bg-gray-800"
        >
          <option value="">All types</option>
          <option value="person">Person</option>
          <option value="company">Company</option>
          <option value="job">Job</option>
          <option value="job_search">Job Search</option>
          <option value="company_posts">Company Posts</option>
        </select>
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
          className="text-sm border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-1.5 bg-white dark:bg-gray-800"
        >
          <option value="">All statuses</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
          <option value="running">Running</option>
          <option value="pending">Pending</option>
        </select>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 dark:border-gray-700 text-left text-gray-500 dark:text-gray-400">
              <th className="pb-2 font-medium">Type</th>
              <th className="pb-2 font-medium">URL / Params</th>
              <th className="pb-2 font-medium">Status</th>
              <th className="pb-2 font-medium">Date</th>
              <th className="pb-2 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
            {jobs.map((job) => (
              <tr key={job.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                <td className="py-2.5">
                  <span className={`text-xs px-1.5 py-0.5 rounded ${typeColors[job.scrape_type] || ''}`}>
                    {job.scrape_type}
                  </span>
                </td>
                <td className="py-2.5">
                  <Link
                    to={`/history/${job.id}`}
                    className="text-blue-600 dark:text-blue-400 hover:underline truncate block max-w-xs"
                  >
                    {job.input_url}
                  </Link>
                </td>
                <td className="py-2.5">
                  <span className={`text-xs px-1.5 py-0.5 rounded ${statusColors[job.status] || ''}`}>
                    {job.status}
                  </span>
                </td>
                <td className="py-2.5 text-gray-400 text-xs">
                  {new Date(job.created_at).toLocaleString()}
                </td>
                <td className="py-2.5">
                  <div className="flex items-center gap-1">
                    {job.status === 'completed' && (
                      <>
                        <a
                          href={getExportUrl(job.id, 'json')}
                          className="p-1 text-gray-400 hover:text-blue-600"
                          title="Export JSON"
                        >
                          <Download size={14} />
                        </a>
                      </>
                    )}
                    <button
                      onClick={() => handleDelete(job.id)}
                      className="p-1 text-gray-400 hover:text-red-500"
                      title="Delete"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {jobs.length === 0 && (
        <p className="text-sm text-gray-400 text-center py-8">No scrape history found.</p>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button
            onClick={() => setPage(Math.max(1, page - 1))}
            disabled={page <= 1}
            className="px-3 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded disabled:opacity-30"
          >
            Previous
          </button>
          <span className="text-sm text-gray-500">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage(Math.min(totalPages, page + 1))}
            disabled={page >= totalPages}
            className="px-3 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded disabled:opacity-30"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
