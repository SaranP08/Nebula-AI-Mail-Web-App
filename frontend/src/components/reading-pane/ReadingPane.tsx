import React, { useEffect, useRef, useState } from 'react';
import DOMPurify from 'dompurify';
import { useMailStore } from '@/store/useMailStore';
import { emailsApi } from '@/services/api';
import type { ThreadMessage } from '@/types';
import {
  ArrowReplyRegular,
  ArrowReplyAllRegular,
  ArrowForwardRegular,
  MailReadRegular,
  MailUnreadRegular,
  DismissRegular,
  ChevronDownRegular,
  ChevronUpRegular,
  ChatMultipleRegular,
} from '@fluentui/react-icons';
import styles from './ReadingPane.module.css';

function getInitials(name: string): string {
  if (!name) return '?';
  return name.split(' ').slice(0, 2).map(s => s[0]?.toUpperCase() ?? '').join('');
}

const AVATAR_COLORS = [
  '#0078d4', '#2b88d8', '#107c10', '#ca5010', '#8764b8',
  '#00b7c3', '#c43ba8', '#d13438', '#e3008c', '#038387',
];

function getAvatarColor(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}

function formatFullDate(isoString: string): string {
  if (!isoString) return '';
  try {
    return new Date(isoString).toLocaleString([], {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return isoString;
  }
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// Sandboxed iframe for safe HTML rendering
const SafeBodyViewer: React.FC<{ html: string; plain: string }> = ({ html, plain }) => {
  const iframeRef = useRef<HTMLIFrameElement>(null);

  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe) return;

    const sanitized = html
      ? DOMPurify.sanitize(html, {
          FORCE_BODY: true,
          ADD_ATTR: ['target'],
        })
      : `<pre style="font-family: inherit; white-space: pre-wrap; word-break: break-word;">${
          (plain || '').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        }</pre>`;

    const doc = iframe.contentDocument;
    if (doc) {
      doc.open();
      doc.write(`<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  * { box-sizing: border-box; }
  body {
    font-family: -apple-system, 'Segoe UI', system-ui, sans-serif;
    font-size: 14px;
    line-height: 1.6;
    color: #201f1e;
    margin: 0;
    padding: 0;
    word-break: break-word;
    overflow-wrap: break-word;
  }
  a { color: #0078d4; }
  img { max-width: 100%; height: auto; }
  blockquote {
    border-left: 3px solid #d2d0ce;
    margin: 0;
    padding-left: 12px;
    color: #605e5c;
  }
  pre { overflow-x: auto; }
</style>
</head>
<body>${sanitized}</body>
</html>`);
      doc.close();

      const resize = () => {
        if (iframe.contentDocument?.body) {
          iframe.style.height = `${iframe.contentDocument.body.scrollHeight + 24}px`;
        }
      };
      setTimeout(resize, 100);
    }
  }, [html, plain]);

  return (
    <iframe
      ref={iframeRef}
      title="Email body"
      sandbox="allow-same-origin"
      className={styles.bodyFrame}
      referrerPolicy="no-referrer"
    />
  );
};

