import React, { useEffect, useRef, useState } from 'react';
import { useMailStore } from '@/store/useMailStore';
import {
  FilterRegular,
} from '@fluentui/react-icons';
import { FilterChips, FilterPopover } from './FilterPopover';
import { EmailRow } from './EmailRow';
import { EmailSkeleton } from './EmailSkeleton';
import { EmptyState } from './EmptyState';
import styles from './MessageListPane.module.css';

export const MessageListPane: React.FC = () => {
  const folder = useMailStore(s => s.folder);
  const emails = useMailStore(s => s.emails);
  const loading = useMailStore(s => s.loading);
  const error = useMailStore(s => s.error);
  const nextPageToken = useMailStore(s => s.nextPageToken);
  const openEmailId = useMailStore(s => s.openEmailId);
  const loadEmails = useMailStore(s => s.loadEmails);
  const loadMoreEmails = useMailStore(s => s.loadMoreEmails);
  const openEmail = useMailStore(s => s.openEmail);
  const filters = useMailStore(s => s.filters);
  const filteredEmailIds = useMailStore(s => s.filteredEmailIds);
  const resultSizeEstimate = useMailStore(s => s.resultSizeEstimate);

  const displayedEmails = filteredEmailIds
    ? emails.filter(e => filteredEmailIds.includes(e.id))
    : emails;

  const [filterOpen, setFilterOpen] = useState(false);
  const filterRef = useRef<HTMLDivElement>(null);

  // Load on mount and folder/filter changes
  useEffect(() => {
    loadEmails();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Active filter count (excluding folder/limit/page_token)
  const activeFilterCount = [
    filters.date_from,
    filters.date_to,
    filters.sender,
    filters.keyword,
    filters.unread,
  ].filter(v => v !== null && v !== undefined).length;

  const hasFilters = activeFilterCount > 0;
  const folderLabel = folder === 'inbox' ? 'Inbox' : 'Sent Items';

  const handleListKeyDown = (e: React.KeyboardEvent) => {
    if (displayedEmails.length === 0) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      const currentIdx = displayedEmails.findIndex(m => m.id === openEmailId);
      const nextIdx = currentIdx < displayedEmails.length - 1 ? currentIdx + 1 : 0;
      const target = displayedEmails[nextIdx];
      if (target) {
        openEmail(target.id);
        document.getElementById(`email-row-${target.id}`)?.scrollIntoView({ block: 'nearest' });
      }
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      const currentIdx = displayedEmails.findIndex(m => m.id === openEmailId);
      const prevIdx = currentIdx > 0 ? currentIdx - 1 : displayedEmails.length - 1;
      const target = displayedEmails[prevIdx];
      if (target) {
        openEmail(target.id);
        document.getElementById(`email-row-${target.id}`)?.scrollIntoView({ block: 'nearest' });
      }
    }
  };

  return (
    <section className={styles.pane} aria-label={folderLabel}>
      {/* Pane header */}
      <div className={styles.header}>
        <div className={styles.titleWrapper}>
          <h1 className={styles.folderTitle}>{folderLabel}</h1>
          <span className={styles.resultCount} id="list-result-count">
            ({displayedEmails.length}{resultSizeEstimate > displayedEmails.length ? ` of ${resultSizeEstimate}` : ''})
          </span>
        </div>
        <div className={styles.headerActions} ref={filterRef} style={{ position: 'relative' }}>
          <button
            id="filter-btn"
            className={`${styles.filterButton} ${hasFilters ? styles.filterButtonActive : ''}`}
            onClick={() => setFilterOpen(v => !v)}
            aria-label="Filter emails"
            aria-expanded={filterOpen}
            aria-haspopup="true"
          >
            <FilterRegular fontSize={16} />
            Filter
            {activeFilterCount > 0 && (
              <span className={styles.filterBadge}>{activeFilterCount}</span>
            )}
          </button>

          {filterOpen && (
            <FilterPopover onClose={() => setFilterOpen(false)} />
          )}
        </div>
      </div>

      {/* Active filter chips */}
      <FilterChips />

      {/* Email list with keyboard navigation */}
      <div
        className={styles.listContainer}
        role="list"
        aria-label="Email list"
        tabIndex={0}
        onKeyDown={handleListKeyDown}
      >
        {loading && emails.length === 0 ? (
          // Initial loading skeletons
          Array.from({ length: 8 }).map((_, i) => (
            <EmailSkeleton key={i} />
          ))
        ) : error ? (
          <div className={styles.errorState}>
            <p>{error}</p>
            <button className={styles.retryBtn} onClick={loadEmails}>Retry</button>
          </div>
        ) : displayedEmails.length === 0 ? (
          <EmptyState folder={folder} hasFilters={hasFilters || filteredEmailIds !== null} />
        ) : (
          <>
            {displayedEmails.map(email => (
              <EmailRow
                key={email.id}
                email={email}
                isSelected={email.id === openEmailId}
                onClick={() => openEmail(email.id)}
              />
            ))}

            {/* Load more */}
            {nextPageToken && (
              <div className={styles.loadMoreWrapper}>
                <button
                  id="load-more-btn"
                  className={styles.loadMoreBtn}
                  onClick={loadMoreEmails}
                  disabled={loading}
                >
                  {loading ? 'Loading...' : 'Load more'}
                </button>
              </div>
            )}

            {/* Loading more indicator */}
            {loading && emails.length > 0 && (
              <EmailSkeleton />
            )}
          </>
        )}
      </div>
    </section>
  );
};
