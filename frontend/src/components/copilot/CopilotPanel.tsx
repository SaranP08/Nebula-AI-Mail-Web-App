import React, { useEffect, useRef, useState } from 'react';
import { useMailStore } from '@/store/useMailStore';
import { streamAssistantChat } from '@/services/assistantApi';
import type { AssistantMessage, ConfirmSendProposal, EmailSummary } from '@/types';
import {
  ArrowResetRegular,
  ArrowRightRegular,
  BotRegular,
  DismissRegular,
  MailRegular,
  SparkleRegular,
} from '@fluentui/react-icons';
import styles from './CopilotPanel.module.css';

export const CopilotPanel: React.FC = () => {
  const assistantOpen = useMailStore(s => s.assistantOpen);
  const toggleAssistant = useMailStore(s => s.toggleAssistant);
  const openEmailId = useMailStore(s => s.openEmailId);
  const openEmail = useMailStore(s => s.openEmail);
  const sendDraft = useMailStore(s => s.sendDraft);
  const setView = useMailStore(s => s.setView);
  const showToast = useMailStore(s => s.showToast);
  const getUIState = useMailStore(s => s.getUIState);

  const [messages, setMessages] = useState<AssistantMessage[]>([]);
  const [inputText, setInputText] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);

  const chatEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isStreaming]);

  // Listen for sent mail event (triggered from either confirmation card or compose form)
  useEffect(() => {
    const handleMailSent = () => {
      setMessages(prev =>
        prev.map(m =>
          m.confirmSend
            ? {
                ...m,
                confirmSend: null,
                content: (m.content ? m.content + '\n\n' : '') + '✓ Email sent confirmed by user.',
              }
            : m
        )
      );
    };
    window.addEventListener('mail:sent', handleMailSent);
    return () => window.removeEventListener('mail:sent', handleMailSent);
  }, []);

  if (!assistantOpen) return null;

  const handleResetChat = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    setMessages([]);
    setIsStreaming(false);
  };

  const getToolDisplayName = (name: string, args: Record<string, any>): string => {
    switch (name) {
      case 'search_emails':
        return args.keyword
          ? `Searching emails for "${args.keyword}"...`
          : args.sender
          ? `Searching emails from ${args.sender}...`
          : 'Searching emails...';
      case 'get_email':
        return 'Reading email content...';
      case 'set_filters':
        return 'Filtering main list...';
      case 'clear_filters':
        return 'Clearing list filters...';
      case 'show_results':
        return 'Updating inbox view with results...';
      case 'open_email':
        return 'Opening email in reading pane...';
      case 'navigate':
        return `Navigating to ${args.view || 'view'}...`;
      case 'open_compose':
        return 'Opening compose draft...';
      case 'fill_compose':
        return 'Drafting email in compose form...';
      case 'propose_send':
        return 'Preparing send confirmation...';
      default:
        return 'Processing...';
    }
  };

  const handleSendMessage = async (textToSend?: string) => {
    const prompt = (textToSend || inputText).trim();
    if (!prompt || isStreaming) return;

    setInputText('');
    const userMsgId = `user_${Date.now()}`;
    const assistantMsgId = `assistant_${Date.now()}`;

    const userMsg: AssistantMessage = {
      id: userMsgId,
      role: 'user',
      content: prompt,
    };

    const initialAssistantMsg: AssistantMessage = {
      id: assistantMsgId,
      role: 'assistant',
      content: '',
      toolStatus: 'Thinking...',
    };

    const updatedMessages = [...messages, userMsg];
    setMessages([...updatedMessages, initialAssistantMsg]);
    setIsStreaming(true);

    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    const uiState = getUIState();

    // Map conversation messages for backend
    const apiMessages = updatedMessages.map(m => ({
      role: m.role,
      content: m.content,
    }));

    await streamAssistantChat(
      apiMessages,
      uiState,
      {
        onTextDelta: (delta: string) => {
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantMsgId ? { ...m, content: m.content + delta, toolStatus: undefined } : m
            )
          );
        },
        onToolCall: (name: string, args: Record<string, any>) => {
          const statusText = getToolDisplayName(name, args);
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantMsgId ? { ...m, toolStatus: statusText } : m
            )
          );
        },
        onUIAction: () => {
          // Actions are dispatched directly to the executor in streamAssistantChat
        },
        onEmailCards: (cards: EmailSummary[]) => {
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantMsgId ? { ...m, cards } : m
            )
          );
        },
        onConfirmSend: (proposal: ConfirmSendProposal) => {
          const currentDraft = useMailStore.getState().draft;
          const resolvedProposal: ConfirmSendProposal = {
            to: proposal.to || currentDraft.to || '(None)',
            subject: proposal.subject || currentDraft.subject || '(No subject)',
            bodyPreview: proposal.bodyPreview || currentDraft.body.slice(0, 300) || '(No content)',
          };
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantMsgId ? { ...m, confirmSend: resolvedProposal, toolStatus: undefined } : m
            )
          );
        },
        onError: (err: string) => {
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantMsgId
                ? {
                    ...m,
                    content: m.content ? `${m.content}\n\n⚠️ ${err}` : `⚠️ ${err}`,
                    toolStatus: undefined,
                  }
                : m
            )
          );
          setIsStreaming(false);
          abortControllerRef.current = null;
        },
        onDone: () => {
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantMsgId ? { ...m, toolStatus: undefined } : m
            )
          );
          setIsStreaming(false);
          abortControllerRef.current = null;
        },
      },
      abortController.signal
    );
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleConfirmSendAction = async (msgId: string, action: 'send' | 'edit' | 'cancel') => {
    if (action === 'send') {
      try {
        await sendDraft();
      } catch (err: any) {
        showToast(`Failed to send: ${err?.message || 'Error'}`);
      }
    } else if (action === 'edit') {
      setView('compose');
    } else if (action === 'cancel') {
      setMessages(prev =>
        prev.map(m =>
          m.id === msgId ? { ...m, confirmSend: null } : m
        )
      );
    }
  };

  // Suggestion chips
  const suggestions = [
    { label: 'Show unread from this week', prompt: 'Show unread emails from this week' },
    ...(openEmailId
      ? [
          { label: 'Summarize this email', prompt: 'Summarize the currently open email' },
          { label: 'Reply to this email', prompt: 'Reply to this email thanking them' },
        ]
      : [
          { label: 'Find emails from last 7 days', prompt: 'Show emails from the last 7 days' },
          { label: 'Draft a quick check-in', prompt: 'Compose a new draft asking for an update' },
        ]),
  ];

  return (
    <aside className={styles.panel} aria-label="Copilot AI assistant">
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <div className={styles.copilotBadge}>
            <SparkleRegular fontSize={16} />
          </div>
          <span className={styles.title}>Mail AI</span>
        </div>
        <div className={styles.headerActions}>
          <button
            id="reset-copilot-btn"
            className={styles.iconBtn}
            onClick={handleResetChat}
            title="Reset conversation"
            aria-label="Reset conversation"
          >
            <ArrowResetRegular fontSize={16} />
          </button>
          <button
            id="close-copilot-btn"
            className={styles.iconBtn}
            onClick={toggleAssistant}
            title="Close Mail AI"
            aria-label="Close Copilot panel"
          >
            <DismissRegular fontSize={16} />
          </button>
        </div>
      </div>

      {/* Chat messages */}
      <div className={styles.chatArea}>
        {messages.length === 0 ? (
          <div className={styles.welcome}>
            <div className={styles.welcomeIcon}>
              <BotRegular fontSize={28} />
            </div>
            <h2 className={styles.welcomeTitle}>Mail AI</h2>
            <p className={styles.welcomeText}>
              I can control the mail app for you. Ask me to find emails, change filters,
              open messages, or draft replies.
            </p>
          </div>
        ) : (
          messages.map(msg => (
            <div key={msg.id} className={styles.messageRow}>
              {/* Tool activity chip */}
              {msg.toolStatus && (
                <div className={styles.toolChip}>
                  <div className={styles.toolDot} />
                  <span>{msg.toolStatus}</span>
                </div>
              )}

              {/* Message bubble */}
              {msg.content && (
                <div
                  className={
                    msg.role === 'user' ? styles.userMessage : styles.assistantMessage
                  }
                >
                  {msg.content}
                </div>
              )}

              {/* Rich email cards */}
              {msg.cards && msg.cards.length > 0 && (
                <div className={styles.cardsContainer} role="region" aria-label="Email search results">
                  {msg.cards.slice(0, 5).map(card => (
                    <div
                      key={card.id}
                      className={styles.emailCard}
                      onClick={() => openEmail(card.id)}
                      role="button"
                      tabIndex={0}
                      onKeyDown={e => {
                        if (e.key === 'Enter') openEmail(card.id);
                      }}
                    >
                      <div className={styles.cardHeader}>
                        <span className={styles.cardSender}>
                          {card.sender.name || card.sender.address}
                        </span>
                        <span className={styles.cardDate}>
                          {new Date(card.date).toLocaleDateString([], { month: 'short', day: 'numeric' })}
                        </span>
                      </div>
                      <div className={styles.cardSubject}>{card.subject || '(No subject)'}</div>
                      <div className={styles.cardSnippet}>{card.snippet}</div>
                    </div>
                  ))}
                </div>
              )}

              {/* Human-in-the-loop Confirm Send card */}
              {msg.confirmSend && (
                <div className={styles.confirmCard} role="alert">
                  <div className={styles.confirmTitle}>
                    <MailRegular fontSize={16} />
                    Confirm Send
                  </div>
                  <div className={styles.confirmField}>
                    <strong>To:</strong> {msg.confirmSend.to || '(None)'}
                  </div>
                  <div className={styles.confirmField}>
                    <strong>Subject:</strong> {msg.confirmSend.subject}
                  </div>
                  <div className={styles.confirmPreview}>{msg.confirmSend.bodyPreview}</div>
                  <div className={styles.confirmActions}>
                    <button
                      className={styles.confirmCancelBtn}
                      onClick={() => handleConfirmSendAction(msg.id, 'cancel')}
                    >
                      Cancel
                    </button>
                    <button
                      className={styles.confirmEditBtn}
                      onClick={() => handleConfirmSendAction(msg.id, 'edit')}
                    >
                      Edit
                    </button>
                    <button
                      className={styles.confirmSendBtn}
                      onClick={() => handleConfirmSendAction(msg.id, 'send')}
                    >
                      Send
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))
        )}
        <div ref={chatEndRef} />
      </div>

      {/* Suggestion Chips */}
      <div className={styles.suggestionContainer}>
        {suggestions.map((s, idx) => (
          <button
            key={idx}
            className={styles.chip}
            onClick={() => handleSendMessage(s.prompt)}
            disabled={isStreaming}
          >
            <SparkleRegular fontSize={12} />
            <span>{s.label}</span>
          </button>
        ))}
      </div>

      {/* Input area */}
      <div className={styles.footer}>
        <div className={styles.inputWrapper}>
          <textarea
            ref={textareaRef}
            id="copilot-input"
            className={styles.input}
            rows={1}
            placeholder={isStreaming ? 'Mail AI is working...' : 'Ask Mail AI to drive Mail AI...'}
            value={inputText}
            onChange={e => setInputText(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isStreaming}
          />
          <button
            id="send-copilot-btn"
            className={styles.sendBtn}
            onClick={() => handleSendMessage()}
            disabled={!inputText.trim() || isStreaming}
            aria-label="Send message to Copilot"
          >
            <ArrowRightRegular fontSize={16} />
          </button>
        </div>
      </div>
    </aside>
  );
};
