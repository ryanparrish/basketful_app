/**
 * Login Page
 * Customer number based authentication
 */
import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  TextField,
  Button,
  Typography,
  Alert,
  CircularProgress,
  InputAdornment,
  IconButton,
} from '@mui/material';
import { Visibility, VisibilityOff, Person, Lock } from '@mui/icons-material';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../providers/AuthContext';
import { useThemeConfig } from '../../shared/theme/dynamicTheme';

interface LocationState {
  from?: { pathname: string };
}

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { login, isAuthenticated, isLoading, error, clearError } = useAuth();
  const { themeConfig } = useThemeConfig();
  
  const [customerNumber, setCustomerNumber] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const from = (location.state as LocationState)?.from?.pathname || '/products';

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      navigate(from, { replace: true });
    }
  }, [isAuthenticated, navigate, from]);

  // Clear errors when inputs change
  useEffect(() => {
    if (error) clearError();
    if (formError) setFormError(null);
  }, [customerNumber, password]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    // Validation
    if (!customerNumber.trim()) {
      setFormError('Please enter your customer number');
      return;
    }
    if (!password.trim()) {
      setFormError('Please enter your password');
      return;
    }

    try {
      await login({
        customer_number: customerNumber.trim(),
        password: password,
      });
      // Navigation handled by useEffect above
    } catch (err) {
      // Error is already set in auth context
      console.error('Login failed:', err);
    }
  };

  const toggleShowPassword = () => {
    setShowPassword(prev => !prev);
  };

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        bgcolor: 'background.default',
        p: 2,
      }}
    >
      <Card
        sx={{
          width: '100%',
          maxWidth: 400,
          mx: 'auto',
        }}
        elevation={4}
      >
        <CardContent sx={{ p: 4 }}>
          {/* Logo/App Name */}
          <Box sx={{ textAlign: 'center', mb: 4 }}>
            {themeConfig?.logo ? (
              <Box
                component="img"
                src={themeConfig.logo}
                alt={themeConfig.app_name}
                sx={{
                  maxHeight: 80,
                  maxWidth: '100%',
                  mb: 2,
                }}
              />
            ) : (
              <Typography variant="h4" component="h1" color="primary" gutterBottom>
                {themeConfig?.app_name || 'Basketful'}
              </Typography>
            )}
            <Typography variant="body2" color="text.secondary">
              Sign in to your account
            </Typography>
          </Box>

          {/* Error Messages */}
          {(error || formError) && (
            <Alert severity="error" sx={{ mb: 3 }}>
              {formError || error}
            </Alert>
          )}

          {/* Login Form */}
          <Box component="form" onSubmit={handleSubmit} noValidate>
            <TextField
              fullWidth
              id="customer-number"
              label="Customer Number"
              value={customerNumber}
              onChange={(e) => setCustomerNumber(e.target.value)}
              margin="normal"
              autoComplete="username"
              autoFocus
              disabled={isLoading}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <Person color="action" />
                  </InputAdornment>
                ),
              }}
              inputProps={{
                inputMode: 'text',
                'aria-label': 'Customer number',
              }}
            />

            <TextField
              fullWidth
              id="password"
              label="Password"
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              margin="normal"
              autoComplete="current-password"
              disabled={isLoading}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <Lock color="action" />
                  </InputAdornment>
                ),
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton
                      aria-label={showPassword ? 'Hide password' : 'Show password'}
                      onClick={toggleShowPassword}
                      edge="end"
                      disabled={isLoading}
                    >
                      {showPassword ? <VisibilityOff /> : <Visibility />}
                    </IconButton>
                  </InputAdornment>
                ),
              }}
            />

            <Button
              type="submit"
              fullWidth
              variant="contained"
              size="large"
              disabled={isLoading}
              sx={{ mt: 3, mb: 2, py: 1.5 }}
            >
              {isLoading ? (
                <CircularProgress size={24} color="inherit" />
              ) : (
                'Sign In'
              )}
            </Button>
          </Box>

          {/* Help Text */}
          <Typography
            variant="body2"
            color="text.secondary"
            align="center"
            sx={{ mt: 2 }}
          >
            Need help? Contact your program administrator.
          </Typography>
        </CardContent>
      </Card>
    </Box>
  );
};

export default LoginPage;
