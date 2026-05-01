/**
 * ProgramFilterSidebar
 *
 * An always-visible program filter rail for the OrderList.
 * Inspired by Gmail's label sidebar: one click = instant drill-down,
 * no dropdowns, no form submission required.
 *
 * Filter param: `account__participant__program` (integer ID).
 */
import { useGetList, useListContext } from 'react-admin';
import {
  Box,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  ListSubheader,
  Skeleton,
  Tooltip,
  Typography,
} from '@mui/material';
import FilterListIcon from '@mui/icons-material/FilterList';

/** Shape returned by /api/v1/programs/ */
interface Program {
  id: number;
  name: string;
}

/** The filter key sent to the backend queryset. */
const FILTER_KEY = 'account__participant__program';

// ---------------------------------------------------------------------------
// Sub-component: a single program row
// ---------------------------------------------------------------------------
interface ProgramRowProps {
  program: Program;
  isSelected: boolean;
  onSelect: (id: number | null) => void;
}

const ProgramRow = ({ program, isSelected, onSelect }: ProgramRowProps) => (
  <ListItem disablePadding>
    <Tooltip title={`Show all orders for "${program.name}"`} placement="right" arrow>
      <ListItemButton
        selected={isSelected}
        onClick={() => onSelect(isSelected ? null : program.id)}
        sx={{
          borderRadius: 1,
          mx: 0.5,
          px: 1.5,
          py: 0.75,
          '&.Mui-selected': {
            bgcolor: 'primary.light',
            color: 'primary.contrastText',
            '&:hover': { bgcolor: 'primary.main' },
          },
        }}
      >
        <ListItemText
          primary={program.name}
          primaryTypographyProps={{
            variant: 'body2',
            fontWeight: isSelected ? 600 : 400,
            noWrap: true,
          }}
        />
      </ListItemButton>
    </Tooltip>
  </ListItem>
);

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------
export interface ProgramFilterSidebarProps {
  /**
   * Width of the sidebar in pixels.
   * @default 200
   */
  width?: number;
}

export const ProgramFilterSidebar = ({ width = 200 }: ProgramFilterSidebarProps) => {
  const { filterValues, setFilters, displayedFilters } = useListContext();

  const { data: programs, isPending, error } = useGetList<Program>('programs', {
    pagination: { page: 1, perPage: 100 },
    sort: { field: 'name', order: 'ASC' },
  });

  const selectedProgramId: number | undefined = filterValues[FILTER_KEY];

  const handleSelect = (id: number | null) => {
    const next = { ...filterValues };
    if (id === null) {
      delete next[FILTER_KEY];
    } else {
      next[FILTER_KEY] = id;
    }
    setFilters(next, displayedFilters);
  };

  return (
    <Box
      sx={{
        width,
        minWidth: width,
        borderRight: '1px solid',
        borderColor: 'divider',
        display: 'flex',
        flexDirection: 'column',
        pt: 1,
        overflowY: 'auto',
      }}
    >
      <List
        dense
        subheader={
          <ListSubheader
            component="div"
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 0.75,
              lineHeight: '36px',
              fontSize: '0.7rem',
              fontWeight: 700,
              textTransform: 'uppercase',
              letterSpacing: '0.08em',
              color: 'text.secondary',
            }}
          >
            <FilterListIcon sx={{ fontSize: 14 }} />
            Programs
          </ListSubheader>
        }
      >
        {/* "All programs" clear-filter row */}
        <ListItem disablePadding>
          <ListItemButton
            selected={selectedProgramId === undefined}
            onClick={() => handleSelect(null)}
            sx={{
              borderRadius: 1,
              mx: 0.5,
              px: 1.5,
              py: 0.75,
              '&.Mui-selected': {
                bgcolor: 'action.selected',
              },
            }}
          >
            <ListItemText
              primary="All Programs"
              primaryTypographyProps={{
                variant: 'body2',
                fontWeight: selectedProgramId === undefined ? 600 : 400,
                fontStyle: 'italic',
              }}
            />
          </ListItemButton>
        </ListItem>

        {/* Loading skeletons */}
        {isPending &&
          Array.from({ length: 5 }).map((_, i) => (
            <ListItem key={i} sx={{ px: 2, py: 0.5 }}>
              <Skeleton variant="text" width="80%" height={24} />
            </ListItem>
          ))}

        {/* Error state */}
        {error && (
          <ListItem>
            <Typography variant="caption" color="error" sx={{ px: 1 }}>
              Failed to load programs
            </Typography>
          </ListItem>
        )}

        {/* Program rows */}
        {programs?.map((program) => (
          <ProgramRow
            key={program.id}
            program={program}
            isSelected={selectedProgramId === program.id}
            onSelect={handleSelect}
          />
        ))}
      </List>
    </Box>
  );
};
