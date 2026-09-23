import React from 'react';
import styles from './EmailSkeleton.module.css';

export const EmailSkeleton: React.FC = () => (
  <div className={styles.row} aria-hidden="true">
    <div className={`${styles.avatar} skeleton`} />
    <div className={styles.content}>
      <div className={styles.topRow}>
        <div className={`${styles.senderSkel} skeleton`} />
        <div className={`${styles.dateSkel} skeleton`} />
      </div>
      <div className={`${styles.subjectSkel} skeleton`} />
      <div className={`${styles.snippetSkel} skeleton`} />
    </div>
  </div>
);
