import ScrapeForm from '../components/scrape/ScrapeForm';
import ProgressPanel from '../components/scrape/ProgressPanel';
import ResultViewer from '../components/results/ResultViewer';
import { useScrapeJob } from '../hooks/useScrapeJob';
import { scrapePerson } from '../api/scrape';

export default function ScrapePersonPage() {
  const { startScrape, jobId, startError, progress, completed, error } = useScrapeJob();
  const isRunning = !!jobId && !completed && !error;

  return (
    <div className="max-w-3xl space-y-4">
      <h2 className="text-2xl font-bold">Scrape Person</h2>
      <ScrapeForm
        label="LinkedIn Profile URL"
        placeholder="https://www.linkedin.com/in/username/"
        onSubmit={(url) => startScrape(scrapePerson, url)}
        loading={isRunning}
      />
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
