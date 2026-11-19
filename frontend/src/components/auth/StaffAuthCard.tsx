/**
 * The card every signed-out staff page sits in: sign-in, forgot password,
 * set a new password.
 */
import type { ReactNode } from 'react';
import { Avatar, Box, Card, Typography } from '@mui/material';
import LockIcon from '@mui/icons-material/Lock';

interface StaffAuthCardProps {
  subtitle: string;
  children: ReactNode;
}

export const StaffAuthCard = ({ subtitle, children }: StaffAuthCardProps) => (
  <Box
    sx={{
      display: 'flex',
      flexDirection: 'column',
      minHeight: '100vh',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      p: 2,
    }}
  >
    <Card sx={{ width: '100%', maxWidth: 450, p: 3 }}>
      <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', mb: 3 }}>
        <Avatar sx={{ bgcolor: 'primary.main', mb: 2 }}>
          <LockIcon />
        </Avatar>
        <Typography component="h1" variant="h5">
          Basketful Admin
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
          {subtitle}
        </Typography>
      </Box>
      {children}
    </Card>
  </Box>
);

export default StaffAuthCard;
