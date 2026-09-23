/**
 * Server-Sent Events (SSE) client for real-time mail updates.
 *
 * Subscribes to /api/stream using EventSource with credentials.
 * Dispatches incoming new_mail events directly into the Zustand store.
 * Handles reconnects automatically with backoff.
 */
import { useMailStore } from '@/store/useMailStore';
import type { EmailSummary } from '@/types';

class LiveStreamService {
  private eventSource: EventSource | null = null;
  private reconnectTimeout: number | null = null;
  private retryDelay = 2000;
  private isConnecting = false;

  public connect(): void {
    if (this.eventSource || this.isConnecting) return;
    this.isConnecting = true;

    try {
      // EventSource with credentials sends session cookies
      const es = new EventSource('/api/stream', { withCredentials: true });
      this.eventSource = es;

      es.onopen = () => {
        this.isConnecting = false;
        this.retryDelay = 2000;
        console.log('[SSE] Connected to real-time mail stream');
      };

      es.addEventListener('new_mail', (event: MessageEvent) => {
        try {
          const payload = JSON.parse(event.data) as { email: EmailSummary };
          if (payload?.email) {
            console.log('[SSE] Received new_mail event:', payload.email.id);
            useMailStore.getState().handleIncomingMail(payload.email);
          }
        } catch (err) {
          console.error('[SSE] Failed to parse new_mail event data:', err);
        }
      });

      es.onerror = (err) => {
        console.warn('[SSE] Stream error or connection lost:', err);
        this.disconnect();
        this.scheduleReconnect();
      };
    } catch (e) {
      console.error('[SSE] Failed to create EventSource:', e);
      this.isConnecting = false;
      this.scheduleReconnect();
    }
  }

  public disconnect(): void {
    if (this.reconnectTimeout) {
      window.clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
    this.isConnecting = false;
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimeout) return;
    // Exponential backoff up to 30s
    const delay = Math.min(this.retryDelay, 30000);
    this.retryDelay = delay * 1.5;

    this.reconnectTimeout = window.setTimeout(() => {
      this.reconnectTimeout = null;
      // Only reconnect if user is still logged in
      if (useMailStore.getState().user) {
        this.connect();
      }
    }, delay);
  }
}

export const liveStreamService = new LiveStreamService();
