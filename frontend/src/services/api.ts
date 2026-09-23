/**
 * Typed API client for the Mail App backend.
 *
 * All requests include credentials (cookies) automatically.
 * Errors are thrown as { status, message } objects.
 */
import type {
  EmailDetail,
  EmailListResponse,
  Filters,
  ThreadResponse,
  User,
} from '@/types';

const BASE = '';  // same origin via Vite proxy in dev, FastAPI in prod

interface ApiError {
  status: number;
  message: string;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    credentials: 'include',  // always send the session cookie
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  });

  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    try {
      const body = await response.json();
      message = body.detail || body.message || message;
    } catch {
      // ignore parse errors
    }
    const error: ApiError = { status: response.status, message };
    throw error;
  }

  // 204 No Content
  if (response.status === 204) {
    return null as T;
  }

  return response.json() as Promise<T>;
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export const authApi = {
  me: (): Promise<User> => request<User>('/auth/me'),
  logout: (): Promise<void> =>
    request<void>('/auth/logout', { method: 'POST' }),
  loginUrl: '/auth/login',
};

// ── Emails ────────────────────────────────────────────────────────────────────

function buildQueryString(filters: Filters): string {
  const params = new URLSearchParams();
  params.set('folder', filters.folder);
  params.set('limit', String(filters.limit));
  if (filters.page_token) params.set('page_token', filters.page_token);
  if (filters.date_from) params.set('date_from', filters.date_from);
  if (filters.date_to) params.set('date_to', filters.date_to);
  if (filters.sender) params.set('sender', filters.sender);
  if (filters.keyword) params.set('keyword', filters.keyword);
  if (filters.unread !== null && filters.unread !== undefined) {
    params.set('unread', String(filters.unread));
  }
  return params.toString();
}

export const emailsApi = {
  list: (filters: Filters): Promise<EmailListResponse> =>
    request<EmailListResponse>(`/api/emails?${buildQueryString(filters)}`),

  get: (id: string): Promise<EmailDetail> =>
    request<EmailDetail>(`/api/emails/${id}`),

  send: (payload: {
    to: string[];
    cc?: string[];
    subject: string;
    body: string;
    reply_to_message_id?: string | null;
    thread_id?: string | null;
  }): Promise<{ id: string; threadId: string; status: string }> =>
    request(`/api/emails/send`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  markRead: (id: string): Promise<void> =>
    request<void>(`/api/emails/${id}/read`, { method: 'POST' }),

  markUnread: (id: string): Promise<void> =>
    request<void>(`/api/emails/${id}/unread`, { method: 'POST' }),

  getThread: (threadId: string): Promise<ThreadResponse> =>
    request<ThreadResponse>(`/api/threads/${threadId}`),
};
