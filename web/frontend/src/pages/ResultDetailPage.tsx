import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, Download, Loader2, Upload } from 'lucide-react';
import { getScrapeJob } from '../api/scrape';
import { getExportUrl } from '../api/history';
import { syncToCRM } from '../api/crm';
import ResultViewer from '../components/results/ResultViewer';
import type { ScrapeJob } from '../types';

const SYNCABLE_TYPES = ['person', 'company', 'extract_users'];

export default function ResultDetailPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const [job, setJob] = useState<ScrapeJob | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<string | null>(null);
  const [syncError, setSyncError] = useState<string | null>(null);

  useEffect(() => {
    if (jobId) {
      getScrapeJob(jobId).then(({ data }) => setJob(data)).catch(() => {});
    }
  }, [jobId]);

  const handleSync = async () => {
    if (!jobId) return;
    setSyncing(true);
    setSyncResult(null);
    setSyncError(null);
    try {
      const { data } = await syncToCRM(jobId);
      const d = data.detail;
      if (d.action) {
        setSyncResult(`${d.action} in CRM`);
      } else if (d.created !== undefined) {
        setSyncResult(`Created: ${d.created}, Updated: ${d.updated}, Failed: ${d.failed || 0}`);
      } else {
        setSyncResult('Synced to CRM');
      }
    } catch (e: any) {
      setSyncError(e.response?.data?.detail || 'Sync failed');
    }
    setSyncing(false);
  };

  if (!jobId) return null;

  const canSync = job?.status === 'completed' && SYNCABLE_TYPES.includes(job?.scrape_type || '');

  return (
    <div className="max-w-3xl space-y-4">
      <Link to="/history" className="flex items-center gap-1 text-sm text-blue-600 dark:text-blue-400 hover:underline">
        <ArrowLeft size={14} /> Back to History
      </Link>

      {job && (
        <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold capitalize">{job.scrape_type.replace('_', ' ')}</h2>
              <p className="text-sm text-gray-400 truncate">{job.input_url}</p>
              <p className="text-xs text-gray-400 mt-1">
                {job.status} - {new Date(job.created_at).toLocaleString()}
              </p>
            </div>
            {job.status === 'completed' && (
              <div className="flex gap-2 flex-wrap">
                <a
                  href={getExportUrl(jobId, 'json')}
                  className="flex items-center gap-1 px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800"
                >
                  <Download size={14} /> JSON
                </a>
                <a
                  href={getExportUrl(jobId, 'csv')}
                  className="flex items-center gap-1 px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800"
                >
                  <Download size={14} /> CSV
                </a>
                {canSync && (
                  <button
                    onClick={handleSync}
                    disabled={syncing}
                    className="flex items-center gap-1 px-3 py-1.5 text-sm bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white rounded-lg"
                  >
                    {syncing ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}
                    Push to CRM
                  </button>
                )}
              </div>
            )}
          </div>
          {syncResult && <p className="text-sm text-green-600 mt-2">{syncResult}</p>}
          {syncError && <p className="text-sm text-red-500 mt-2">{syncError}</p>}
          {job.error_message && <p className="text-sm text-red-500 mt-2">{job.error_message}</p>}
        </div>
      )}

      {job?.status === 'completed' && <ResultViewer jobId={jobId} />}
    </div>
  );
}
