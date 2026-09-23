import React from 'react';
import { MailRegular } from '@fluentui/react-icons';
import styles from './IconRail.module.css';

export const IconRail: React.FC = () => {
  return (
    <nav className={styles.rail} aria-label="App navigation">
      <button
        id="nav-mail-btn"
        className={`${styles.railItem} ${styles.railItemActive}`}
        aria-label="Mail"
        aria-current="page"
        title="Mail"
      >
        <MailRegular fontSize={22} />
      </button>
    </nav>
  );
};
