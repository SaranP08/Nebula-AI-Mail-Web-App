import React, { useState } from 'react';
import { useMailStore } from '@/store/useMailStore';
import { SendRegular, DismissRegular } from '@fluentui/react-icons';
import styles from './InlineCompose.module.css';

export const InlineCompose: React.FC = () => {
  const view = useMailStore(s => s.view);
  const draft = useMailStore(s => s.draft);
  const updateDraft = useMailStore(s => s.updateDraft);
  const sendDraft = useMailStore(s => s.sendDraft);
  const discardDraft = useMailStore(s => s.discardDraft);

  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const [ccExpanded, setCcExpanded] = useState(!!draft.cc);

  if (view !== 'compose') return null;

  const modeLabel = {
    new: 'New Message',
    reply: 'Reply',
    replyAll: 'Reply All',
    forward: 'Forward',
  }[draft.mode];

  const handleSend = async () => {
    if (!draft.to.trim()) {
      setSendError('Please enter at least one recipient.');
      return;
    }
    setSending(true);
    setSendError(null);
    try {
      await sendDraft();
    } catch (err: unknown) {
      const msg = (err as { message?: string })?.message ?? 'Failed to send message.';
      setSendError(msg);
      setSending(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // Ctrl+Enter or Cmd+Enter to send
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div
      className={styles.pane}
      role="main"
      aria-label="Compose message"
      onKeyDown={handleKeyDown}
    >
      {/* ── Top Command Bar (Outlook Web standard) ────────────────── */}
      <div className={styles.commandBar}>
        <div className={styles.commandBarLeft}>
          <button
            id="send-btn"
            className={styles.primarySendBtn}
            onClick={handleSend}
            disabled={sending}
            title="Send message (Ctrl+Enter)"
          >
            <SendRegular fontSize={16} />
            <span>{sending ? 'Sending...' : 'Send'}</span>
          </button>
          <button
            id="discard-compose-btn"
            className={styles.toolbarBtn}
            onClick={discardDraft}
            disabled={sending}
            title="Discard draft"
          >
            Discard
          </button>
        </div>

        <div className={styles.commandBarRight}>
          <span className={styles.modeTitle}>{modeLabel}</span>
          <button
            id="discard-btn"
            className={styles.discardIcon}
            onClick={discardDraft}
            aria-label="Discard draft"
            title="Close / Discard"
          >
            <DismissRegular fontSize={16} />
          </button>
        </div>
      </div>

      {/* ── Scrollable Compose Form ───────────────────────────────── */}
      <div className={styles.composeBody}>
        {/* To */}
        <div className={styles.field}>
          <label className={styles.fieldLabel} htmlFor="compose-to">To</label>
          <input
            id="compose-to"
            type="text"
            className={styles.fieldInput}
            placeholder="Recipients"
            value={draft.to}
            onChange={e => updateDraft({ to: e.target.value })}
            autoFocus={draft.mode === 'new'}
          />
        </div>

        {/* Cc toggle */}
        <div className={styles.field}>
          <label className={styles.fieldLabel} htmlFor="compose-cc">Cc</label>
          <div className={styles.ccRow}>
            <input
              id="compose-cc"
              type="text"
              className={styles.fieldInput}
              placeholder="Cc recipients"
              value={draft.cc}
              onChange={e => updateDraft({ cc: e.target.value })}
              style={{ display: ccExpanded ? 'block' : 'none', flex: 1 }}
            />
            {!ccExpanded && (
              <button
                className={styles.ccToggle}
                onClick={() => setCcExpanded(true)}
                aria-label="Show Cc field"
              >
                Add Cc
              </button>
            )}
          </div>
        </div>

        {/* Subject */}
        <div className={styles.field}>
          <label className={styles.fieldLabel} htmlFor="compose-subject">Subject</label>
          <input
            id="compose-subject"
            type="text"
            className={styles.fieldInput}
            placeholder="Subject"
            value={draft.subject}
            onChange={e => updateDraft({ subject: e.target.value })}
          />
        </div>

        {/* Divider */}
        <hr className={styles.divider} />

        {/* Body Textarea */}
        <textarea
          id="compose-body"
          className={styles.bodyArea}
          placeholder="Write your message... (Ctrl+Enter to send)"
          value={draft.body}
          onChange={e => updateDraft({ body: e.target.value })}
          aria-label="Message body"
        />

        {/* Error notification */}
        {sendError && (
          <div className={styles.errorMsg} role="alert">{sendError}</div>
        )}
      </div>

      {/* ── Pinned Bottom Action Bar ──────────────────────────────── */}
      <div className={styles.bottomBar}>
        <button
          id="send-btn-bottom"
          className={styles.primarySendBtn}
          onClick={handleSend}
          disabled={sending}
          title="Send message (Ctrl+Enter)"
        >
          <SendRegular fontSize={16} />
          <span>{sending ? 'Sending...' : 'Send'}</span>
        </button>
        <button
          id="discard-bottom-btn"
          className={styles.toolbarBtn}
          onClick={discardDraft}
          disabled={sending}
          title="Discard draft"
        >
          Discard
        </button>
      </div>
    </div>
  );
};
