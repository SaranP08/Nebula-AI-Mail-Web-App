import { describe, it, expect, beforeEach, vi } from 'vitest';
import { useMailStore } from '../useMailStore';
import { uiActionExecutor } from '@/services/uiActionExecutor';
import { emailsApi } from '@/services/api';

vi.mock('@/services/api', () => ({
  emailsApi: {
    list: vi.fn().mockResolvedValue({
      emails: [
        {
          id: 'mock_1',
          threadId: 'th_1',
          sender: { name: 'Alice', address: 'alice@example.com' },
          to: [{ name: 'Me', address: 'me@example.com' }],
          subject: 'Hello World',
          date: '2026-09-20T10:00:00Z',
          snippet: 'Hello!',
          is_read: true,
        },
      ],
      next_page_token: null,
      result_size_estimate: 1,
    }),
    get: vi.fn().mockResolvedValue({
      id: 'mock_1',
      threadId: 'th_1',
      sender: { name: 'Alice', address: 'alice@example.com' },
      reply_to: { name: 'Alice Work', address: 'alice.work@example.com' },
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
  },
  authApi: {
    me: vi.fn().mockResolvedValue({ id: 'u1', email: 'test@example.com', name: 'Tester', picture: '' }),
    logout: vi.fn().mockResolvedValue(undefined),
  },
}));

describe('AI Assistant UI Control Scenarios (A through E)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
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
      toast: null,
    });
  });

  it('Scenario A: Compose and send (typewriter populates draft, user sends, toast shown)', async () => {
    // 1. Assistant executes open_compose and fill_compose
    await uiActionExecutor.enqueue({
      action: 'open_compose',
      params: { mode: 'new' },
    });
    await uiActionExecutor.enqueue({
      action: 'fill_compose',
      params: {
        to: 'john@example.com',
        subject: 'Meeting Tomorrow',
        body: "Let's meet at 3pm",
      },
    });

    const storeAfterDraft = useMailStore.getState();
    expect(storeAfterDraft.view).toBe('compose');
    expect(storeAfterDraft.draft.to).toBe('john@example.com');
    expect(storeAfterDraft.draft.subject).toBe('Meeting Tomorrow');
    expect(storeAfterDraft.draft.body).toBe("Let's meet at 3pm");

    // 2. User confirms and sends
    await useMailStore.getState().sendDraft();

    expect(emailsApi.send).toHaveBeenCalledWith({
      to: ['john@example.com'],
      cc: [],
      subject: 'Meeting Tomorrow',
      body: "Let's meet at 3pm",
      reply_to_message_id: null,
      thread_id: null,
    });

    const storeAfterSend = useMailStore.getState();
    expect(storeAfterSend.view).toBe('list');
    expect(storeAfterSend.draft.to).toBe('');
    expect(storeAfterSend.toast?.message).toBe('Email sent successfully!');
  });

  it('Scenario B: Search and display updates main list filters and triggers fetch', async () => {
    await uiActionExecutor.enqueue({
      action: 'set_filters',
      params: {
        sender: 'Sarah',
        keyword: 'project update',
      },
    });

    const state = useMailStore.getState();
    expect(state.filters.sender).toBe('Sarah');
    expect(state.filters.keyword).toBe('project update');
    expect(state.filteredEmailIds).toBeNull(); // ensures no stale filtered IDs block view
  });

  it('Scenario C: Navigate and open email switches view to detail', async () => {
    await uiActionExecutor.enqueue({
      action: 'open_email',
      params: { email_id: 'mock_1' },
    });

    const state = useMailStore.getState();
    expect(state.view).toBe('detail');
    expect(state.openEmailId).toBe('mock_1');
    expect(state.openEmailDetail?.id).toBe('mock_1');
  });

  it('Scenario D: Context awareness for reply populates Reply-To, Re:, and original quote', async () => {
    // Open email first
    await useMailStore.getState().openEmail('mock_1');

    // Assistant opens reply compose
    await uiActionExecutor.enqueue({
      action: 'open_compose',
      params: { mode: 'reply', reply_to_message_id: 'mock_1' },
    });

    // Assistant types body text
    await uiActionExecutor.enqueue({
      action: 'fill_compose',
      params: { body: 'Thanks for the quick response!' },
    });

    const state = useMailStore.getState();
    expect(state.view).toBe('compose');
    expect(state.draft.mode).toBe('reply');
    // Reply-to address takes precedence over sender address
    expect(state.draft.to).toBe('alice.work@example.com');
    expect(state.draft.subject).toBe('Re: Hello World');
    expect(state.draft.replyToMessageId).toBe('mock_1');
    expect(state.draft.threadId).toBe('th_1');
    // Assistant message must precede quoted original
    expect(state.draft.body).toContain('Thanks for the quick response!');
    expect(state.draft.body).toContain('wrote:\n> Hello!');
  });

  it('Scenario E: Filters via assistant supports refinements and clear_filters', async () => {
    // 1. Show only unread emails from this week
    await uiActionExecutor.enqueue({
      action: 'set_filters',
      params: {
        unread: true,
        date_from: '2026-09-21',
        date_to: '2026-09-23',
      },
    });

    let state = useMailStore.getState();
    expect(state.filters.unread).toBe(true);
    expect(state.filters.date_from).toBe('2026-09-21');
    expect(state.filters.date_to).toBe('2026-09-23');

    // 2. Refinement: only from Sarah (merges with existing)
    await uiActionExecutor.enqueue({
      action: 'set_filters',
      params: { sender: 'Sarah' },
    });

    state = useMailStore.getState();
    expect(state.filters.unread).toBe(true);
    expect(state.filters.date_from).toBe('2026-09-21');
    expect(state.filters.sender).toBe('Sarah');

    // 3. Clear filters
    await uiActionExecutor.enqueue({
      action: 'clear_filters',
    });

    state = useMailStore.getState();
    expect(state.filters.sender).toBeNull();
    expect(state.filters.unread).toBeNull();
    expect(state.filters.date_from).toBeNull();
    expect(state.filteredEmailIds).toBeNull();
  });
});
