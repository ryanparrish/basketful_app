/**
 * Validation Feedback Component
 * Displays cart validation errors and warnings
 */
import React from 'react';
import {
  Box,
  Alert,
  AlertTitle,
  Collapse,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  CircularProgress,
  Typography,
} from '@mui/material';
import {
  ErrorOutline,
  WarningAmber,
  CheckCircleOutline,
} from '@mui/icons-material';
import { useCartValidation } from '../../shared/hooks/useCartValidation';

interface ValidationFeedbackProps {
  showSuccess?: boolean;
  compact?: boolean;
}

export const ValidationFeedback: React.FC<ValidationFeedbackProps> = ({
  showSuccess = false,
  compact = false,
}) => {
  const {
    isValid,
    isValidating,
    errors,
    warnings,
    hasBudgetError,
    hasQuantityError,
  } = useCartValidation();

  const hasErrors = errors.length > 0;
  const hasWarnings = warnings.length > 0;

  // Group errors by type
  const budgetErrors = errors.filter(e => 
    e.type === 'budget' || e.message?.toLowerCase().includes('budget')
  );
  const quantityErrors = errors.filter(e => 
    e.type === 'quantity' || e.type === 'limit' || e.message?.toLowerCase().includes('limit')
  );
  const otherErrors = errors.filter(e => 
    !budgetErrors.includes(e) && !quantityErrors.includes(e)
  );

  if (isValidating) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, py: 1 }}>
        <CircularProgress size={16} />
        <Typography variant="body2" color="text.secondary">
          Validating cart...
        </Typography>
      </Box>
    );
  }

  if (!hasErrors && !hasWarnings) {
    if (showSuccess && isValid) {
      return (
        <Alert severity="success" icon={<CheckCircleOutline />} sx={{ mt: 1 }}>
          Cart is valid and ready for checkout
        </Alert>
      );
    }
    return null;
  }

  if (compact) {
    return (
      <Box>
        {hasErrors && (
          <Alert severity="error" sx={{ mb: 1 }}>
            {errors.length} {errors.length === 1 ? 'issue' : 'issues'} found in your cart
          </Alert>
        )}
        {hasWarnings && !hasErrors && (
          <Alert severity="warning">
            {warnings.length} {warnings.length === 1 ? 'warning' : 'warnings'}
          </Alert>
        )}
      </Box>
    );
  }

  return (
    <Box>
      {/* Budget Errors */}
      <Collapse in={hasBudgetError}>
        <Alert severity="error" sx={{ mb: 1 }}>
          <AlertTitle>Budget Exceeded</AlertTitle>
          <List dense disablePadding>
            {budgetErrors.map((error, idx) => (
              <ListItem key={`budget-${idx}`} disablePadding>
                <ListItemIcon sx={{ minWidth: 32 }}>
                  <ErrorOutline fontSize="small" color="error" />
                </ListItemIcon>
                <ListItemText
                  primary={error.message}
                  primaryTypographyProps={{ variant: 'body2' }}
                />
              </ListItem>
            ))}
          </List>
        </Alert>
      </Collapse>

      {/* Quantity/Limit Errors */}
      <Collapse in={hasQuantityError}>
        <Alert severity="error" sx={{ mb: 1 }}>
          <AlertTitle>Quantity Limits</AlertTitle>
          <List dense disablePadding>
            {quantityErrors.map((error, idx) => (
              <ListItem key={`quantity-${idx}`} disablePadding>
                <ListItemIcon sx={{ minWidth: 32 }}>
                  <ErrorOutline fontSize="small" color="error" />
                </ListItemIcon>
                <ListItemText
                  primary={error.message}
                  secondary={error.product_id ? `Product ID: ${error.product_id}` : undefined}
                  primaryTypographyProps={{ variant: 'body2' }}
                />
              </ListItem>
            ))}
          </List>
        </Alert>
      </Collapse>

      {/* Other Errors */}
      <Collapse in={otherErrors.length > 0}>
        <Alert severity="error" sx={{ mb: 1 }}>
          <AlertTitle>Cart Issues</AlertTitle>
          <List dense disablePadding>
            {otherErrors.map((error, idx) => (
              <ListItem key={`other-${idx}`} disablePadding>
                <ListItemIcon sx={{ minWidth: 32 }}>
                  <ErrorOutline fontSize="small" color="error" />
                </ListItemIcon>
                <ListItemText
                  primary={error.message}
                  primaryTypographyProps={{ variant: 'body2' }}
                />
              </ListItem>
            ))}
          </List>
        </Alert>
      </Collapse>

      {/* Warnings */}
      <Collapse in={hasWarnings}>
        <Alert severity="warning">
          <AlertTitle>Warnings</AlertTitle>
          <List dense disablePadding>
            {warnings.map((warning, idx) => (
              <ListItem key={`warning-${idx}`} disablePadding>
                <ListItemIcon sx={{ minWidth: 32 }}>
                  <WarningAmber fontSize="small" color="warning" />
                </ListItemIcon>
                <ListItemText
                  primary={warning.message}
                  primaryTypographyProps={{ variant: 'body2' }}
                />
              </ListItem>
            ))}
          </List>
        </Alert>
      </Collapse>
    </Box>
  );
};
