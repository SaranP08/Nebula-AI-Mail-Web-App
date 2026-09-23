import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useMailStore } from '@/store/useMailStore';
import type { Filters } from '@/types';
import {
  FilterRegular,
  DismissRegular,
  ChevronDownRegular,
} from '@fluentui/react-icons';
import styles from './FilterPopover.module.css';

type DatePreset = 'today' | 'last7' | 'thisWeek' | 'last30' | 'custom';

function getPresetDates(preset: DatePreset): { from: string; to: string } {
  const today = new Date();
  const fmt = (d: Date) => d.toISOString().split('T')[0];

  const startOfWeek = new Date(today);
  startOfWeek.setDate(today.getDate() - today.getDay());

  switch (preset) {
    case 'today':
      return { from: fmt(today), to: fmt(today) };
    case 'last7': {
      const d = new Date(today);
      d.setDate(d.getDate() - 7);
      return { from: fmt(d), to: fmt(today) };
    }
    case 'thisWeek':
      return { from: fmt(startOfWeek), to: fmt(today) };
    case 'last30': {
      const d = new Date(today);
      d.setDate(d.getDate() - 30);
      return { from: fmt(d), to: fmt(today) };
    }
    default:
      return { from: '', to: '' };
  }
}

interface FilterPopoverProps {
  onClose: () => void;
}

export const FilterPopover: React.FC<FilterPopoverProps> = ({ onClose }) => {
  const filters = useMailStore(s => s.filters);
  const setFilters = useMailStore(s => s.setFilters);

  const [datePreset, setDatePreset] = useState<DatePreset | null>(null);
  const [dateFrom, setDateFrom] = useState(filters.date_from ?? '');
  const [dateTo, setDateTo] = useState(filters.date_to ?? '');
  const [sender, setSender] = useState(filters.sender ?? '');
  const [keyword, setKeyword] = useState(filters.keyword ?? '');
  const [unread, setUnread] = useState<boolean | null>(filters.unread ?? null);

  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        onClose();
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [onClose]);

  const applyPreset = useCallback((preset: DatePreset) => {
    setDatePreset(preset);
    if (preset !== 'custom') {
      const { from, to } = getPresetDates(preset);
      setDateFrom(from);
      setDateTo(to);
    }
  }, []);

  const handleApply = useCallback(() => {
    const partial: Partial<Filters> = {
      date_from: dateFrom || null,
      date_to: dateTo || null,
      sender: sender.trim() || null,
      keyword: keyword.trim() || null,
      unread,
    };
    setFilters(partial);
    onClose();
  }, [dateFrom, dateTo, sender, keyword, unread, setFilters, onClose]);

  const handleClear = useCallback(() => {
    setDatePreset(null);
    setDateFrom('');
    setDateTo('');
    setSender('');
    setKeyword('');
    setUnread(null);
  }, []);

  const presets: { key: DatePreset; label: string }[] = [
    { key: 'today', label: 'Today' },
    { key: 'last7', label: 'Last 7 days' },
    { key: 'thisWeek', label: 'This week' },
    { key: 'last30', label: 'Last 30 days' },
    { key: 'custom', label: 'Custom range' },
  ];

  return (
    <div ref={ref} className={styles.popover} role="dialog" aria-label="Filter emails">
      <div className={styles.header}>
        <span className={styles.title}>Filter</span>
        <button className={styles.clearLink} onClick={handleClear}>Clear all</button>
      </div>

      {/* Date presets */}
      <div className={styles.section}>
        <label className={styles.sectionLabel}>Date</label>
        <div className={styles.presets}>
          {presets.map(p => (
            <button
              key={p.key}
              id={`filter-preset-${p.key}`}
              className={`${styles.presetBtn} ${datePreset === p.key ? styles.presetBtnActive : ''}`}
              onClick={() => applyPreset(p.key)}
            >
              {p.label}
            </button>
          ))}
        </div>
        {datePreset === 'custom' && (
          <div className={styles.dateRange}>
            <div className={styles.dateField}>
              <label className={styles.fieldLabel} htmlFor="filter-date-from">From</label>
              <input
                id="filter-date-from"
                type="date"
                className={styles.input}
                value={dateFrom}
                onChange={e => setDateFrom(e.target.value)}
              />
            </div>
            <div className={styles.dateField}>
              <label className={styles.fieldLabel} htmlFor="filter-date-to">To</label>
              <input
                id="filter-date-to"
                type="date"
                className={styles.input}
                value={dateTo}
                onChange={e => setDateTo(e.target.value)}
              />
            </div>
          </div>
        )}
      </div>

      {/* Sender */}
      <div className={styles.section}>
        <label className={styles.sectionLabel} htmlFor="filter-sender">From</label>
        <input
          id="filter-sender"
          type="text"
          className={styles.input}
          placeholder="Sender name or email"
          value={sender}
          onChange={e => setSender(e.target.value)}
        />
      </div>

      {/* Keyword */}
      <div className={styles.section}>
        <label className={styles.sectionLabel} htmlFor="filter-keyword">Keyword</label>
        <input
          id="filter-keyword"
          type="text"
          className={styles.input}
          placeholder="Search in subject or body"
          value={keyword}
          onChange={e => setKeyword(e.target.value)}
        />
      </div>

      {/* Unread toggle */}
      <div className={styles.section}>
        <label className={styles.sectionLabel}>Status</label>
        <div className={styles.toggleGroup}>
          <button
            id="filter-unread-all"
            className={`${styles.toggleBtn} ${unread === null ? styles.toggleBtnActive : ''}`}
            onClick={() => setUnread(null)}
          >All</button>
          <button
            id="filter-unread-true"
            className={`${styles.toggleBtn} ${unread === true ? styles.toggleBtnActive : ''}`}
            onClick={() => setUnread(true)}
          >Unread</button>
          <button
            id="filter-unread-false"
            className={`${styles.toggleBtn} ${unread === false ? styles.toggleBtnActive : ''}`}
            onClick={() => setUnread(false)}
          >Read</button>
        </div>
      </div>

      {/* Actions */}
      <div className={styles.actions}>
        <button className={styles.cancelBtn} onClick={onClose}>Cancel</button>
        <button id="filter-apply-btn" className={styles.applyBtn} onClick={handleApply}>Apply</button>
      </div>
    </div>
  );
};

