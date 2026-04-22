import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, Download } from 'lucide-react';
import { getScrapeJob } from '../api/scrape';
import { getExportUrl } from '../api/history';
import ResultViewer from '../components/results/ResultViewer';
import type { ScrapeJob } from '../types';

export default function ResultDetailPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const [job, setJob] = useState<ScrapeJob | null>(null);

  useEffect(() => {
    if (jobId) {
      getScrapeJob(jobId).then(({ data }) => setJob(data)).catch(() => {});
    }
  }, [jobId]);

  if (!jobId) return null;

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
              <div className="flex gap-2">
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
              </div>
            )}
          </div>
          {job.error_message && (
            <p className="text-sm text-red-500 mt-2">{job.error_message}</p>
          )}
        </div>
      )}

      {job?.status === 'completed' && <ResultViewer jobId={jobId} />}
    </div>
  );
}
