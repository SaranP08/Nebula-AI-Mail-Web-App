/**
 * UI Action Executor: maps structured actions from the AI assistant to the Zustand store.
 *
 * Guarantees actions run in order using a promise queue.
 * Animates compose fields with a smooth typewriter effect so the user sees the AI typing.
 */
import { useMailStore } from '@/store/useMailStore';
import { emailsApi } from '@/services/api';
import type { UIAction } from '@/types';

class UIActionExecutor {
  private queue: Promise<void> = Promise.resolve();

  /**
   * Enqueue a UI action to be executed strictly in order.
   */
  public enqueue(action: UIAction): Promise<void> {
    this.queue = this.queue.then(async () => {
      try {
        await this.execute(action);
      } catch (err) {
        console.error('[UIActionExecutor] Failed to execute action:', action, err);
      }
    });
    return this.queue;
  }

  private async execute(action: UIAction): Promise<void> {
    const store = useMailStore.getState();

    switch (action.action) {
      case 'set_filters': {
        store.setFilters(action.params);
        break;
      }

      case 'clear_filters': {
        store.resetFilters();
        break;
      }

      case 'show_results': {
        store.setFilteredEmailIds(action.params.email_ids);
        break;
      }

      case 'open_email': {
        await store.openEmail(action.params.email_id);
        break;
      }

      case 'navigate': {
        if (action.params.folder && action.params.folder !== store.folder) {
          store.setFolder(action.params.folder);
        }
        if (action.params.view) {
          store.setView(action.params.view);
        }
        break;
      }

      case 'open_compose': {
        const mode = action.params.mode || 'new';
        let initialDraft: Record<string, any> = { mode };

        let currentDetail = store.openEmailDetail;
        const targetId = action.params.reply_to_message_id || store.openEmailId;
        if (!currentDetail && targetId) {
          try {
            currentDetail = await emailsApi.get(targetId);
          } catch {
            // fallback
          }
        } else if (currentDetail && action.params.reply_to_message_id && currentDetail.id !== action.params.reply_to_message_id) {
          try {
            currentDetail = await emailsApi.get(action.params.reply_to_message_id);
          } catch {
            // fallback
          }
        }

        if (mode === 'reply' && currentDetail) {
          const dateStr = new Date(currentDetail.date).toLocaleDateString([], {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
          });
          const senderDisplay = currentDetail.sender.name || currentDetail.sender.address;
          const quoted = (currentDetail.body_plain || currentDetail.snippet || '').replace(/\n/g, '\n> ');
          initialDraft = {
            mode: 'reply',
            to: currentDetail.reply_to?.address || currentDetail.sender.address,
            subject: currentDetail.subject.startsWith('Re:')
              ? currentDetail.subject
              : `Re: ${currentDetail.subject}`,
            body: `\n\nOn ${dateStr}, ${senderDisplay} wrote:\n> ${quoted}`,
            replyToMessageId: currentDetail.id,
            threadId: currentDetail.threadId,
          };
        } else if (mode === 'replyAll' && currentDetail) {
          const allRecipients = [
            currentDetail.reply_to?.address || currentDetail.sender.address,
            ...currentDetail.to.map(t => t.address),
          ].filter((addr, idx, arr) => addr && arr.indexOf(addr) === idx);

          const dateStr = new Date(currentDetail.date).toLocaleDateString([], {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
          });
          const senderDisplay = currentDetail.sender.name || currentDetail.sender.address;
          const quoted = (currentDetail.body_plain || currentDetail.snippet || '').replace(/\n/g, '\n> ');
          initialDraft = {
            mode: 'replyAll',
            to: allRecipients.join(', '),
            subject: currentDetail.subject.startsWith('Re:')
              ? currentDetail.subject
              : `Re: ${currentDetail.subject}`,
            body: `\n\nOn ${dateStr}, ${senderDisplay} wrote:\n> ${quoted}`,
            replyToMessageId: currentDetail.id,
            threadId: currentDetail.threadId,
          };
        } else if (mode === 'forward' && currentDetail) {
          initialDraft = {
            mode: 'forward',
            to: '',
            subject: currentDetail.subject.startsWith('Fwd:')
              ? currentDetail.subject
              : `Fwd: ${currentDetail.subject}`,
            body: `\n\n---------- Forwarded message ---------\nFrom: ${currentDetail.sender.name} <${currentDetail.sender.address}>\nDate: ${currentDetail.date}\nSubject: ${currentDetail.subject}\n\n${currentDetail.body_plain || currentDetail.snippet || ''}`,
            replyToMessageId: currentDetail.id,
            threadId: currentDetail.threadId,
          };
        }

        store.openCompose(initialDraft);
        break;
      }

      case 'fill_compose': {
        // Ensure compose view is open first
        if (useMailStore.getState().view !== 'compose') {
          useMailStore.getState().openCompose();
          await this.sleep(150);
        }

        const { to, cc, subject, body } = action.params;
        const currentDraft = useMailStore.getState().draft;

        // Sequence: To -> CC -> Subject -> Body
        if (to !== undefined) {
          await this.typeField('to', to, 12, 400);
        }
        if (cc !== undefined) {
          await this.typeField('cc', cc, 12, 400);
        }
        if (subject !== undefined) {
          await this.typeField('subject', subject, 12, 500);
        }
        if (body !== undefined) {
          // If the draft already contains a quote at the bottom, place the assistant text above the quote
          const existingBody = currentDraft.body || '';
          let targetBody = body;
          if (existingBody.includes('\n\nOn ') || existingBody.includes('---------- Forwarded message ---------')) {
            const quoteIdx = existingBody.indexOf('\n\nOn ') !== -1
              ? existingBody.indexOf('\n\nOn ')
              : existingBody.indexOf('---------- Forwarded message ---------');
            const quotePart = existingBody.slice(quoteIdx).trim();
            targetBody = `${body}\n\n${quotePart}`;
          }

          // Body typewriter: ~18ms per character, capped at 1600ms total
          await this.typeField('body', targetBody, 18, 1600);
        }
        break;
      }

      case 'propose_send': {
        // Handled in CopilotPanel through confirm_send event
        break;
      }
    }
  }

  /**
   * Animate typing text into a draft field in the Zustand store.
   */
  private async typeField(
    field: 'to' | 'cc' | 'subject' | 'body',
    fullText: string,
    msPerChar: number,
    maxDurationMs: number,
  ): Promise<void> {
    if (!fullText) {
      useMailStore.getState().updateDraft({ [field]: '' });
      return;
    }

    const isTest = Boolean(import.meta.env?.MODE === 'test');
    if (isTest) {
      useMailStore.getState().updateDraft({ [field]: fullText });
      return;
    }

    const totalChars = fullText.length;
    // Cap animation duration for long text
    const actualDelay = Math.min(msPerChar, maxDurationMs / Math.max(totalChars, 1));

    // Chunk size: for very long text, type in small chunks of chars
    const chunkSize = actualDelay < 5 ? Math.ceil(totalChars / (maxDurationMs / 10)) : 1;

    let current = '';
    for (let i = 0; i < totalChars; i += chunkSize) {
      current = fullText.slice(0, i + chunkSize);
      useMailStore.getState().updateDraft({ [field]: current });
      await this.sleep(actualDelay);
    }
    useMailStore.getState().updateDraft({ [field]: fullText });
  }

  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

export const uiActionExecutor = new UIActionExecutor();
