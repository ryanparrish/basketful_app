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
import { useTranslation } from 'react-i18next';
import { useCartValidation } from '../../shared/hooks/useCartValidation';
import type { ValidationError } from '../../shared/types/api';

interface ValidationFeedbackProps {
  showSuccess?: boolean;
  compact?: boolean;
}

export const ValidationFeedback: React.FC<ValidationFeedbackProps> = ({
  showSuccess = false,
  compact = false,
}) => {
  const { t } = useTranslation();
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

  // Server messages arrive already translated; only the frontend-synthesized
  // 'system' error carries no message and is translated here
  const displayMessage = (violation: ValidationError) =>
    violation.type === 'system' ? t('validation.systemError') : violation.message;

  // Bucket by the backend's machine-readable type, never by message text
  const budgetErrors = errors.filter(e => e.type === 'balance');
  const quantityErrors = errors.filter(e => e.type === 'limit');
  const otherErrors = errors.filter(e => e.type !== 'balance' && e.type !== 'limit');

  if (isValidating) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, py: 1 }}>
        <CircularProgress size={16} />
        <Typography variant="body2" color="text.secondary">
          {t('validation.validating')}
        </Typography>
      </Box>
    );
  }

  if (!hasErrors && !hasWarnings) {
    if (showSuccess && isValid) {
      return (
        <Alert severity="success" icon={<CheckCircleOutline />} sx={{ mt: 1 }}>
          {t('validation.cartValid')}
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
            {t('validation.issuesFound', { count: errors.length })}
          </Alert>
        )}
        {hasWarnings && !hasErrors && (
          <Alert severity="warning">
            {t('validation.warningCount', { count: warnings.length })}
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
          <AlertTitle>{t('validation.budgetExceeded')}</AlertTitle>
          <List dense disablePadding>
            {budgetErrors.map((error, idx) => (
              <ListItem key={`budget-${idx}`} disablePadding>
                <ListItemIcon sx={{ minWidth: 32 }}>
                  <ErrorOutline fontSize="small" color="error" />
                </ListItemIcon>
                <ListItemText
                  primary={displayMessage(error)}
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
          <AlertTitle>{t('validation.quantityLimits')}</AlertTitle>
          <List dense disablePadding>
            {quantityErrors.map((error, idx) => (
              <ListItem key={`quantity-${idx}`} disablePadding>
                <ListItemIcon sx={{ minWidth: 32 }}>
                  <ErrorOutline fontSize="small" color="error" />
                </ListItemIcon>
                <ListItemText
                  primary={displayMessage(error)}
                  secondary={error.product_id ? t('validation.productId', { id: error.product_id }) : undefined}
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
          <AlertTitle>{t('validation.cartIssues')}</AlertTitle>
          <List dense disablePadding>
            {otherErrors.map((error, idx) => (
              <ListItem key={`other-${idx}`} disablePadding>
                <ListItemIcon sx={{ minWidth: 32 }}>
                  <ErrorOutline fontSize="small" color="error" />
                </ListItemIcon>
                <ListItemText
                  primary={displayMessage(error)}
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
          <AlertTitle>{t('validation.warningsTitle')}</AlertTitle>
          <List dense disablePadding>
            {warnings.map((warning, idx) => (
              <ListItem key={`warning-${idx}`} disablePadding>
                <ListItemIcon sx={{ minWidth: 32 }}>
                  <WarningAmber fontSize="small" color="warning" />
                </ListItemIcon>
                <ListItemText
                  primary={displayMessage(warning)}
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
