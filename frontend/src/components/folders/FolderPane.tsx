import React from 'react';
import { useMailStore } from '@/store/useMailStore';
import { MailRegular, SendRegular, AddRegular } from '@fluentui/react-icons';
import styles from './FolderPane.module.css';

interface FolderItemProps {
  id: string;
  icon: React.ReactNode;
  label: string;
  isActive: boolean;
  badge?: number;
  onClick: () => void;
}

const FolderItem: React.FC<FolderItemProps> = ({ id, icon, label, isActive, badge, onClick }) => (
  <button
    id={id}
    className={`${styles.folderItem} ${isActive ? styles.folderItemActive : ''}`}
    onClick={onClick}
    aria-current={isActive ? 'page' : undefined}
  >
    <span className={styles.folderIcon}>{icon}</span>
    <span className={styles.folderLabel}>{label}</span>
    {badge != null && badge > 0 && (
      <span className={styles.badge} aria-label={`${badge} unread`}>
        {badge > 99 ? '99+' : badge}
      </span>
    )}
  </button>
);

export const FolderPane: React.FC = () => {
  const folder = useMailStore(s => s.folder);
  const emails = useMailStore(s => s.emails);
  const setFolder = useMailStore(s => s.setFolder);
  const openCompose = useMailStore(s => s.openCompose);

  const unreadCount = emails.filter(e => !e.is_read).length;

  return (
    <aside className={styles.pane} aria-label="Folders">
      {/* New mail button */}
      <div className={styles.newMailWrapper}>
        <button
          id="new-mail-btn"
          className={styles.newMailButton}
          onClick={() => openCompose({ mode: 'new' })}
        >
          <AddRegular fontSize={16} />
          New mail
        </button>
      </div>

      {/* Folder list */}
      <nav className={styles.folderList} aria-label="Mail folders">
        <FolderItem
          id="folder-inbox-btn"
          icon={<MailRegular fontSize={18} />}
          label="Inbox"
          isActive={folder === 'inbox'}
          badge={unreadCount}
          onClick={() => setFolder('inbox')}
        />
        <FolderItem
          id="folder-sent-btn"
          icon={<SendRegular fontSize={18} />}
          label="Sent Items"
          isActive={folder === 'sent'}
          onClick={() => setFolder('sent')}
        />
      </nav>
    </aside>
  );
};
