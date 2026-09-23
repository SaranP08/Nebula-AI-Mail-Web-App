/**
 * Assistant API client handling Server-Sent Events (SSE) streaming
 * from POST /api/assistant/chat.
 */
import type { ConfirmSendProposal, EmailSummary, UIAction, UIState } from '@/types';
import { uiActionExecutor } from './uiActionExecutor';

export interface AssistantCallbacks {
  onTextDelta: (delta: string) => void;
  onToolCall: (name: string, args: Record<string, any>) => void;
  onUIAction: (action: UIAction) => void;
  onEmailCards: (cards: EmailSummary[]) => void;
  onConfirmSend: (proposal: ConfirmSendProposal) => void;
  onError: (error: string) => void;
  onDone: () => void;
}

export async function streamAssistantChat(
  messages: Array<{ role: string; content: string }>,
  uiState: UIState,
  callbacks: AssistantCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch('/api/assistant/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages, ui_state: uiState }),
    signal,
  });

  if (!response.ok) {
    const text = await response.text();
    callbacks.onError(`Server error (${response.status}): ${text || response.statusText}`);
    callbacks.onDone();
    return;
  }

  const reader = response.body?.getReader();
  if (!reader) {
    callbacks.onError('Streaming response body is unavailable.');
    callbacks.onDone();
    return;
  }

  const decoder = new TextDecoder('utf-8');
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      let currentEvent = 'message';

      for (let i = 0; i < lines.length; i++) {
        const line = lines[i].trim();
        if (!line) continue;

        if (line.startsWith('event:')) {
          currentEvent = line.replace('event:', '').trim();
        } else if (line.startsWith('data:')) {
          const rawData = line.replace('data:', '').trim();
          try {
            const data = JSON.parse(rawData);

            switch (currentEvent) {
              case 'text_delta':
                if (data.delta) callbacks.onTextDelta(data.delta);
                break;
              case 'tool_call':
                callbacks.onToolCall(data.name, data.args || {});
                break;
              case 'ui_action':
                // Structured UI action -> execute via sequential executor
                callbacks.onUIAction(data);
                uiActionExecutor.enqueue(data as UIAction);
                break;
              case 'email_cards':
                if (data.cards) callbacks.onEmailCards(data.cards);
                break;
              case 'confirm_send':
                callbacks.onConfirmSend(data);
                break;
              case 'error':
                callbacks.onError(data.message || 'Unknown assistant error');
                break;
              case 'done':
                callbacks.onDone();
                break;
            }
          } catch (e) {
            console.warn('[AssistantApi] Failed to parse SSE data JSON:', rawData, e);
          }
        }
      }
    }
  } catch (err: any) {
    if (err.name !== 'AbortError') {
      callbacks.onError(err.message || 'Stream connection error');
    }
  } finally {
    callbacks.onDone();
  }
}
