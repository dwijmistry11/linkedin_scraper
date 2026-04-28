import api from './client';

export interface CRMSettings {
  url: string;
  has_api_key: boolean;
  auto_sync: boolean;
}

export interface CRMStatus {
  connected: boolean;
  url: string;
}

export interface CRMSyncResult {
  success: boolean;
  detail: any;
}

export const getCRMSettings = () => api.get<CRMSettings>('/crm/settings');

export const updateCRMSettings = (data: { url?: string; api_key?: string; auto_sync?: boolean }) =>
  api.put<CRMSettings>('/crm/settings', data);

export const getCRMStatus = () => api.get<CRMStatus>('/crm/status');

export const syncToCRM = (jobId: string) => api.post<CRMSyncResult>(`/crm/sync/${jobId}`);

export const syncAllToCRM = () => api.post<CRMSyncResult>('/crm/sync-all');
