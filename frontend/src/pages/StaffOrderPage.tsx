/**
 * StaffOrderPage
 *
 * Allows staff to place an order on behalf of a participant without
 * impersonating their account. Uses the existing validate-cart and
 * orders endpoints — zero backend changes required.
 *
 * Flow:
 *   1. Search & select a participant
 *   2. Browse the product catalog and build a cart (local state)
 *   3. Review: call validate-cart for real-time violations
 *   4. Submit: POST /orders/ against the participant's AccountBalance
 */
import React, { useState, useEffect } from 'react';
import {
  Alert,
  Badge,
  Box,
  Button,
  Card,
  CardActions,
  CardContent,
  Chip,
  CircularProgress,
  Divider,
  IconButton,
  InputAdornment,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  Paper,
  Stack,
  Step,
  StepLabel,
  Stepper,
  TextField,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import RemoveIcon from '@mui/icons-material/Remove';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import SearchIcon from '@mui/icons-material/Search';
import ShoppingCartIcon from '@mui/icons-material/ShoppingCart';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import { Title, useNotify } from 'react-admin';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../lib/api/apiClient';

// ─── Types ────────────────────────────────────────────────────────────────────

interface Balances {
  available_balance: string;
  hygiene_balance: string;
  go_fresh_balance: string;
}

interface Participant {
  id: number;
  name: string;
  customer_number: string;
  balances: Balances | null;
}

interface AccountBalance {
  id: number;
  available_balance: string;
  hygiene_balance: string;
  go_fresh_balance: string;
}

interface Product {
  id: number;
  name: string;
  price: string;
  category_name: string | null;
  active: boolean;
}

interface CartItem {
  productId: number;
  name: string;
  price: number;
  quantity: number;
  categoryName: string;
}

interface Violation {
  type: string;
  severity: 'error' | 'warning';
  message: string;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const STEPS = ['Select Participant', 'Build Cart', 'Review Order', 'Done'];

// ─── Component ────────────────────────────────────────────────────────────────

const StaffOrderPage: React.FC = () => {
  const navigate = useNavigate();
  const notify = useNotify();

  // Wizard step (0–3)
  const [activeStep, setActiveStep] = useState(0);

  // Step 0 — participant search
  const [searchQuery, setSearchQuery] = useState('');
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);

  // Selected participant + their account balance
  const [selectedParticipant, setSelectedParticipant] = useState<Participant | null>(null);
  const [accountBalance, setAccountBalance] = useState<AccountBalance | null>(null);
  const [balanceLoading, setBalanceLoading] = useState(false);

  // Step 1 — products + cart
  const [products, setProducts] = useState<Product[]>([]);
  const [productsLoading, setProductsLoading] = useState(false);
  const [productSearch, setProductSearch] = useState('');
  const [cart, setCart] = useState<CartItem[]>([]);

  // Step 2 — validation
  const [violations, setViolations] = useState<Violation[]>([]);
  const [validating, setValidating] = useState(false);
  const [cartIsValid, setCartIsValid] = useState(false);

  // Step 2 → done — submission
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [orderNumber, setOrderNumber] = useState<string | null>(null);

  // ── Participant search (debounced 300 ms) ──────────────────────────────────
  useEffect(() => {
    if (searchQuery.trim().length < 2) {
      setParticipants([]);
      return;
    }
    const timer = setTimeout(async () => {
      setSearchLoading(true);
      try {
        const { data } = await apiClient.get('/participants/', {
          params: { search: searchQuery, active: true, page_size: 20 },
        });
        setParticipants(data.results ?? data);
      } catch {
        setParticipants([]);
      } finally {
        setSearchLoading(false);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // ── Select a participant → load balance + products ─────────────────────────
  const handleSelectParticipant = async (participant: Participant) => {
    setSelectedParticipant(participant);
    setCart([]);
    setViolations([]);

    // Fetch AccountBalance ID (needed for the final POST /orders/)
    setBalanceLoading(true);
    try {
      const { data } = await apiClient.get('/account-balances/', {
        params: { participant: participant.id },
      });
      const bal: AccountBalance = data.results?.[0] ?? data[0] ?? null;
      setAccountBalance(bal);
    } catch {
      setAccountBalance(null);
      notify('Could not load participant balance.', { type: 'warning' });
    } finally {
      setBalanceLoading(false);
    }

    // Load product catalog
    setProductsLoading(true);
    try {
      const { data } = await apiClient.get('/products/', {
        params: { active: true, page_size: 500 },
      });
      setProducts(data.results ?? data);
    } catch {
      notify('Could not load products.', { type: 'error' });
    } finally {
      setProductsLoading(false);
    }

    setActiveStep(1);
  };

  // ── Cart helpers ───────────────────────────────────────────────────────────
  const addToCart = (product: Product) => {
    setCart((prev) => {
      const existing = prev.find((i) => i.productId === product.id);
      if (existing) {
        return prev.map((i) =>
          i.productId === product.id ? { ...i, quantity: i.quantity + 1 } : i
        );
      }
      return [
        ...prev,
        {
          productId: product.id,
          name: product.name,
          price: parseFloat(product.price),
          quantity: 1,
          categoryName: product.category_name ?? '',
        },
      ];
    });
  };

  const adjustQty = (productId: number, delta: number) => {
    setCart((prev) =>
      prev.flatMap((i) => {
        if (i.productId !== productId) return [i];
        const newQty = i.quantity + delta;
        return newQty > 0 ? [{ ...i, quantity: newQty }] : [];
      })
    );
  };

  const removeFromCart = (productId: number) => {
    setCart((prev) => prev.filter((i) => i.productId !== productId));
  };

  const cartItemCount = cart.reduce((s, i) => s + i.quantity, 0);
  const cartTotal = cart.reduce((s, i) => s + i.price * i.quantity, 0);

  // ── Product filtering + grouping ───────────────────────────────────────────
  const filteredProducts = products.filter(
    (p) =>
      !productSearch ||
      p.name.toLowerCase().includes(productSearch.toLowerCase()) ||
      (p.category_name ?? '').toLowerCase().includes(productSearch.toLowerCase())
  );

  const productsByCategory = filteredProducts.reduce<Record<string, Product[]>>(
    (acc, p) => {
      const cat = p.category_name ?? 'Other';
      (acc[cat] ??= []).push(p);
      return acc;
    },
    {}
  );

  // ── Step 1 → 2: validate cart ──────────────────────────────────────────────
  const handleReview = async () => {
    if (!selectedParticipant || cart.length === 0) return;
    setValidating(true);
    setViolations([]);
    try {
      const { data } = await apiClient.post('/orders/validate-cart/', {
        participant_id: selectedParticipant.id,
        items: cart.map((i) => ({ product_id: i.productId, quantity: i.quantity })),
      });
      const viols: Violation[] = data.violations ?? [];
      setViolations(viols);
      setCartIsValid(!viols.some((v) => v.severity === 'error'));
    } catch {
      setViolations([
        { type: 'error', severity: 'error', message: 'Validation failed — please try again.' },
      ]);
      setCartIsValid(false);
    } finally {
      setValidating(false);
      setActiveStep(2);
    }
  };

  // ── Step 2 → done: submit order ────────────────────────────────────────────
  const handleSubmit = async () => {
    if (!accountBalance) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const { data } = await apiClient.post('/orders/', {
        account: accountBalance.id,
        items: cart.map((i) => ({ product: i.productId, quantity: i.quantity })),
      });
      setOrderNumber(data.order_number);
      setActiveStep(3);
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { error?: string; detail?: string } } };
      setSubmitError(
        axiosErr.response?.data?.error ??
          axiosErr.response?.data?.detail ??
          'Order submission failed. Please try again.'
      );
    } finally {
      setSubmitting(false);
    }
  };

  // ── Reset to start ─────────────────────────────────────────────────────────
  const handleReset = () => {
    setActiveStep(0);
    setSearchQuery('');
    setParticipants([]);
    setSelectedParticipant(null);
    setAccountBalance(null);
    setProducts([]);
    setCart([]);
    setViolations([]);
    setOrderNumber(null);
    setSubmitError(null);
    setCartIsValid(false);
  };

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <Box sx={{ p: 3, maxWidth: 1200, mx: 'auto' }}>
      <Title title="Place Order for Participant" />

      <Typography variant="h5" fontWeight={600} gutterBottom>
        Place Order for Participant
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Build and submit an order on behalf of a participant — no impersonation required.
      </Typography>

      <Stepper activeStep={activeStep} sx={{ mb: 4 }}>
        {STEPS.map((label) => (
          <Step key={label}>
            <StepLabel>{label}</StepLabel>
          </Step>
        ))}
      </Stepper>

      {/* ─── Step 0: Participant Search ──────────────────────────────────── */}
      {activeStep === 0 && (
        <Paper sx={{ p: 3, maxWidth: 600 }}>
          <Typography variant="h6" gutterBottom>
            Search for a participant
          </Typography>
          <TextField
            fullWidth
            placeholder="Name or customer number…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            autoFocus
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  {searchLoading ? (
                    <CircularProgress size={18} />
                  ) : (
                    <SearchIcon fontSize="small" />
                  )}
                </InputAdornment>
              ),
            }}
            sx={{ mb: 2 }}
          />

          {participants.length > 0 && (
            <List disablePadding>
              {participants.map((p) => (
                <ListItemButton
                  key={p.id}
                  onClick={() => handleSelectParticipant(p)}
                  divider
                  sx={{ borderRadius: 1 }}
                >
                  <ListItemText
                    primary={p.name}
                    secondary={`Customer #${p.customer_number}`}
                  />
                  {p.balances && (
                    <Chip
                      label={`$${parseFloat(
                        p.balances.available_balance ?? '0'
                      ).toFixed(2)} avail.`}
                      size="small"
                      color="success"
                      variant="outlined"
                      sx={{ ml: 1 }}
                    />
                  )}
                </ListItemButton>
              ))}
            </List>
          )}

          {searchQuery.length >= 2 && !searchLoading && participants.length === 0 && (
            <Alert severity="info">
              No active participants found for &ldquo;{searchQuery}&rdquo;
            </Alert>
          )}
        </Paper>
      )}

      {/* ─── Step 1: Build Cart ──────────────────────────────────────────── */}
      {activeStep === 1 && selectedParticipant && (
        <Box>
          {/* Participant + balance bar */}
          <Paper
            sx={{
              p: 2,
              mb: 2,
              display: 'flex',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: 1,
            }}
          >
            <Typography fontWeight={600}>{selectedParticipant.name}</Typography>
            <Chip label={`#${selectedParticipant.customer_number}`} size="small" />

            {balanceLoading && <CircularProgress size={16} sx={{ ml: 1 }} />}

            {accountBalance && !balanceLoading && (
              <>
                <Chip
                  label={`Budget: $${parseFloat(accountBalance.available_balance).toFixed(2)}`}
                  color="success"
                  size="small"
                />
                {parseFloat(accountBalance.hygiene_balance) > 0 && (
                  <Chip
                    label={`Hygiene: $${parseFloat(accountBalance.hygiene_balance).toFixed(2)}`}
                    color="info"
                    size="small"
                  />
                )}
                {parseFloat(accountBalance.go_fresh_balance) > 0 && (
                  <Chip
                    label={`Go Fresh: $${parseFloat(accountBalance.go_fresh_balance).toFixed(2)}`}
                    color="secondary"
                    size="small"
                  />
                )}
              </>
            )}

            {!accountBalance && !balanceLoading && (
              <Alert severity="warning" sx={{ py: 0, ml: 1 }}>
                Balance unavailable — order may still be placed.
              </Alert>
            )}

            <Button
              size="small"
              onClick={() => setActiveStep(0)}
              sx={{ ml: 'auto' }}
            >
              ← Change Participant
            </Button>
          </Paper>

          <Box sx={{ display: 'flex', gap: 2, alignItems: 'flex-start' }}>
            {/* ── Products panel ─────────────────────────────────────── */}
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <TextField
                fullWidth
                size="small"
                placeholder="Filter products…"
                value={productSearch}
                onChange={(e) => setProductSearch(e.target.value)}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchIcon fontSize="small" />
                    </InputAdornment>
                  ),
                }}
                sx={{ mb: 2 }}
              />

              {productsLoading ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
                  <CircularProgress />
                </Box>
              ) : filteredProducts.length === 0 ? (
                <Alert severity="info">No products match your filter.</Alert>
              ) : (
                Object.entries(productsByCategory).map(([cat, prods]) => (
                  <Box key={cat} sx={{ mb: 3 }}>
                    <Typography
                      variant="overline"
                      color="text.secondary"
                      sx={{ px: 0.5, letterSpacing: 1 }}
                    >
                      {cat}
                    </Typography>
                    <Box
                      sx={{
                        display: 'flex',
                        flexWrap: 'wrap',
                        gap: 1.5,
                        mt: 0.5,
                      }}
                    >
                      {prods.map((p) => {
                        const inCart = cart.find((i) => i.productId === p.id);
                        return (
                          <Card
                            key={p.id}
                            variant="outlined"
                            sx={{
                              width: 155,
                              transition: 'box-shadow 0.15s',
                              boxShadow: inCart ? 2 : 0,
                              borderColor: inCart ? 'primary.main' : undefined,
                            }}
                          >
                            <CardContent sx={{ pb: 0.5, pt: 1.5, px: 1.5 }}>
                              <Typography
                                variant="body2"
                                fontWeight={500}
                                noWrap
                                title={p.name}
                              >
                                {p.name}
                              </Typography>
                              <Stack
                                direction="row"
                                justifyContent="space-between"
                                alignItems="center"
                                sx={{ mt: 0.5 }}
                              >
                                <Typography variant="caption" color="text.secondary">
                                  ${parseFloat(p.price).toFixed(2)}
                                </Typography>
                                {inCart && (
                                  <Badge
                                    badgeContent={inCart.quantity}
                                    color="primary"
                                    sx={{ mr: 1 }}
                                  />
                                )}
                              </Stack>
                            </CardContent>
                            <CardActions sx={{ pt: 0.5, pb: 1, justifyContent: 'center' }}>
                              {inCart ? (
                                <Stack direction="row" alignItems="center" spacing={0.5}>
                                  <IconButton
                                    size="small"
                                    onClick={() => adjustQty(p.id, -1)}
                                    aria-label="decrease"
                                  >
                                    <RemoveIcon sx={{ fontSize: 16 }} />
                                  </IconButton>
                                  <Typography
                                    variant="body2"
                                    sx={{ minWidth: 20, textAlign: 'center', fontWeight: 600 }}
                                  >
                                    {inCart.quantity}
                                  </Typography>
                                  <IconButton
                                    size="small"
                                    onClick={() => adjustQty(p.id, 1)}
                                    aria-label="increase"
                                  >
                                    <AddIcon sx={{ fontSize: 16 }} />
                                  </IconButton>
                                </Stack>
                              ) : (
                                <Button
                                  size="small"
                                  startIcon={<AddIcon />}
                                  onClick={() => addToCart(p)}
                                >
                                  Add
                                </Button>
                              )}
                            </CardActions>
                          </Card>
                        );
                      })}
                    </Box>
                  </Box>
                ))
              )}
            </Box>

            {/* ── Cart panel ─────────────────────────────────────────── */}
            <Paper
              variant="outlined"
              sx={{
                width: 290,
                flexShrink: 0,
                position: 'sticky',
                top: 72,
                display: 'flex',
                flexDirection: 'column',
              }}
            >
              {/* Cart header */}
              <Box
                sx={{
                  p: 2,
                  borderBottom: 1,
                  borderColor: 'divider',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 1,
                }}
              >
                <ShoppingCartIcon fontSize="small" color="action" />
                <Typography fontWeight={600}>Cart</Typography>
                {cartItemCount > 0 && (
                  <Chip label={cartItemCount} size="small" color="primary" sx={{ ml: 'auto' }} />
                )}
              </Box>

              {/* Cart items */}
              {cart.length === 0 ? (
                <Box sx={{ p: 3, textAlign: 'center' }}>
                  <Typography variant="body2" color="text.secondary">
                    Add items from the product list
                  </Typography>
                </Box>
              ) : (
                <>
                  <List dense sx={{ maxHeight: 380, overflow: 'auto', px: 0.5 }}>
                    {cart.map((item) => (
                      <ListItem
                        key={item.productId}
                        disableGutters
                        secondaryAction={
                          <IconButton
                            edge="end"
                            size="small"
                            onClick={() => removeFromCart(item.productId)}
                            aria-label={`Remove ${item.name}`}
                          >
                            <DeleteOutlineIcon sx={{ fontSize: 16 }} />
                          </IconButton>
                        }
                        sx={{ px: 1 }}
                      >
                        <ListItemText
                          primary={item.name}
                          secondary={`${item.quantity} × $${item.price.toFixed(2)}`}
                          primaryTypographyProps={{ variant: 'body2', noWrap: true }}
                          secondaryTypographyProps={{ variant: 'caption' }}
                        />
                      </ListItem>
                    ))}
                  </List>

                  <Divider />

                  <Box sx={{ p: 2 }}>
                    <Stack direction="row" justifyContent="space-between" sx={{ mb: 2 }}>
                      <Typography variant="body2" fontWeight={600}>
                        Total
                      </Typography>
                      <Typography variant="body2" fontWeight={600}>
                        ${cartTotal.toFixed(2)}
                      </Typography>
                    </Stack>
                    <Button
                      fullWidth
                      variant="contained"
                      onClick={handleReview}
                      disabled={cart.length === 0 || validating}
                      startIcon={
                        validating ? <CircularProgress size={16} color="inherit" /> : undefined
                      }
                    >
                      {validating ? 'Validating…' : 'Review Order →'}
                    </Button>
                  </Box>
                </>
              )}
            </Paper>
          </Box>
        </Box>
      )}

      {/* ─── Step 2: Review & Submit ─────────────────────────────────────── */}
      {activeStep === 2 && selectedParticipant && (
        <Paper sx={{ p: 3, maxWidth: 600 }}>
          <Typography variant="h6" gutterBottom>
            Review Order
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
            Placing for <strong>{selectedParticipant.name}</strong>{' '}
            (#{selectedParticipant.customer_number})
          </Typography>

          {/* Validation results */}
          {violations.length === 0 ? (
            <Alert severity="success" sx={{ mb: 3 }}>
              Cart is valid — ready to submit.
            </Alert>
          ) : (
            <Box sx={{ mb: 3 }}>
              {violations.map((v, i) => (
                <Alert key={i} severity={v.severity} sx={{ mb: 1 }}>
                  {v.message}
                </Alert>
              ))}
            </Box>
          )}

          {/* Order summary */}
          <List dense disablePadding>
            {cart.map((item) => (
              <ListItem key={item.productId} disableGutters>
                <ListItemText
                  primary={item.name}
                  secondary={item.categoryName || undefined}
                  primaryTypographyProps={{ variant: 'body2' }}
                  secondaryTypographyProps={{ variant: 'caption' }}
                />
                <Typography variant="body2" color="text.secondary">
                  {item.quantity} × ${item.price.toFixed(2)}
                </Typography>
                <Typography variant="body2" fontWeight={600} sx={{ ml: 2, minWidth: 60, textAlign: 'right' }}>
                  ${(item.quantity * item.price).toFixed(2)}
                </Typography>
              </ListItem>
            ))}
          </List>

          <Divider sx={{ my: 2 }} />

          <Stack direction="row" justifyContent="space-between" sx={{ mb: 3 }}>
            <Typography fontWeight={700}>Total</Typography>
            <Typography fontWeight={700}>${cartTotal.toFixed(2)}</Typography>
          </Stack>

          {submitError && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {submitError}
            </Alert>
          )}

          {!accountBalance && (
            <Alert severity="warning" sx={{ mb: 2 }}>
              Participant account balance could not be loaded. Cannot place order.
            </Alert>
          )}

          <Stack direction="row" spacing={2}>
            <Button onClick={() => setActiveStep(1)} disabled={submitting}>
              ← Edit Cart
            </Button>
            <Button
              variant="contained"
              onClick={handleSubmit}
              disabled={!cartIsValid || submitting || !accountBalance}
              sx={{ flex: 1 }}
              startIcon={
                submitting ? <CircularProgress size={16} color="inherit" /> : undefined
              }
            >
              {submitting ? 'Placing Order…' : 'Place Order'}
            </Button>
          </Stack>
        </Paper>
      )}

      {/* ─── Step 3: Success ─────────────────────────────────────────────── */}
      {activeStep === 3 && (
        <Paper sx={{ p: 5, textAlign: 'center', maxWidth: 480, mx: 'auto' }}>
          <CheckCircleIcon color="success" sx={{ fontSize: 80, mb: 2 }} />
          <Typography variant="h5" gutterBottom fontWeight={600}>
            Order Placed!
          </Typography>
          <Typography color="text.secondary" sx={{ mb: 0.5 }}>
            Order <strong>#{orderNumber}</strong> submitted successfully for
          </Typography>
          <Typography fontWeight={600} sx={{ mb: 3 }}>
            {selectedParticipant?.name}
          </Typography>
          <Stack direction="row" spacing={2} justifyContent="center">
            <Button variant="outlined" onClick={() => navigate('/orders')}>
              View Orders
            </Button>
            <Button variant="contained" onClick={handleReset}>
              Place Another Order
            </Button>
          </Stack>
        </Paper>
      )}
    </Box>
  );
};

export default StaffOrderPage;
