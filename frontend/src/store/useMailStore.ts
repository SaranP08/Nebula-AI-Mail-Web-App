/**
 * The single Zustand store for the Mail App.
 *
 * ALL UI state lives here. The AI assistant (future step) will also
 * read and write this store to control the UI programmatically.
 *
 * Architecture decisions:
 *  - One flat store (no slices) — simple for a hiring demo, easy to inspect
 *  - Actions are plain functions — the AI can call them by name
 *  - Async actions update loading/error state in-place
 */
import { create } from 'zustand';
import { authApi, emailsApi } from '@/services/api';
import { liveStreamService } from '@/services/stream';
import type {
  AppView,
  Draft,
  EmailDetail,
  EmailSummary,
  Filters,
  Theme,
  ToastItem,
  UIState,
  User,
} from '@/types';
import { defaultDraft, defaultFilters } from '@/types';

// ── Store shape ───────────────────────────────────────────────────────────────

interface MailState {
  // ── Auth ──────────────────────────────────────────────────────────────────
  user: User | null;
  authLoading: boolean;

  // ── Navigation / view ─────────────────────────────────────────────────────
  view: AppView;
  folder: 'inbox' | 'sent';

  // ── Filters (shared by filter popover, search box, and filter chips) ──────
  filters: Filters;

  // ── Email list ─────────────────────────────────────────────────────────────
  emails: EmailSummary[];
  nextPageToken: string | null;
  loading: boolean;
  error: string | null;
  resultSizeEstimate: number;

  // ── Email detail ───────────────────────────────────────────────────────────
  openEmailId: string | null;
  /** The full detail of the currently open email (null if none or loading) */
  openEmailDetail: EmailDetail | null;
  detailLoading: boolean;
  detailError: string | null;

  // ── Compose draft ──────────────────────────────────────────────────────────
  draft: Draft;

  // ── Real-time & Highlights ───────────────────────────────────────────────
  highlightedEmailIds: string[];
  toast: ToastItem | null;
  showToast: (message: string) => void;
  clearToast: () => void;
  handleIncomingMail: (email: EmailSummary) => void;

  // ── Filtered IDs for AI show_results ───────────────────────────────────────
  filteredEmailIds: string[] | null;
  setFilteredEmailIds: (ids: string[] | null) => void;

  // ── Right-side Copilot panel ───────────────────────────────────────────────
  assistantOpen: boolean;
  openAssistant: () => void;

  // ── UI state snapshot for AI assistant ─────────────────────────────────────
  getUIState: () => UIState;

  // ── Theme ──────────────────────────────────────────────────────────────────
  theme: Theme;

  // ── Actions ───────────────────────────────────────────────────────────────
  // Auth
  loadUser: () => Promise<void>;
  logout: () => Promise<void>;

  // Navigation
  setFolder: (folder: 'inbox' | 'sent') => void;
  setView: (view: AppView) => void;

  // Filters (all three entry points — search, popover, chips — call these)
  setFilters: (partial: Partial<Filters>) => void;
  resetFilters: () => void;

  // Email list
  loadEmails: () => Promise<void>;
  loadMoreEmails: () => Promise<void>;

  // Email detail — action to open an email by ID
  openEmail: (id: string) => Promise<void>;
  closeEmail: () => void;

  // Compose
  openCompose: (partial?: Partial<Draft>) => void;
  updateDraft: (partial: Partial<Draft>) => void;
  sendDraft: () => Promise<void>;
  discardDraft: () => void;

  // Mark read/unread
  markRead: (id: string) => Promise<void>;
  markUnread: (id: string) => Promise<void>;

  // Copilot panel toggle
  toggleAssistant: () => void;

  // Theme
  setTheme: (theme: Theme) => void;
}

// ── Store implementation ──────────────────────────────────────────────────────

const THEME_KEY = 'mail-app-theme';

