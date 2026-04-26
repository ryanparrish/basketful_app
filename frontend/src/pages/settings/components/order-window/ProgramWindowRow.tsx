import { useState } from 'react';
import {
  Box,
  Chip,
  Collapse,
  Divider,
  IconButton,
  TableCell,
  TableRow,
  Tooltip,
  Typography,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import { STATUS_META } from '../../utils';
import { useCountdown } from '../../hooks/useCountdown';
import { CycleTimeline } from './CycleTimeline';
import { InlineConfigPanel } from './InlineConfigPanel';
import { ManualOverridePanel } from './ManualOverridePanel';
import type { ProgramWindowStatus } from '../../types';

export const ProgramWindowRow = ({
  program,
  onRefresh,
}: {
  program: ProgramWindowStatus;
  onRefresh: () => void;
}) => {
  const [expanded, setExpanded] = useState(false);
  const countdown = useCountdown(program.seconds_until_change);
  const meta = STATUS_META[program.window_status];

  return (
    <>
      <TableRow sx={{ '& td': { verticalAlign: 'middle' } }}>
        <TableCell sx={{ fontWeight: 500 }}>{program.program_name}</TableCell>
        <TableCell sx={{ textTransform: 'capitalize' }}>
          {program.meeting_day} {program.meeting_time.slice(0, 5)}
        </TableCell>
        <TableCell>
          <Chip
            label={meta.label}
            color={meta.color}
            size="small"
            sx={{ fontWeight: 700, letterSpacing: 0.5 }}
          />
        </TableCell>
        <TableCell sx={{ fontSize: '0.8rem', color: 'text.secondary' }}>
          {countdown && (
            <Tooltip
              title={
                program.window_status === 'open'
                  ? 'Closes in'
                  : program.window_status === 'closed'
                    ? 'Opens in'
                    : 'Changes in'
              }
            >
              <span>{countdown}</span>
            </Tooltip>
          )}
        </TableCell>
        <TableCell align="center">
          <Chip label={program.active_order_count} size="small" variant="outlined" />
        </TableCell>
        <TableCell>
          <IconButton size="small" onClick={() => setExpanded(e => !e)}>
            {expanded ? (
              <ExpandLessIcon fontSize="small" />
            ) : (
              <ExpandMoreIcon fontSize="small" />
            )}
          </IconButton>
        </TableCell>
      </TableRow>
      <TableRow>
        <TableCell
          colSpan={6}
          sx={{ p: 0, borderBottom: expanded ? undefined : 'none' }}
        >
          <Collapse in={expanded} timeout="auto" unmountOnExit>
            <Box sx={{ p: 2, bgcolor: 'action.hover' }}>
              <Typography
                variant="caption"
                sx={{ fontWeight: 600, color: 'text.secondary', display: 'block', mb: 0.5 }}
              >
                Upcoming Windows
              </Typography>
              <CycleTimeline cycles={program.cycles} />
              <Divider sx={{ my: 1.5 }} />
              <InlineConfigPanel
                programId={program.program_id}
                config={program.config}
                onSaved={onRefresh}
              />
              <Divider sx={{ my: 1.5 }} />
              <ManualOverridePanel
                programId={program.program_id}
                programName={program.program_name}
                override={program.override}
                onSaved={onRefresh}
              />
            </Box>
          </Collapse>
        </TableCell>
      </TableRow>
    </>
  );
};
