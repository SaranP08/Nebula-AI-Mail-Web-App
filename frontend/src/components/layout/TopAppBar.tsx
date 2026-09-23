import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useMailStore } from '@/store/useMailStore';
import {
  SearchRegular,
  WeatherMoonRegular,
  WeatherSunnyRegular,
  PanelRightExpandRegular,
  PanelRightContractRegular,
} from '@fluentui/react-icons';
import styles from './TopAppBar.module.css';

function getInitials(name: string): string {
  return name
    .split(' ')
    .slice(0, 2)
    .map(s => s[0]?.toUpperCase() ?? '')
    .join('');
}

export const TopAppBar: React.FC = () => {
  const user = useMailStore(s => s.user);
  const theme = useMailStore(s => s.theme);
  const filters = useMailStore(s => s.filters);
  const assistantOpen = useMailStore(s => s.assistantOpen);
  const setFilters = useMailStore(s => s.setFilters);
  const setTheme = useMailStore(s => s.setTheme);
  const logout = useMailStore(s => s.logout);
  const toggleAssistant = useMailStore(s => s.toggleAssistant);

  const [searchValue, setSearchValue] = useState(filters.keyword ?? '');
  const [profileOpen, setProfileOpen] = useState(false);
  const profileRef = useRef<HTMLDivElement>(null);

  // Debounced keyword filter
  useEffect(() => {
    const timer = setTimeout(() => {
      const trimmed = searchValue.trim() || null;
      if (trimmed !== filters.keyword) {
        setFilters({ keyword: trimmed });
      }
    }, 400);
    return () => clearTimeout(timer);
  }, [searchValue, filters.keyword, setFilters]);

  // Sync search box when store keyword changes externally (e.g. from AI)
  useEffect(() => {
    setSearchValue(filters.keyword ?? '');
  }, [filters.keyword]);

  // Close profile dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (profileRef.current && !profileRef.current.contains(e.target as Node)) {
        setProfileOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      const trimmed = searchValue.trim() || null;
      setFilters({ keyword: trimmed });
    }
  }, [searchValue, setFilters]);

  return (
    <header className={styles.appBar} role="banner">
      {/* Logo / App Name */}
      <div className={styles.logo}>
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
          <rect width="20" height="20" rx="3" fill="white" fillOpacity="0.2" />
          <path d="M3 6h14v2H3V6zm0 4h14v2H3v-2zm0 4h9v2H3v-2z" fill="white" />
        </svg>
        <span className={styles.logoText}>Mail</span>
      </div>

      {/* Search */}
      <div className={styles.searchWrapper} role="search">
        <SearchRegular className={styles.searchIcon} aria-hidden="true" />
        <input
          id="mail-search"
          type="search"
          className={styles.searchInput}
          placeholder="Search mail"
          value={searchValue}
          onChange={e => setSearchValue(e.target.value)}
          onKeyDown={handleKeyDown}
          aria-label="Search mail"
          autoComplete="off"
        />
      </div>

      {/* Right controls */}
      <div className={styles.controls}>
        {/* Theme toggle */}
        <button
          id="theme-toggle-btn"
          className={styles.iconButton}
          onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}
          aria-label={theme === 'light' ? 'Switch to dark theme' : 'Switch to light theme'}
          title={theme === 'light' ? 'Dark theme' : 'Light theme'}
        >
          {theme === 'light'
            ? <WeatherMoonRegular fontSize={18} />
            : <WeatherSunnyRegular fontSize={18} />
          }
        </button>

        {/* Copilot toggle */}
        <button
          id="copilot-toggle-btn"
          className={`${styles.iconButton} ${assistantOpen ? styles.iconButtonActive : ''}`}
          onClick={toggleAssistant}
          aria-label={assistantOpen ? 'Close Copilot panel' : 'Open Copilot panel'}
          title="Copilot"
        >
          {assistantOpen
            ? <PanelRightContractRegular fontSize={18} />
            : <PanelRightExpandRegular fontSize={18} />
          }
        </button>

        {/* User avatar / profile menu */}
        {user && (
          <div className={styles.profileWrapper} ref={profileRef}>
            <button
              id="user-avatar-btn"
              className={styles.avatarButton}
              onClick={() => setProfileOpen(v => !v)}
              aria-label="Account menu"
              aria-expanded={profileOpen}
              aria-haspopup="true"
            >
              {user.picture
                ? <img src={user.picture} alt={user.name} className={styles.avatarImg} />
                : <span className={styles.avatarInitials}>{getInitials(user.name || user.email)}</span>
              }
            </button>

            {profileOpen && (
              <div className={styles.profileMenu} role="menu" aria-label="Account options">
                <div className={styles.profileHeader}>
                  <span className={styles.profileName}>{user.name}</span>
                  <span className={styles.profileEmail}>{user.email}</span>
                </div>
                <hr className={styles.profileDivider} />
                <button
                  id="logout-btn"
                  className={styles.profileMenuItem}
                  role="menuitem"
                  onClick={() => { setProfileOpen(false); logout(); }}
                >
                  Sign out
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </header>
  );
};
