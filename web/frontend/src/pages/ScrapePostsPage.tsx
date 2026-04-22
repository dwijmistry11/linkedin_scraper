import { useState } from 'react';
import { Loader2 } from 'lucide-react';
import ProgressPanel from '../components/scrape/ProgressPanel';
import ResultViewer from '../components/results/ResultViewer';
import { useScrapeJob } from '../hooks/useScrapeJob';
import { scrapeCompanyPosts } from '../api/scrape';

export default function ScrapePostsPage() {
  const [url, setUrl] = useState('');
  const [limit, setLimit] = useState(10);
  const { startScrape, jobId, startError, progress, completed, error } = useScrapeJob();
  const isRunning = !!jobId && !completed && !error;

  return (
    <div className="max-w-3xl space-y-4">
      <h2 className="text-2xl font-bold">Scrape Company Posts</h2>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (url.trim()) startScrape(scrapeCompanyPosts, url.trim(), limit);
        }}
        className="space-y-3"
      >
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
          <div className="sm:col-span-3">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Company URL
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
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Limit
            </label>
            <input
              type="number"
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value))}
              min={1}
              max={100}
              className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-800 focus:ring-2 focus:ring-blue-500 outline-none"
            />
          </div>
        </div>
        <button
          type="submit"
          disabled={isRunning}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg flex items-center gap-2 transition-colors"
        >
          {isRunning && <Loader2 size={16} className="animate-spin" />}
          Scrape Posts
        </button>
      </form>

      {startError && <p className="text-sm text-red-500">{startError}</p>}
      {jobId && (
        <ProgressPanel
          percent={progress.percent}
          message={progress.message}
          error={error}
          completed={completed}
        />
      )}
      {jobId && completed && <ResultViewer jobId={jobId} />}
    </div>
  );
}
