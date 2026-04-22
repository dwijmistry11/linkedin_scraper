import api from './client';
import type { HistoryList } from '../types';

export const fetchHistory = (params?: {
  type?: string;
  status?: string;
  search?: string;
  page?: number;
  per_page?: number;
}) => api.get<HistoryList>('/history', { params });

export const deleteHistory = (jobId: string) => api.delete(`/history/${jobId}`);

export const getExportUrl = (jobId: string, format: 'json' | 'csv') =>
  `/api/history/${jobId}/export?format=${format}`;
