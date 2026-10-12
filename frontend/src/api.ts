import axios from 'axios';
import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({ defaultOptions: {
  queries: { retry: false, staleTime: 10_000 }, mutations: { retry: false },
} });
export const api = axios.create({ baseURL: '/api/v1', timeout: 180_000 });
let accessToken = '';
export function setToken(value: string) { accessToken = value; }
api.interceptors.request.use(config => {
  if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`;
  return config;
});
api.interceptors.response.use(response => response, error => {
  if (error.response?.status === 401 && error.config?.url !== '/auth/login') {
    setToken('');
    window.dispatchEvent(new Event('session-expired'));
  }
  return Promise.reject(error);
});
export function errorText(error: unknown): string {
  if (!axios.isAxiosError(error)) return '操作失败，请稍后重试。';
  const body = error.response?.data;
  if (body?.message) return `${body.message}${body.code ? ` (${body.code})` : ''}${body.request_id ? ` · 请求 ${body.request_id}` : ''}`;
  if (Array.isArray(body?.detail)) return body.detail.map((d: { loc?: string[]; msg?: string }) => `${d.loc?.join('.')}: ${d.msg}`).join('；');
  if (typeof body?.detail === 'string') return body.detail;
  if (error.code === 'ECONNABORTED') return '请求超时；上传可能已受理，请保持表单不变重试。';
  return error.response ? `请求失败（HTTP ${error.response.status}）` : '无法连接 API，请检查后端与前端代理。';
}
export function isPending(status: string) { return status === 'QUEUED' || status === 'RUNNING'; }
