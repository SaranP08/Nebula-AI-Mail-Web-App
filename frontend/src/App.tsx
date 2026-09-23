import React, { useEffect } from 'react';
import { FluentProvider, webLightTheme, webDarkTheme } from '@fluentui/react-components';
import { useMailStore } from '@/store/useMailStore';
import { TopAppBar } from '@/components/layout/TopAppBar';
import { IconRail } from '@/components/layout/IconRail';
import { FolderPane } from '@/components/folders/FolderPane';
import { MessageListPane } from '@/components/mail-list/MessageListPane';
import { ReadingPane } from '@/components/reading-pane/ReadingPane';
import { InlineCompose } from '@/components/compose/InlineCompose';
import { CopilotPanel } from '@/components/copilot/CopilotPanel';
import { LoginPage } from '@/components/layout/LoginPage';
import { Toast } from '@/components/layout/Toast';
import styles from './App.module.css';

const AppShell: React.FC = () => {
  const view = useMailStore(s => s.view);
  const assistantOpen = useMailStore(s => s.assistantOpen);

  return (
    <div className={styles.shell}>
      <TopAppBar />
      <div className={styles.content}>
        <IconRail />
        <FolderPane />
        <MessageListPane />
        <div className={styles.mainArea}>
          {view === 'detail' && <ReadingPane />}
          {view === 'compose' && <InlineCompose />}
          {view === 'list' && (
            <div className={styles.emptyPane}>
              <div className={styles.emptyPaneContent}>
                <svg width="64" height="64" viewBox="0 0 64 64" fill="none" aria-hidden="true">
                  <rect width="64" height="64" rx="8" fill="var(--color-brand-light)" />
                  <path d="M12 22h40v4H12V22zm0 9h40v4H12v-4zm0 9h28v4H12v-4z"
                    fill="var(--color-brand)" opacity="0.8" />
                </svg>
                <p className={styles.emptyPaneText}>Select an email to read</p>
              </div>
            </div>
          )}
        </div>
        {assistantOpen && <CopilotPanel />}
      </div>
    </div>
  );
};

const App: React.FC = () => {
  const user = useMailStore(s => s.user);
  const authLoading = useMailStore(s => s.authLoading);
  const loadUser = useMailStore(s => s.loadUser);
  const theme = useMailStore(s => s.theme);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  const fluentTheme = theme === 'dark' ? webDarkTheme : webLightTheme;

  return (
    <FluentProvider theme={fluentTheme}>
      {authLoading ? (
        <div className={styles.authLoading}>
          <div className={styles.spinner} aria-label="Loading..." role="status" />
        </div>
      ) : user ? (
        <AppShell />
      ) : (
        <LoginPage />
      )}
      <Toast />
    </FluentProvider>
  );
};

export default App;
