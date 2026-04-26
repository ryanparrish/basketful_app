import { useNavigate } from 'react-router-dom';
import { Button } from 'react-admin';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';

interface BackNavButtonProps {
  to: string;
  label: string;
}

export function BackNavButton({ to, label }: BackNavButtonProps) {
  const navigate = useNavigate();
  return (
    <Button
      label={label}
      onClick={() => navigate(to)}
      startIcon={<ArrowBackIcon />}
      sx={{ mr: 'auto' }}
    />
  );
}
