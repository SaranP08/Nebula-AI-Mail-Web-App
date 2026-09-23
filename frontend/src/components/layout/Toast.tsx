import React from 'react';
import { useMailStore } from '@/store/useMailStore';
import { MailRegular, DismissRegular } from '@fluentui/react-icons';
import styles from './Toast.module.css';

export const Toast: React.FC = () => {
  const toast = useMailStore(s => s.toast);
  const clearToast = useMailStore(s => s.clearToast);

  if (!toast) return null;

  return (
    <div className={styles.toastContainer} role="status" aria-live="polite">
      <div className={styles.toast}>
        <div className={styles.iconWrapper}>
          <MailRegular fontSize={18} />
        </div>
        <div className={styles.message}>{toast.message}</div>
        <button
          className={styles.closeBtn}
          onClick={clearToast}
          aria-label="Close notification"
        >
          <DismissRegular fontSize={14} />
        </button>
      </div>
    </div>
  );
};
