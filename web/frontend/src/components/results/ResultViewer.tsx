import { useEffect, useState } from 'react';
import { getScrapeResult } from '../../api/scrape';
import type { ScrapeResult, Person, Company, Job, Post, ExtractUsersResult } from '../../types';
import PersonCard from './PersonCard';
import CompanyCard from './CompanyCard';
import JobCard from './JobCard';
import PostCard from './PostCard';
import UsersTable from './UsersTable';

export default function ResultViewer({ jobId }: { jobId: string }) {
  const [result, setResult] = useState<ScrapeResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getScrapeResult(jobId)
      .then(({ data }) => setResult(data))
      .catch((e) => setError(e.response?.data?.detail || 'Failed to load result'));
  }, [jobId]);

  if (error) return <p className="text-sm text-red-500">{error}</p>;
  if (!result) return <p className="text-sm text-gray-400">Loading result...</p>;

  const { scrape_type, result_data } = result;

  if (scrape_type === 'person') {
    return <PersonCard data={result_data as Person} />;
  }
  if (scrape_type === 'company') {
    return <CompanyCard data={result_data as Company} />;
  }
  if (scrape_type === 'job') {
    return <JobCard data={result_data as Job} />;
  }
  if (scrape_type === 'company_posts') {
    const posts = result_data as Post[];
    return (
      <div className="space-y-3">
        <p className="text-sm text-gray-500">{posts.length} posts scraped</p>
        {posts.map((p, i) => (
          <PostCard key={i} data={p} />
        ))}
      </div>
    );
  }
  if (scrape_type === 'extract_users') {
    return <UsersTable data={result_data as unknown as ExtractUsersResult} />;
  }
  if (scrape_type === 'job_search') {
    const urls = result_data as string[];
    return (
      <div className="space-y-2">
        <p className="text-sm text-gray-500">{urls.length} job URLs found</p>
        {urls.map((url, i) => (
          <a
            key={i}
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="block text-sm text-blue-600 dark:text-blue-400 hover:underline truncate"
          >
            {url}
          </a>
        ))}
      </div>
    );
  }

  return (
    <pre className="text-xs bg-gray-50 dark:bg-gray-800 p-4 rounded-lg overflow-auto">
      {JSON.stringify(result_data, null, 2)}
    </pre>
  );
}