export const ReadingPane: React.FC = () => {
  const view = useMailStore(s => s.view);
  const openEmail = useMailStore(s => s.openEmailDetail);
  const detailLoading = useMailStore(s => s.detailLoading);
  const detailError = useMailStore(s => s.detailError);
  const closeEmail = useMailStore(s => s.closeEmail);
  const openCompose = useMailStore(s => s.openCompose);
  const markRead = useMailStore(s => s.markRead);
  const markUnread = useMailStore(s => s.markUnread);

  // Conversation thread state
  const [threadMessages, setThreadMessages] = useState<ThreadMessage[]>([]);
  const [expandedMessageIds, setExpandedMessageIds] = useState<Set<string>>(new Set());

  // Fetch conversation thread whenever openEmail changes
  useEffect(() => {
    if (openEmail?.threadId) {
      emailsApi
        .getThread(openEmail.threadId)
        .then(res => {
          if (res?.messages && res.messages.length > 0) {
            setThreadMessages(res.messages);
            // By default expand the latest message (last in list)
            const latest = res.messages[res.messages.length - 1];
            setExpandedMessageIds(new Set([latest.id]));
          } else {
            setThreadMessages([]);
          }
        })
        .catch(() => {
          setThreadMessages([]);
        });
    } else {
      setThreadMessages([]);
      setExpandedMessageIds(new Set());
    }
  }, [openEmail?.id, openEmail?.threadId]);

  if (view !== 'detail') return null;

  if (detailLoading) {
    return (
      <div className={styles.pane}>
        <div className={styles.loadingState}>
          <div className={`${styles.skelTitle} skeleton`} />
          <div className={styles.skelMeta}>
            <div className={`${styles.skelAvatar} skeleton`} />
            <div className={styles.skelMetaContent}>
              <div className={`${styles.skelLine} skeleton`} style={{ width: '40%' }} />
              <div className={`${styles.skelLine} skeleton`} style={{ width: '60%' }} />
            </div>
          </div>
          <div className={`${styles.skelLine} skeleton`} style={{ width: '100%', marginTop: 16 }} />
          <div className={`${styles.skelLine} skeleton`} style={{ width: '90%' }} />
          <div className={`${styles.skelLine} skeleton`} style={{ width: '80%' }} />
          <div className={`${styles.skelLine} skeleton`} style={{ width: '95%' }} />
        </div>
      </div>
    );
  }

  if (detailError) {
    return (
      <div className={styles.pane}>
        <div className={styles.errorState}>
          <p>{detailError}</p>
        </div>
      </div>
    );
  }

  if (!openEmail) return null;

  const email = openEmail;
  const senderName = email.sender.name || email.sender.address;
  const initials = getInitials(senderName);
  const avatarColor = getAvatarColor(senderName);

  const toStr = email.to.map(a => (a.name ? `${a.name} <${a.address}>` : a.address)).join(', ');
  const ccStr = email.cc.map(a => (a.name ? `${a.name} <${a.address}>` : a.address)).join(', ');

  const handleReplyToMessage = (targetMsg: { id: string; sender: { address: string; name?: string }; date: string; body_plain?: string; snippet?: string }) => {
    const dateLabel = formatFullDate(targetMsg.date);
    const targetSender = targetMsg.sender.name || targetMsg.sender.address;
    const quote = (targetMsg.body_plain || targetMsg.snippet || '').replace(/\n/g, '\n> ');

    openCompose({
      mode: 'reply',
      to: targetMsg.sender.address,
      subject: email.subject.startsWith('Re: ') ? email.subject : `Re: ${email.subject}`,
      body: `\n\nOn ${dateLabel}, ${targetSender} wrote:\n> ${quote}`,
      replyToMessageId: targetMsg.id,
      threadId: email.threadId,
    });
  };

  const handleReplyAllToMessage = (targetMsg: { id: string; sender: { address: string; name?: string }; date: string; body_plain?: string; snippet?: string }) => {
    const allRecipients = [targetMsg.sender.address, ...email.to.map(a => a.address)].filter(
      (addr, idx, arr) => addr && arr.indexOf(addr) === idx
    );
    const dateLabel = formatFullDate(targetMsg.date);
    const targetSender = targetMsg.sender.name || targetMsg.sender.address;
    const quote = (targetMsg.body_plain || targetMsg.snippet || '').replace(/\n/g, '\n> ');

    openCompose({
      mode: 'replyAll',
      to: allRecipients.join(', '),
      cc: ccStr,
      subject: email.subject.startsWith('Re: ') ? email.subject : `Re: ${email.subject}`,
      body: `\n\nOn ${dateLabel}, ${targetSender} wrote:\n> ${quote}`,
      replyToMessageId: targetMsg.id,
      threadId: email.threadId,
    });
  };

  const handleForwardMessage = (targetMsg: { id: string; sender: { address: string; name?: string }; date: string; body_html?: string; body_plain?: string; snippet?: string }) => {
    const targetSender = targetMsg.sender.name || targetMsg.sender.address;
    openCompose({
      mode: 'forward',
      subject: email.subject.startsWith('Fwd: ') ? email.subject : `Fwd: ${email.subject}`,
      body: `\n\n---------- Forwarded message ---------\nFrom: ${targetSender} <${targetMsg.sender.address}>\nDate: ${formatFullDate(targetMsg.date)}\nSubject: ${email.subject}\n\n${targetMsg.body_plain || targetMsg.snippet || ''}`,
      threadId: email.threadId,
      replyToMessageId: targetMsg.id,
    });
  };

  const toggleMessageExpansion = (msgId: string) => {
    setExpandedMessageIds(prev => {
      const next = new Set(prev);
      if (next.has(msgId)) {
        next.delete(msgId);
      } else {
        next.add(msgId);
      }
      return next;
    });
  };

  const isThread = threadMessages.length > 1;

  return (
    <div className={styles.pane} role="main" aria-label="Email detail">
      {/* Subject Header */}
      <div className={styles.subjectRow}>
        <div style={{ display: 'flex', alignItems: 'center', minWidth: 0, flex: 1 }}>
          <h2 className={styles.subject}>{email.subject || '(No subject)'}</h2>
          {isThread && (
            <span className={styles.threadBadge}>
              <ChatMultipleRegular fontSize={14} />
              {threadMessages.length}
            </span>
          )}
        </div>
        <button
          id="close-reading-pane-btn"
          className={styles.closeBtn}
          onClick={closeEmail}
          aria-label="Close reading pane"
        >
          <DismissRegular fontSize={16} />
        </button>
      </div>

      {/* Action Toolbar */}
      <div className={styles.actionRow}>
        <button
          id="reply-btn"
          className={styles.actionBtn}
          onClick={() => handleReplyToMessage(email)}
          aria-label="Reply to email"
        >
          <ArrowReplyRegular fontSize={15} /> Reply
        </button>
        <button
          id="reply-all-btn"
          className={styles.actionBtn}
          onClick={() => handleReplyAllToMessage(email)}
          aria-label="Reply all to email"
        >
          <ArrowReplyAllRegular fontSize={15} /> Reply all
        </button>
        <button
          id="forward-btn"
          className={styles.actionBtn}
          onClick={() => handleForwardMessage(email)}
          aria-label="Forward email"
        >
          <ArrowForwardRegular fontSize={15} /> Forward
        </button>
        <div className={styles.actionSpacer} />
        {email.is_read ? (
          <button
            id="mark-unread-btn"
            className={styles.actionBtn}
            onClick={() => markUnread(email.id)}
            title="Mark as unread"
            aria-label="Mark as unread"
          >
            <MailUnreadRegular fontSize={15} /> Mark unread
          </button>
        ) : (
          <button
            id="mark-read-btn"
            className={styles.actionBtn}
            onClick={() => markRead(email.id)}
            title="Mark as read"
            aria-label="Mark as read"
          >
            <MailReadRegular fontSize={15} /> Mark read
          </button>
        )}
      </div>

      {/* Main Body: Conversation Stack OR Single Message */}
      <div className={styles.bodyWrapper}>
        {isThread ? (
          <div className={styles.threadStack} role="feed" aria-label="Conversation history">
            {threadMessages.map((msg, index) => {
              const isExpanded = expandedMessageIds.has(msg.id);
              const msgSenderName = msg.sender.name || msg.sender.address;
              const msgInitials = getInitials(msgSenderName);
              const msgAvatarColor = getAvatarColor(msgSenderName);
              const isLast = index === threadMessages.length - 1;

              return (
                <article
                  key={msg.id}
                  className={`${styles.threadCard} ${!isExpanded ? styles.threadCardCollapsed : ''}`}
                >
                  {/* Collapsible header */}
                  <div
                    className={styles.threadCardHeader}
                    onClick={() => toggleMessageExpansion(msg.id)}
                    role="button"
                    tabIndex={0}
                    aria-expanded={isExpanded}
                    onKeyDown={e => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        toggleMessageExpansion(msg.id);
                      }
                    }}
                  >
                    <div className={styles.threadCardHeaderLeft}>
                      <div
                        className={styles.threadSenderAvatar}
                        style={{ background: msgAvatarColor }}
                        aria-hidden="true"
                      >
                        {msgInitials}
                      </div>
                      <span className={styles.threadSenderName}>{msgSenderName}</span>
                      {!isExpanded && (
                        <span className={styles.threadSnippet}>{msg.snippet}</span>
                      )}
                    </div>
                    <div className={styles.threadCardHeaderRight}>
                      <span className={styles.threadDate}>{formatFullDate(msg.date)}</span>
                      <span className={styles.threadExpandIcon}>
                        {isExpanded ? <ChevronUpRegular fontSize={14} /> : <ChevronDownRegular fontSize={14} />}
                      </span>
                    </div>
                  </div>

                  {/* Expanded Body */}
                  {isExpanded && (
                    <div className={styles.threadCardBody}>
                      <SafeBodyViewer html={msg.body_html} plain={msg.body_plain} />

                      <div style={{ display: 'flex', gap: 6, marginTop: 12, borderTop: '1px solid var(--color-border-light)', paddingTop: 8 }}>
                        <button
                          className={styles.actionBtn}
                          onClick={() => handleReplyToMessage(msg)}
                          aria-label={`Reply to ${msgSenderName}`}
                        >
                          <ArrowReplyRegular fontSize={14} /> Reply
                        </button>
                        <button
                          className={styles.actionBtn}
                          onClick={() => handleReplyAllToMessage(msg)}
                          aria-label={`Reply all to ${msgSenderName}`}
                        >
                          <ArrowReplyAllRegular fontSize={14} /> Reply all
                        </button>
                        <button
                          className={styles.actionBtn}
                          onClick={() => handleForwardMessage(msg)}
                          aria-label={`Forward message from ${msgSenderName}`}
                        >
                          <ArrowForwardRegular fontSize={14} /> Forward
                        </button>
                      </div>
                    </div>
                  )}
                </article>
              );
            })}
          </div>
        ) : (
          /* Single message view */
          <>
            <div className={styles.metaRow}>
              <div
                className={styles.senderAvatar}
                style={{ background: avatarColor }}
                aria-hidden="true"
              >
                {initials}
              </div>
              <div className={styles.metaContent}>
                <div className={styles.senderRow}>
                  <span className={styles.senderName}>{senderName}</span>
                  <span className={styles.senderEmail}>&lt;{email.sender.address}&gt;</span>
                </div>
                {toStr && (
                  <div className={styles.recipients}>
                    <span className={styles.recipientLabel}>To:</span>
                    <span className={styles.recipientValue}>{toStr}</span>
                  </div>
                )}
                {ccStr && (
                  <div className={styles.recipients}>
                    <span className={styles.recipientLabel}>Cc:</span>
                    <span className={styles.recipientValue}>{ccStr}</span>
                  </div>
                )}
              </div>
              <span className={styles.date}>{formatFullDate(email.date)}</span>
            </div>

            <SafeBodyViewer html={email.body_html} plain={email.body_plain} />
          </>
        )}
      </div>

      {/* Attachments */}
      {email.attachments && email.attachments.length > 0 && (
        <div className={styles.attachments}>
          <p className={styles.attachmentsLabel}>Attachments ({email.attachments.length})</p>
          <div className={styles.attachmentList}>
            {email.attachments.map(att => (
              <div key={att.attachment_id} className={styles.attachment}>
                <span className={styles.attachmentName}>{att.filename}</span>
                <span className={styles.attachmentSize}>{formatBytes(att.size)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