function getInitialTheme(): Theme {
  try {
    const stored = localStorage.getItem(THEME_KEY);
    if (stored === 'dark' || stored === 'light') return stored;
  } catch { /* ignore */ }
  if (typeof window !== 'undefined' && window.matchMedia) {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  return 'light';
}

export const useMailStore = create<MailState>((set, get) => ({
  // ── Initial state ──────────────────────────────────────────────────────────
  user: null,
  authLoading: true,
  view: 'list',
  folder: 'inbox',
  filters: { ...defaultFilters },
  emails: [],
  nextPageToken: null,
  loading: false,
  error: null,
  resultSizeEstimate: 0,
  openEmailId: null,
  openEmailDetail: null,
  detailLoading: false,
  detailError: null,
  draft: { ...defaultDraft },
  assistantOpen: false,
  theme: getInitialTheme(),

  // ── Real-time & Highlights ─────────────────────────────────────────────────
  highlightedEmailIds: [],
  toast: null,
  showToast: (message: string) => {
    const id = Date.now();
    set({ toast: { id, message } });
    setTimeout(() => {
      if (get().toast?.id === id) {
        set({ toast: null });
      }
    }, 4500);
  },
  clearToast: () => set({ toast: null }),

  handleIncomingMail: (email: EmailSummary) => {
    const { folder, filters, emails, resultSizeEstimate } = get();

    // Folder check: new incoming email belongs in Inbox
    const matchesFolder = folder === 'inbox';

    // Unread filter check: new mail is unread
    const matchesUnread = filters.unread === null || filters.unread === true;

    // Sender filter check
    let matchesSender = true;
    if (filters.sender && filters.sender.trim()) {
      const q = filters.sender.toLowerCase();
      matchesSender =
        (email.sender.name || '').toLowerCase().includes(q) ||
        (email.sender.address || '').toLowerCase().includes(q);
    }

    // Keyword filter check
    let matchesKeyword = true;
    if (filters.keyword && filters.keyword.trim()) {
      const q = filters.keyword.toLowerCase();
      matchesKeyword =
        (email.subject || '').toLowerCase().includes(q) ||
        (email.snippet || '').toLowerCase().includes(q);
    }

    if (matchesFolder && matchesUnread && matchesSender && matchesKeyword) {
      if (!emails.some(e => e.id === email.id)) {
        set({
          emails: [email, ...emails],
          resultSizeEstimate: resultSizeEstimate + 1,
          highlightedEmailIds: [...get().highlightedEmailIds, email.id],
        });

        // Clear highlight after 3.5s
        setTimeout(() => {
          set({
            highlightedEmailIds: get().highlightedEmailIds.filter(id => id !== email.id),
          });
        }, 3500);
      }
    }

    // Always show notification toast
    const senderDisplay = email.sender.name || email.sender.address || 'Unknown';
    get().showToast(`New mail from ${senderDisplay}${email.subject ? ': ' + email.subject : ''}`);
  },

  // ── Filtered IDs ───────────────────────────────────────────────────────────
  filteredEmailIds: null,
  setFilteredEmailIds: (ids) => set({ filteredEmailIds: ids }),

  // ── Copilot panel ──────────────────────────────────────────────────────────
  openAssistant: () => set({ assistantOpen: true }),

  // ── UI state snapshot for AI assistant ─────────────────────────────────────
  getUIState: (): UIState => {
    const s = get();
    let openEmailInfo = null;
    if (s.openEmailDetail) {
      const d = s.openEmailDetail;
      openEmailInfo = {
        id: d.id,
        from: d.sender.address || d.sender.name,
        to: d.to.map(t => t.address).join(', '),
        replyTo: d.reply_to?.address || undefined,
        subject: d.subject,
        date: d.date,
        body: (d.body_plain || d.body_html || '').slice(0, 1500),
        threadId: d.threadId,
      };
    }
    return {
      view: s.view,
      folder: s.folder,
      activeFilters: s.filters,
      openEmail: openEmailInfo,
      currentDraft: s.draft,
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
      currentDatetime: new Date().toISOString(),
    };
  },

  // ── Auth ───────────────────────────────────────────────────────────────────
  loadUser: async () => {
    set({ authLoading: true });
    try {
      const user = await authApi.me();
      set({ user, authLoading: false });
      if (user) {
        liveStreamService.connect();
      }
    } catch {
      set({ user: null, authLoading: false });
      liveStreamService.disconnect();
    }
  },

  logout: async () => {
    try {
      await authApi.logout();
    } catch { /* ignore */ }
    liveStreamService.disconnect();
    set({
      user: null,
      emails: [],
      openEmailDetail: null,
      openEmailId: null,
      view: 'list',
      filteredEmailIds: null,
      highlightedEmailIds: [],
    });
  },

  // ── Navigation ─────────────────────────────────────────────────────────────
  setFolder: (folder) => {
    set({
      folder,
      filters: { ...defaultFilters, folder },
      emails: [],
      filteredEmailIds: null,
      nextPageToken: null,
      openEmailDetail: null,
      openEmailId: null,
      view: 'list',
    });
    setTimeout(() => get().loadEmails(), 0);
  },

  setView: (view: AppView) => {
    set({ view });
  },

  // ── Filters ────────────────────────────────────────────────────────────────
  setFilters: (partial) => {
    const current = get().filters;
    const updated = { ...current, ...partial, page_token: null };
    set({ filters: updated, emails: [], nextPageToken: null, filteredEmailIds: null });
    setTimeout(() => get().loadEmails(), 0);
  },

  resetFilters: () => {
    const folder = get().folder;
    set({
      filters: { ...defaultFilters, folder },
      emails: [],
      nextPageToken: null,
      filteredEmailIds: null,
    });
    setTimeout(() => get().loadEmails(), 0);
  },

  // ── Email list ─────────────────────────────────────────────────────────────
  loadEmails: async () => {
    const { filters } = get();
    set({ loading: true, error: null });
    try {
      const result = await emailsApi.list(filters);
      set({
        emails: result.emails,
        nextPageToken: result.next_page_token,
        resultSizeEstimate: result.result_size_estimate,
        loading: false,
      });
    } catch (err: unknown) {
      const msg = (err as { message?: string })?.message ?? 'Failed to load emails';
      set({ loading: false, error: msg });
    }
  },

  loadMoreEmails: async () => {
    const { filters, nextPageToken, emails, loading } = get();
    if (!nextPageToken || loading) return;
    set({ loading: true });
    try {
      const result = await emailsApi.list({ ...filters, page_token: nextPageToken });
      set({
        emails: [...emails, ...result.emails],
        nextPageToken: result.next_page_token,
        loading: false,
      });
    } catch (err: unknown) {
      const msg = (err as { message?: string })?.message ?? 'Failed to load more emails';
      set({ loading: false, error: msg });
    }
  },

  // ── Email detail ───────────────────────────────────────────────────────────
  openEmail: async (id: string) => {
    set({ openEmailId: id, view: 'detail', detailLoading: true, detailError: null, openEmailDetail: null });
    try {
      const email = await emailsApi.get(id);
      set({ openEmailDetail: email, detailLoading: false });
      // Mark as read optimistically in list
      const { emails } = get();
      set({
        emails: emails.map(e => e.id === id ? { ...e, is_read: true } : e),
      });
      // Fire and forget mark-read on server
      emailsApi.markRead(id).catch(() => {/* ignore */});
    } catch (err: unknown) {
      const msg = (err as { message?: string })?.message ?? 'Failed to load email';
      set({ detailLoading: false, detailError: msg });
    }
  },

  closeEmail: () => {
    set({ openEmailId: null, openEmailDetail: null, view: 'list' });
  },

  // ── Compose ────────────────────────────────────────────────────────────────
  openCompose: (partial = {}) => {
    set({
      view: 'compose',
      draft: { ...defaultDraft, ...partial },
    });
  },

  updateDraft: (partial) => {
    set(state => ({ draft: { ...state.draft, ...partial } }));
  },

  sendDraft: async () => {
    const { draft } = get();
    const toList = draft.to.split(',').map(s => s.trim()).filter(Boolean);
    const ccList = draft.cc.split(',').map(s => s.trim()).filter(Boolean);
    await emailsApi.send({
      to: toList,
      cc: ccList,
      subject: draft.subject,
      body: draft.body,
      reply_to_message_id: draft.replyToMessageId,
      thread_id: draft.threadId,
    });
    set({ view: 'list', draft: { ...defaultDraft } });
    get().showToast('Email sent successfully!');
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('mail:sent'));
    }
    setTimeout(() => get().loadEmails(), 0);
  },

  discardDraft: () => {
    set({ view: 'list', draft: { ...defaultDraft } });
  },

  // ── Mark read/unread ───────────────────────────────────────────────────────
  markRead: async (id: string) => {
    set(state => ({
      emails: state.emails.map(e => e.id === id ? { ...e, is_read: true } : e),
      openEmailDetail: state.openEmailDetail?.id === id
        ? { ...state.openEmailDetail, is_read: true }
        : state.openEmailDetail,
    }));
    await emailsApi.markRead(id);
  },

  markUnread: async (id: string) => {
    set(state => ({
      emails: state.emails.map(e => e.id === id ? { ...e, is_read: false } : e),
      openEmailDetail: state.openEmailDetail?.id === id
        ? { ...state.openEmailDetail, is_read: false }
        : state.openEmailDetail,
    }));
    await emailsApi.markUnread(id);
  },

  // ── Copilot panel ──────────────────────────────────────────────────────────
  toggleAssistant: () => {
    set(state => ({ assistantOpen: !state.assistantOpen }));
  },

  // ── Theme ──────────────────────────────────────────────────────────────────
  setTheme: (theme: Theme) => {
    try { localStorage.setItem(THEME_KEY, theme); } catch { /* ignore */ }
    set({ theme });
  },
}));
