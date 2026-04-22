import api from './client';
import type { ScrapeJob, ScrapeResult } from '../types';

export const scrapePerson = (sessionId: string, url: string) =>
  api.post<ScrapeJob>('/scrape/person', { session_id: sessionId, url });

export const scrapeCompany = (sessionId: string, url: string) =>
  api.post<ScrapeJob>('/scrape/company', { session_id: sessionId, url });

export const scrapeJob = (sessionId: string, url: string) =>
  api.post<ScrapeJob>('/scrape/job', { session_id: sessionId, url });

export const scrapeJobSearch = (
  sessionId: string,
  keywords?: string,
  location?: string,
  limit?: number,
) =>
  api.post<ScrapeJob>('/scrape/job-search', {
    session_id: sessionId,
    keywords,
    location,
    limit,
  });

export const scrapeCompanyPosts = (sessionId: string, companyUrl: string, limit?: number) =>
  api.post<ScrapeJob>('/scrape/company-posts', {
    session_id: sessionId,
    company_url: companyUrl,
    limit,
  });

export const getScrapeJob = (jobId: string) => api.get<ScrapeJob>(`/scrape/${jobId}`);

export const getScrapeResult = (jobId: string) =>
  api.get<ScrapeResult>(`/scrape/${jobId}/result`);
