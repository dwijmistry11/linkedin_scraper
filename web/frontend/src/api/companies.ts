import api from './client';

export const listCompanies = (search?: string) =>
  api.get('/companies', { params: search ? { search } : {} });

export const addCompany = (linkedinUrl: string, name?: string) =>
  api.post('/companies', { linkedin_url: linkedinUrl, name });

export const getCompany = (id: string) => api.get(`/companies/${id}`);

export const getCompanyPosts = (id: string) => api.get(`/companies/${id}/posts`);

export const getCompanyUsers = (id: string) => api.get(`/companies/${id}/users`);

export const getCompanyRuns = (id: string) => api.get(`/companies/${id}/runs`);

export const startScrape = (companyId: string, sessionIds: string[]) =>
  api.post(`/companies/${companyId}/scrape`, { session_ids: sessionIds });

export const pauseScrape = (runId: string) =>
  api.post(`/scrape-runs/${runId}/pause`);

export const resumeScrape = (runId: string, sessionIds: string[]) =>
  api.post(`/scrape-runs/${runId}/resume`, { session_ids: sessionIds });

export const getScrapeRun = (runId: string) =>
  api.get(`/scrape-runs/${runId}`);
