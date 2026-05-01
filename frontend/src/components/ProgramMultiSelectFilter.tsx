/**
 * ProgramMultiSelectFilter
 *
 * A dual-mode program filter for the OrderList toolbar.
 *
 * Chip-bar mode (≤ 8 programs):
 *   Shows every program as a toggleable MUI Chip. Click multiple to
 *   filter orders that belong to ANY of those programs (OR semantics).
 *   An "All" chip clears the selection.
 *
 * Autocomplete mode (> 8 programs, or when user toggles):
 *   Full MUI Autocomplete multi-select with search-as-you-type.
 *
 * A small TuneIcon button lets the user switch between modes manually.
 *
 * Filter param: `account__participant__program` (integer ID or array of IDs).
 * The backend OrderFilter uses ModelMultipleChoiceFilter which accepts both.
 */
import { useState } from 'react';
import { useGetList, useListContext } from 'react-admin';
import {
  Autocomplete,
  Box,
  Chip,
  IconButton,
  Skeleton,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import TuneIcon from '@mui/icons-material/Tune';
import FilterListIcon from '@mui/icons-material/FilterList';

// ─── Types ────────────────────────────────────────────────────────────────────

interface Program {
  id: number;
  name: string;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const FILTER_KEY = 'account__participant__program';
const CHIP_BAR_THRESHOLD = 8;

// ─── Helpers ─────────────────────────────────────────────────────────────────

/** Normalise filterValues[FILTER_KEY] → always number[] internally */
function getSelectedIds(filterValues: Record<string, unknown>): number[] {
  const raw = filterValues[FILTER_KEY];
  if (!raw) return [];
  return Array.isArray(raw) ? (raw as number[]) : [raw as number];
}

/**
 * Write back to React-Admin filterValues.
 *  0 selections → remove key (clean URL)
 *  1 selection  → scalar (single exact match, also accepted by ModelMultipleChoiceFilter)
 *  2+ selections → array (repeated query params)
 */
function buildNextFilters(
  filterValues: Record<string, unknown>,
  ids: number[]
): Record<string, unknown> {
  const next = { ...filterValues };
  if (ids.length === 0) {
    delete next[FILTER_KEY];
  } else if (ids.length === 1) {
    next[FILTER_KEY] = ids[0];
  } else {
    next[FILTER_KEY] = ids;
  }
  return next;
}

// ─── Chip-bar mode ───────────────────────────────────────────────────────────

interface ChipBarProps {
  programs: Program[];
  selectedIds: number[];
  onToggle: (id: number) => void;
  onClearAll: () => void;
}

const ChipBar = ({ programs, selectedIds, onToggle, onClearAll }: ChipBarProps) => (
  <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 0.75 }}>
    {/* "All" clear-chip */}
    <Chip
      label="All"
      size="small"
      variant={selectedIds.length === 0 ? 'filled' : 'outlined'}
      color={selectedIds.length === 0 ? 'primary' : 'default'}
      onClick={onClearAll}
      sx={{ fontWeight: selectedIds.length === 0 ? 700 : 400 }}
    />

    {programs.map((p) => {
      const active = selectedIds.includes(p.id);
      return (
        <Chip
          key={p.id}
          label={p.name}
          size="small"
          variant={active ? 'filled' : 'outlined'}
          color={active ? 'secondary' : 'default'}
          onClick={() => onToggle(p.id)}
          sx={{ fontWeight: active ? 700 : 400 }}
        />
      );
    })}
  </Box>
);

// ─── Autocomplete mode ───────────────────────────────────────────────────────

interface AutocompleteBarProps {
  programs: Program[];
  selectedIds: number[];
  isLoading: boolean;
  onChange: (ids: number[]) => void;
}

const AutocompleteBar = ({
  programs,
  selectedIds,
  isLoading,
  onChange,
}: AutocompleteBarProps) => {
  const selected = programs.filter((p) => selectedIds.includes(p.id));

  return (
    <Autocomplete<Program, true>
      multiple
      options={programs}
      loading={isLoading}
      getOptionLabel={(o) => o.name}
      isOptionEqualToValue={(o, v) => o.id === v.id}
      value={selected}
      onChange={(_, newValue) => onChange(newValue.map((p) => p.id))}
      disableCloseOnSelect
      renderTags={(value, getTagProps) =>
        value.map((p, index) => (
          <Chip
            {...getTagProps({ index })}
            key={p.id}
            label={p.name}
            size="small"
            color="secondary"
          />
        ))
      }
      renderInput={(params) => (
        <TextField
          {...params}
          label="Programs"
          size="small"
          variant="outlined"
          placeholder={selected.length === 0 ? 'All programs' : undefined}
        />
      )}
      sx={{ minWidth: 260, maxWidth: 420 }}
    />
  );
};

// ─── Main component ──────────────────────────────────────────────────────────

/**
 * Drop this into the `orderFilters` array with `alwaysOn`.
 * It must be rendered inside a React-Admin `<List>` so that
 * `useListContext` has access to `filterValues` / `setFilters`.
 */
export const ProgramMultiSelectFilter = () => {
  const { filterValues, setFilters, displayedFilters } = useListContext();

  const { data: programs = [], isPending } = useGetList<Program>('programs', {
    pagination: { page: 1, perPage: 100 },
    sort: { field: 'name', order: 'ASC' },
  });

  // Auto-select chip-bar when programs fit; autocomplete when they don't
  const [mode, setMode] = useState<'chip' | 'autocomplete' | null>(null);
  const effectiveMode =
    mode ?? (programs.length > CHIP_BAR_THRESHOLD ? 'autocomplete' : 'chip');

  const selectedIds = getSelectedIds(filterValues);

  const setSelected = (ids: number[]) => {
    setFilters(buildNextFilters(filterValues, ids), displayedFilters);
  };

  const toggleProgram = (id: number) => {
    setSelected(
      selectedIds.includes(id)
        ? selectedIds.filter((x) => x !== id)
        : [...selectedIds, id]
    );
  };

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
      {/* Label */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flexShrink: 0 }}>
        <FilterListIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
        <Typography variant="caption" color="text.secondary" fontWeight={600}>
          Program
        </Typography>
      </Box>

      {/* Loading state */}
      {isPending && (
        <Box sx={{ display: 'flex', gap: 0.75 }}>
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} variant="rounded" width={80} height={24} />
          ))}
        </Box>
      )}

      {/* Chip-bar mode */}
      {!isPending && effectiveMode === 'chip' && (
        <ChipBar
          programs={programs}
          selectedIds={selectedIds}
          onToggle={toggleProgram}
          onClearAll={() => setSelected([])}
        />
      )}

      {/* Autocomplete mode */}
      {!isPending && effectiveMode === 'autocomplete' && (
        <AutocompleteBar
          programs={programs}
          selectedIds={selectedIds}
          isLoading={isPending}
          onChange={setSelected}
        />
      )}

      {/* Mode toggle button */}
      {!isPending && programs.length > 0 && (
        <Tooltip
          title={
            effectiveMode === 'chip'
              ? 'Switch to search mode'
              : 'Switch to quick-select chips'
          }
          arrow
        >
          <IconButton
            size="small"
            onClick={() => setMode(effectiveMode === 'chip' ? 'autocomplete' : 'chip')}
            sx={{ color: 'text.secondary' }}
          >
            <TuneIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      )}
    </Box>
  );
};
