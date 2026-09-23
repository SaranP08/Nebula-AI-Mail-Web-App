import React from 'react';
import { useMailStore } from '@/store/useMailStore';
import type { EmailSummary } from '@/types';
import styles from './EmailRow.module.css';

function getInitials(name: string): string {
  if (!name) return '?';
  return name
    .split(' ')
    .slice(0, 2)
    .map(s => s[0]?.toUpperCase() ?? '')
    .join('');
}

function formatDate(isoString: string): string {
  if (!isoString) return '';
  try {
    const date = new Date(isoString);
    const now = new Date();
    const isToday =
      date.getDate() === now.getDate() &&
      date.getMonth() === now.getMonth() &&
      date.getFullYear() === now.getFullYear();

    if (isToday) {
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    const isThisYear = date.getFullYear() === now.getFullYear();
    if (isThisYear) {
      return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
    }

    return date.toLocaleDateString([], { month: 'short', day: 'numeric', year: '2-digit' });
  } catch {
    return isoString;
  }
}

// Deterministic avatar color based on name
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

interface EmailRowProps {
  email: EmailSummary;
  isSelected: boolean;
  onClick: () => void;
}

export const EmailRow: React.FC<EmailRowProps> = ({ email, isSelected, onClick }) => {
  const isHighlighted = useMailStore(s => s.highlightedEmailIds.includes(email.id));
  const senderName = email.sender.name || email.sender.address || 'Unknown';
  const initials = getInitials(senderName);
  const avatarColor = getAvatarColor(senderName);
  const isUnread = !email.is_read;
  const dateLabel = formatDate(email.date);

  return (
    <div
      id={`email-row-${email.id}`}
      className={[
        styles.row,
        isUnread ? styles.rowUnread : '',
        isSelected ? styles.rowSelected : '',
        isHighlighted ? styles.rowHighlighted : '',
      ].join(' ')}
      onClick={onClick}
      role="listitem"
      aria-selected={isSelected}
      aria-label={`${isUnread ? 'Unread: ' : ''}${senderName}: ${email.subject}`}
      tabIndex={0}
      onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') onClick(); }}
    >
      {/* Unread accent bar */}
      {isUnread && <div className={styles.unreadAccent} aria-hidden="true" />}

      {/* Avatar */}
      <div
        className={styles.avatar}
        style={{ background: avatarColor }}
        aria-hidden="true"
      >
        {initials}
      </div>

      {/* Content */}
      <div className={styles.content}>
        <div className={styles.topRow}>
          <span className={`${styles.sender} ${isUnread ? styles.senderUnread : ''}`}>
            {senderName}
          </span>
          <span className={styles.date}>{dateLabel}</span>
        </div>
        <div className={`${styles.subject} ${isUnread ? styles.subjectUnread : ''} truncate`}>
          {email.subject || '(No subject)'}
        </div>
        <div className={`${styles.snippet} truncate`}>{email.snippet}</div>
      </div>
    </div>
  );
};
