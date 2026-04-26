import { Box, Chip } from '@mui/material';
import { fmt } from '../../utils';
import type { WindowCycle } from '../../types';

export const CycleTimeline = ({ cycles }: { cycles: WindowCycle[] }) => (
  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5, mt: 1 }}>
    {cycles.map((c, i) => (
      <Box key={i} sx={{ display: 'flex', alignItems: 'center', gap: 1, fontSize: '0.78rem' }}>
        <Chip
          label={i === 0 ? 'Next' : `+${i}wk`}
          size="small"
          sx={{ minWidth: 46, fontSize: '0.7rem' }}
        />
        <Box sx={{ color: 'success.main', fontWeight: 500 }}>{fmt(c.opens_at)}</Box>
        <Box sx={{ color: 'text.disabled' }}>→</Box>
        <Box sx={{ color: 'error.main' }}>{fmt(c.closes_at)}</Box>
        <Box sx={{ color: 'text.secondary' }}>· class {fmt(c.meeting_at)}</Box>
      </Box>
    ))}
  </Box>
);
