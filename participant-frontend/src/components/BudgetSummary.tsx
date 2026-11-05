/**
 * What's left in each of the participant's balances (food, hygiene, Go Fresh),
 * live as the cart changes. Used everywhere a balance is shown so the sider,
 * cart, checkout and mobile cart bar can never disagree.
 */
import React from 'react';
import { Box, Stack, Typography } from '@mui/material';
import { useTranslation } from 'react-i18next';
import { useBudgets } from '../shared/hooks/useBudgets';
import { useFormatters } from '../shared/hooks/useFormatters';
import type { BudgetKey } from '../shared/types/api';

interface BudgetSummaryProps {
  /** 'list' = one row per balance; 'inline' = single line for tight spaces (mobile bar, sider). */
  variant?: 'list' | 'inline';
  /** Text color for the inline variant when it sits on a colored background. */
  color?: string;
}

export const BudgetSummary: React.FC<BudgetSummaryProps> = ({ variant = 'list', color }) => {
  const { t } = useTranslation();
  const { formatCurrency } = useFormatters();
  const budgets = useBudgets();

  if (!budgets) return null;

  // The food balance is the voucher total and pays for the whole cart, so
  // it reads as what's left to spend; the caps read as "<name> left"
  const label = (key: BudgetKey) =>
    key === 'food' ? t('budget.leftToSpend') : t('budget.left', { name: t(`budget.${key}`) });

  if (variant === 'inline') {
    return (
      <Box
        data-testid="budget-summary"
        sx={{ display: 'flex', flexWrap: 'wrap', columnGap: 1.5, rowGap: 0.25, color }}
      >
        {budgets.lines.map((line) => (
          <Typography
            key={line.key}
            variant="caption"
            sx={{ fontWeight: line.key === 'food' ? 700 : 500, whiteSpace: 'nowrap', opacity: line.isOver ? 1 : 0.95 }}
            color={line.isOver ? 'error.light' : 'inherit'}
          >
            {label(line.key)}: {formatCurrency(line.remaining)}
          </Typography>
        ))}
      </Box>
    );
  }

  return (
    <Stack spacing={0.5} data-testid="budget-summary">
      {budgets.lines.map((line) => (
        <Stack key={line.key} direction="row" justifyContent="space-between">
          <Typography variant="body2" color={line.isOver ? 'error.main' : 'text.secondary'}>
            {label(line.key)}
          </Typography>
          <Typography variant="body2" fontWeight={500} color={line.isOver ? 'error.main' : 'text.primary'}>
            {formatCurrency(line.remaining)}
          </Typography>
        </Stack>
      ))}
    </Stack>
  );
};
