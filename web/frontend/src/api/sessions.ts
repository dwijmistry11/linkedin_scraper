import api from './client';
import type { Session } from '../types';

export const fetchSessions = () => api.get<Session[]>('/sessions');

export const createSession = (name: string, cookieValue?: string) =>
  api.post<Session>('/sessions', { name, cookie_value: cookieValue });

export const verifySession = (id: string) =>
  api.post<{ authenticated: boolean }>(`/sessions/${id}/verify`);

export const loginWithCookie = (id: string, cookieValue: string) =>
  api.post<Session>(`/sessions/${id}/login-cookie`, { cookie_value: cookieValue });

export const loginWithCredentials = (id: string, email: string, password: string) =>
  api.post<Session>(`/sessions/${id}/login-credentials`, { email, password });

export const deleteSession = (id: string) => api.delete(`/sessions/${id}`);
