import { describe, it, expect, beforeEach, vi } from 'vitest';
import { useMailStore } from '../useMailStore';
import { uiActionExecutor } from '@/services/uiActionExecutor';

// Mock emailsApi and authApi
vi.mock('@/services/api', () => ({
  emailsApi: {
    list: vi.fn().mockResolvedValue({ emails: [], next_page_token: null, result_size_estimate: 0 }),
    get: vi.fn().mockResolvedValue({
      id: 'mock_1',
      threadId: 'th_1',
      sender: { name: 'Alice', address: 'alice@example.com' },
      to: [{ name: 'Me', address: 'me@example.com' }],
      cc: [],
      subject: 'Hello World',
      date: '2026-09-20T10:00:00Z',
      body_html: '<p>Hello!</p>',
      body_plain: 'Hello!',
      snippet: 'Hello!',
      attachments: [],
      is_read: true,
    }),
    markRead: vi.fn().mockResolvedValue(undefined),
    markUnread: vi.fn().mockResolvedValue(undefined),
    send: vi.fn().mockResolvedValue({ id: 'sent_1', threadId: 'th_1', status: 'sent' }),
    getThread: vi.fn().mockResolvedValue({ thread_id: 'th_1', subject: 'Hello', messages: [] }),
  },
  authApi: {
    me: vi.fn().mockResolvedValue({ id: 'u1', email: 'test@example.com', name: 'Tester', picture: '' }),
    logout: vi.fn().mockResolvedValue(undefined),
  },
}));

describe('useMailStore filter and compose actions', () => {
  beforeEach(() => {
    // Reset store state
    useMailStore.setState({
      view: 'list',
      folder: 'inbox',
      filters: {
        folder: 'inbox',
        date_from: null,
        date_to: null,
        sender: null,
        keyword: null,
        unread: null,
        page_token: null,
        limit: 25,
      },
      emails: [],
      openEmailId: null,
      openEmailDetail: null,
      filteredEmailIds: null,
      draft: {
        to: '',
        cc: '',
        subject: '',
        body: '',
        replyToMessageId: null,
        threadId: null,
        mode: 'new',
      },
    });
  });

  it('updates filters with setFilters and resets page_token', () => {
    useMailStore.getState().setFilters({
      sender: 'alice@example.com',
      keyword: 'invoice',
      unread: true,
    });

    const filters = useMailStore.getState().filters;
    expect(filters.sender).toBe('alice@example.com');
    expect(filters.keyword).toBe('invoice');
    expect(filters.unread).toBe(true);
    expect(filters.page_token).toBeNull();
  });

  it('resets filters while preserving current folder', () => {
    useMailStore.getState().setFolder('sent');
    useMailStore.getState().setFilters({
      keyword: 'confidential',
      unread: false,
    });

    useMailStore.getState().resetFilters();

    const filters = useMailStore.getState().filters;
    expect(filters.folder).toBe('sent');
    expect(filters.keyword).toBeNull();
    expect(filters.unread).toBeNull();
  });

  it('opens compose, updates draft fields, and discards draft', () => {
    useMailStore.getState().openCompose({
      to: 'bob@example.com',
      subject: 'Status check',
    });

    let state = useMailStore.getState();
    expect(state.view).toBe('compose');
    expect(state.draft.to).toBe('bob@example.com');
    expect(state.draft.subject).toBe('Status check');

    useMailStore.getState().updateDraft({
      body: 'Everything looks great!',
    });

    state = useMailStore.getState();
    expect(state.draft.body).toBe('Everything looks great!');

    useMailStore.getState().discardDraft();

    state = useMailStore.getState();
    expect(state.view).toBe('list');
    expect(state.draft.to).toBe('');
    expect(state.draft.body).toBe('');
  });
});

describe('uiActionExecutor sequential execution', () => {
  beforeEach(() => {
    useMailStore.setState({
      view: 'list',
      folder: 'inbox',
      filters: {
        folder: 'inbox',
        date_from: null,
        date_to: null,
        sender: null,
        keyword: null,
        unread: null,
        page_token: null,
        limit: 25,
      },
      filteredEmailIds: null,
    });
  });

  it('executes UI actions sequentially and updates the store', async () => {
    const p1 = uiActionExecutor.enqueue({
      action: 'set_filters',
      params: { sender: 'manager@company.com' },
    });

    const p2 = uiActionExecutor.enqueue({
      action: 'show_results',
      params: { email_ids: ['id_101', 'id_102'] },
    });

    const p3 = uiActionExecutor.enqueue({
      action: 'navigate',
      params: { view: 'compose' },
    });

    const p4 = uiActionExecutor.enqueue({
      action: 'fill_compose',
      params: {
        to: 'colleague@example.com',
        subject: 'Weekly standup notes',
        body: 'Here is the summary of today.',
      },
    });

    await Promise.all([p1, p2, p3, p4]);

    const state = useMailStore.getState();
    expect(state.filters.sender).toBe('manager@company.com');
    expect(state.filteredEmailIds).toEqual(['id_101', 'id_102']);
    expect(state.view).toBe('compose');
    expect(state.draft.to).toBe('colleague@example.com');
    expect(state.draft.subject).toBe('Weekly standup notes');
    expect(state.draft.body).toBe('Here is the summary of today.');
  });
});
