import { useState } from 'react';
import ScrapeForm from '../components/scrape/ScrapeForm';
import JobSearchForm from '../components/scrape/JobSearchForm';
import ProgressPanel from '../components/scrape/ProgressPanel';
import ResultViewer from '../components/results/ResultViewer';
import { useScrapeJob } from '../hooks/useScrapeJob';
import { scrapeJob, scrapeJobSearch } from '../api/scrape';

export default function ScrapeJobPage() {
  const [mode, setMode] = useState<'url' | 'search'>('url');
  const { startScrape, jobId, startError, progress, completed, error } = useScrapeJob();
  const isRunning = !!jobId && !completed && !error;

  return (
    <div className="max-w-3xl space-y-4">
      <h2 className="text-2xl font-bold">Scrape Job</h2>

      <div className="flex gap-2">
        <button
          onClick={() => setMode('url')}
          className={`px-3 py-1.5 text-sm rounded-lg ${
            mode === 'url'
              ? 'bg-blue-600 text-white'
              : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400'
          }`}
        >
          Single Job URL
        </button>
        <button
          onClick={() => setMode('search')}
          className={`px-3 py-1.5 text-sm rounded-lg ${
            mode === 'search'
              ? 'bg-blue-600 text-white'
              : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400'
          }`}
        >
          Job Search
        </button>
      </div>

      {mode === 'url' ? (
        <ScrapeForm
          label="LinkedIn Job URL"
          placeholder="https://www.linkedin.com/jobs/view/1234567890/"
          onSubmit={(url) => startScrape(scrapeJob, url)}
          loading={isRunning}
        />
      ) : (
        <JobSearchForm
          onSubmit={(keywords, location, limit) =>
            startScrape(scrapeJobSearch, keywords, location, limit)
          }
          loading={isRunning}
        />
      )}

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
