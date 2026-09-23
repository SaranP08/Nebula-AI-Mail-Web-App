/**
 * Shared TypeScript types for the Mail App.
 *
 * These mirror the backend Pydantic schemas exactly so the
 * Zustand store and API client stay in sync.
 */

// ── Email types ──────────────────────────────────────────────────────────────

export interface EmailAddress {
  name: string;
  address: string;
}

export interface EmailSummary {
  id: string;
  threadId: string;
  sender: EmailAddress;
  to: EmailAddress[];
  subject: string;
  snippet: string;
  date: string; // ISO 8601
  is_read: boolean;
}

export interface Attachment {
  attachment_id: string;
  filename: string;
  mime_type: string;
  size: number;
}

export interface EmailDetail {
  id: string;
  threadId: string;
  sender: EmailAddress;
  to: EmailAddress[];
  cc: EmailAddress[];
  reply_to: EmailAddress | null;
  subject: string;
  date: string;
  body_html: string;
  body_plain: string;
  snippet: string;
  attachments: Attachment[];
  is_read: boolean;
}

export interface EmailListResponse {
  emails: EmailSummary[];
  next_page_token: string | null;
  result_size_estimate: number;
}

export interface ThreadMessage {
  id: string;
  sender: EmailAddress;
  date: string;
  snippet: string;
  body_html: string;
  body_plain: string;
  is_read: boolean;
}

export interface ThreadResponse {
  thread_id: string;
  subject: string;
  messages: ThreadMessage[];
}

// ── Filters ──────────────────────────────────────────────────────────────────

export interface Filters {
  folder: 'inbox' | 'sent';
  date_from: string | null;   // YYYY-MM-DD
  date_to: string | null;     // YYYY-MM-DD
  sender: string | null;
  keyword: string | null;
  unread: boolean | null;
  page_token: string | null;
  limit: number;
}

export const defaultFilters: Filters = {
  folder: 'inbox',
  date_from: null,
  date_to: null,
  sender: null,
  keyword: null,
  unread: null,
  page_token: null,
  limit: 25,
};

// ── Draft ────────────────────────────────────────────────────────────────────

export type ComposeMode = 'new' | 'reply' | 'replyAll' | 'forward';

export interface Draft {
  to: string;
  cc: string;
  subject: string;
  body: string;
  replyToMessageId: string | null;
  threadId: string | null;
  mode: ComposeMode;
}

export const defaultDraft: Draft = {
  to: '',
  cc: '',
  subject: '',
  body: '',
  replyToMessageId: null,
  threadId: null,
  mode: 'new',
};

// ── User ─────────────────────────────────────────────────────────────────────

export interface User {
  id: string;
  email: string;
  name: string;
  picture: string;
}

// ── App view states ───────────────────────────────────────────────────────────

export type AppView = 'list' | 'detail' | 'compose';
export type Theme = 'light' | 'dark';

// ── Assistant & UI Action types ───────────────────────────────────────────────

export type UIAction =
  | { action: 'set_filters'; params: Partial<Filters> }
  | { action: 'clear_filters'; params?: Record<string, never> }
  | { action: 'show_results'; params: { email_ids: string[] } }
  | { action: 'open_email'; params: { email_id: string } }
  | { action: 'navigate'; params: { view: AppView; folder?: 'inbox' | 'sent' } }
  | { action: 'open_compose'; params: { mode: ComposeMode; reply_to_message_id?: string } }
  | { action: 'fill_compose'; params: { to?: string; cc?: string; subject?: string; body?: string } }
  | { action: 'propose_send'; params?: Record<string, never> };

export interface ConfirmSendProposal {
  to: string;
  subject: string;
  bodyPreview: string;
}

export interface UIState {
  view: AppView;
  folder: 'inbox' | 'sent';
  activeFilters: Filters;
  openEmail?: {
    id: string;
    from: string;
    to: string;
    replyTo?: string;
    subject: string;
    date: string;
    body: string;
    threadId: string;
  } | null;
  currentDraft: Draft;
  timezone: string;
  currentDatetime: string;
}

export interface AssistantMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  toolStatus?: string;
  cards?: EmailSummary[];
  confirmSend?: ConfirmSendProposal | null;
}

export interface ToastItem {
  id: number;
  message: string;
}

