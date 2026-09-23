import React from 'react';
import { MailRegular, SendRegular } from '@fluentui/react-icons';
import styles from './EmptyState.module.css';

interface EmptyStateProps {
  folder: 'inbox' | 'sent';
  hasFilters: boolean;
}

export const EmptyState: React.FC<EmptyStateProps> = ({ folder, hasFilters }) => {
  const icon = folder === 'inbox'
    ? <MailRegular fontSize={48} />
    : <SendRegular fontSize={48} />;

  const title = hasFilters
    ? 'No results match your filters'
    : folder === 'inbox'
      ? 'Your inbox is empty'
      : 'No sent messages';

  const subtitle = hasFilters
    ? 'Try adjusting or clearing your filters.'
    : folder === 'inbox'
      ? 'New messages will appear here.'
      : 'Messages you send will appear here.';

  return (
    <div className={styles.empty} role="status">
      <div className={styles.icon}>{icon}</div>
      <p className={styles.title}>{title}</p>
      <p className={styles.subtitle}>{subtitle}</p>
    </div>
  );
};
