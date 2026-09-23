import React from 'react';
import styles from './LoginPage.module.css';

export const LoginPage: React.FC = () => {
  return (
    <div className={styles.page}>
      <div className={styles.card}>
        {/* Brand header */}
        <div className={styles.brandHeader}>
          <div className={styles.brandIcon}>
            <svg width="32" height="32" viewBox="0 0 32 32" fill="none" aria-hidden="true">
              <rect width="32" height="32" rx="6" fill="#0078d4" />
              <path d="M6 10h20v3H6V10zm0 5.5h20v3H6v-3zm0 5.5h14v3H6v-3z" fill="white" />
            </svg>
          </div>
          <span className={styles.brandName}>Mail</span>
        </div>

        <h1 className={styles.heading}>Sign in to your account</h1>
        <p className={styles.subheading}>
          Connect your Gmail to get started with the AI-powered mail experience.
        </p>

        <a
          id="google-signin-btn"
          href="/auth/login"
          className={styles.googleBtn}
        >
          {/* Google G logo */}
          <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
            <path fill="#4285F4" d="M17.64 9.205c0-.639-.057-1.252-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.875 2.684-6.616z" />
            <path fill="#34A853" d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.258c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 009 18z" />
            <path fill="#FBBC05" d="M3.964 10.71A5.41 5.41 0 013.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 000 9c0 1.452.348 2.827.957 4.042l3.007-2.332z" />
            <path fill="#EA4335" d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 00.957 4.958L3.964 7.29C4.672 5.163 6.656 3.58 9 3.58z" />
          </svg>
          Continue with Google
        </a>

        <p className={styles.disclaimer}>
          We request only read and send access to your Gmail.
          Your data is never stored beyond what is required for this session.
        </p>
      </div>
    </div>
  );
};