// ── Filter chips bar ──────────────────────────────────────────────────────────

export const FilterChips: React.FC = () => {
  const filters = useMailStore(s => s.filters);
  const setFilters = useMailStore(s => s.setFilters);
  const resetFilters = useMailStore(s => s.resetFilters);

  const chips: { key: keyof Filters; label: string; value: string }[] = [];

  if (filters.date_from || filters.date_to) {
    const from = filters.date_from ?? '';
    const to = filters.date_to ?? '';
    chips.push({
      key: 'date_from',
      label: from && to ? `${from} – ${to}` : from ? `From ${from}` : `Until ${to}`,
      value: 'date_range',
    });
  }
  if (filters.sender) {
    chips.push({ key: 'sender', label: `From: ${filters.sender}`, value: filters.sender });
  }
  if (filters.keyword) {
    chips.push({ key: 'keyword', label: `"${filters.keyword}"`, value: filters.keyword });
  }
  if (filters.unread !== null && filters.unread !== undefined) {
    chips.push({ key: 'unread', label: filters.unread ? 'Unread only' : 'Read only', value: String(filters.unread) });
  }

  if (chips.length === 0) return null;

  const removeChip = (key: keyof Filters) => {
    if (key === 'date_from') {
      setFilters({ date_from: null, date_to: null });
    } else {
      setFilters({ [key]: null } as Partial<Filters>);
    }
  };

  return (
    <div className={styles.chipsBar} role="list" aria-label="Active filters">
      {chips.map(chip => (
        <span key={chip.key} className={styles.chip} role="listitem">
          <span className={styles.chipLabel}>{chip.label}</span>
          <button
            className={styles.chipRemove}
            onClick={() => removeChip(chip.key)}
            aria-label={`Remove filter: ${chip.label}`}
          >
            <DismissRegular fontSize={10} />
          </button>
        </span>
      ))}
      <button className={styles.clearAllLink} onClick={resetFilters}>Clear all</button>
    </div>
  );
};
