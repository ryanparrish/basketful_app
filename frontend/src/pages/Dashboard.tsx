/**
 * Dashboard Component
 */
import { useState, useEffect, useCallback } from 'react';
import { API_URL } from '../utils/apiUrl';
import { Card, CardContent, CardHeader, Chip, Alert, AlertTitle } from '@mui/material';
import {
  useGetList,
  Loading,
  Title,
} from 'react-admin';
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  LineChart,
  Line,
  CartesianGrid,
  ReferenceLine,
} from 'recharts';

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884d8'];

// Stats Card Component
interface StatsCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
}

const StatsCard = ({ title, value, subtitle }: StatsCardProps) => (
  <Card sx={{ minWidth: 200, m: 1 }}>
    <CardContent>
      <div style={{ fontSize: '0.875rem', color: '#666' }}>{title}</div>
      <div style={{ fontSize: '2rem', fontWeight: 'bold', color: '#1976d2' }}>
        {value}
      </div>
      {subtitle && (
        <div style={{ fontSize: '0.75rem', color: '#999' }}>{subtitle}</div>
      )}
    </CardContent>
  </Card>
);

// Orders by Status Chart
const OrdersByStatusChart = () => {
  const { data, isPending } = useGetList('orders', {
    pagination: { page: 1, perPage: 1000 },
  });

  if (isPending) return <Loading />;

  const statusCounts = (data || []).reduce(
    (acc: Record<string, number>, order: { status: string }) => {
      acc[order.status] = (acc[order.status] || 0) + 1;
      return acc;
    },
    {}
  );

  const chartData = Object.entries(statusCounts).map(([name, value]) => ({
    name: name.charAt(0).toUpperCase() + name.slice(1),
    value,
  }));

  return (
    <Card sx={{ m: 1, minHeight: 300 }}>
      <CardHeader title="Orders by Status" />
      <CardContent>
        <ResponsiveContainer width="100%" height={200}>
          <PieChart>
            <Pie
              data={chartData}
              dataKey="value"
              nameKey="name"
              cx="50%"
              cy="50%"
              outerRadius={80}
              label
            >
              {chartData.map((_, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={COLORS[index % COLORS.length]}
                />
              ))}
            </Pie>
            <Tooltip />
            <Legend />
          </PieChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
};

// Participants by Program Chart
const ParticipantsByProgramChart = () => {
  const { data, isPending } = useGetList('programs', {
    pagination: { page: 1, perPage: 100 },
  });

  if (isPending) return <Loading />;

  const chartData = (data || []).map((program: { name: string; participant_count: number }) => ({
    name: program.name,
    participants: program.participant_count || 0,
  }));

  return (
    <Card sx={{ m: 1, minHeight: 300 }}>
      <CardHeader title="Participants by Program" />
      <CardContent>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={chartData}>
            <XAxis dataKey="name" />
            <YAxis />
            <Tooltip />
            <Bar dataKey="participants" fill="#8884d8" />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
};

// Recent Orders List
const RecentOrders = () => {
  const { data, isPending } = useGetList('orders', {
    pagination: { page: 1, perPage: 5 },
    sort: { field: 'order_date', order: 'DESC' },
  });

  if (isPending) return <Loading />;

  return (
    <Card sx={{ m: 1 }}>
      <CardHeader title="Recent Orders" />
      <CardContent>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #ddd' }}>
              <th style={{ textAlign: 'left', padding: '8px' }}>Order #</th>
              <th style={{ textAlign: 'left', padding: '8px' }}>Participant</th>
              <th style={{ textAlign: 'left', padding: '8px' }}>Status</th>
              <th style={{ textAlign: 'right', padding: '8px' }}>Total</th>
            </tr>
          </thead>
          <tbody>
            {(data || []).map((order: {
              id: number;
              order_number: string;
              participant_name: string;
              status: string;
              total_price: number;
            }) => (
              <tr key={order.id} style={{ borderBottom: '1px solid #eee' }}>
                <td style={{ padding: '8px' }}>{order.order_number}</td>
                <td style={{ padding: '8px' }}>{order.participant_name}</td>
                <td style={{ padding: '8px' }}>
                  <span
                    style={{
                      backgroundColor:
                        order.status === 'pending'
                          ? '#FFA726'
                          : order.status === 'confirmed'
                          ? '#66BB6A'
                          : '#9E9E9E',
                      color: 'white',
                      padding: '2px 8px',
                      borderRadius: '4px',
                      fontSize: '0.75rem',
                    }}
                  >
                    {order.status.toUpperCase()}
                  </span>
                </td>
                <td style={{ textAlign: 'right', padding: '8px' }}>
                  ${Number(order.total_price).toFixed(2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
};

// Failed Order Analytics Widget
const FailedOrderAnalytics = () => {
  const [analytics, setAnalytics] = useState<{
    total_failures: number;
    failure_rate: number;
    common_errors: Array<{ error: string; count: number }>;
  } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('accessToken');
    fetch(`${API_URL}/api/v1/orders/failure-analytics/?days=7`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        setAnalytics(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  if (loading) return <Loading />;
  if (!analytics) return null;

  return (
    <Card sx={{ m: 1 }}>
      <CardHeader title="Failed Order Attempts (Last 7 Days)" />
      <CardContent>
        <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', marginBottom: 16 }}>
          <div>
            <div style={{ fontSize: '0.75rem', color: '#666' }}>Total Failures</div>
            <div style={{ fontSize: '1.75rem', fontWeight: 'bold', color: '#d32f2f' }}>
              {analytics.total_failures}
            </div>
          </div>
          <div>
            <div style={{ fontSize: '0.75rem', color: '#666' }}>Failure Rate</div>
            <div style={{ fontSize: '1.75rem', fontWeight: 'bold', color: '#f57c00' }}>
              {(analytics.failure_rate * 100).toFixed(1)}%
            </div>
          </div>
        </div>
        {analytics.common_errors?.length > 0 && (
          <div>
            <div style={{ fontSize: '0.875rem', fontWeight: 600, marginBottom: 8 }}>
              Top Errors
            </div>
            {analytics.common_errors.slice(0, 3).map((e, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <Chip label={e.count} size="small" color="error" />
                <span style={{ fontSize: '0.8rem', color: '#444' }}>{e.error}</span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

// Product Consumption Chart
const ALL_STATUSES = ['pending', 'confirmed', 'packing', 'completed'] as const;
const STATUS_CHIP_COLORS: Record<string, 'warning' | 'success' | 'info' | 'primary'> = {
  pending: 'warning',
  confirmed: 'success',
  packing: 'info',
  completed: 'primary',
};
const TREND_COLORS = ['#1976d2', '#00897b', '#f57c00', '#8e24aa', '#e53935', '#00acc1', '#43a047', '#fb8c00', '#5e35b1', '#d81b60'];

type ViewMode = 'week' | 'trends' | 'mom';
type WeekItem = { product_name: string; category_name: string; total_quantity: number; avg_per_order: number };
type TrendProduct = { product_id: number; product_name: string; monthly_data: Array<{ month: string; month_label: string; total_quantity: number }> };
type TrendData = { months: string[]; products: TrendProduct[] };
type MomItem = { product_id: number; product_name: string; category_name: string; current_qty: number; prev_qty: number; change: number; pct_change: number | null };
type MomData = { current_month: string; prev_month: string; results: MomItem[] };

const ProductConsumptionChart = () => {
  const [viewMode, setViewMode] = useState<ViewMode>('week');
  const [weekData, setWeekData] = useState<WeekItem[]>([]);
  const [trendData, setTrendData] = useState<TrendData | null>(null);
  const [momData, setMomData] = useState<MomData | null>(null);
  const [categories, setCategories] = useState<Array<{ id: number; name: string }>>([]);
  const [selectedCategory, setSelectedCategory] = useState<string>('');
  const [selectedStatuses, setSelectedStatuses] = useState<string[]>([...ALL_STATUSES]);
  const [loading, setLoading] = useState(true);
  const [weekLabel, setWeekLabel] = useState('');

  const fetchWeekData = useCallback(() => {
    const token = localStorage.getItem('accessToken');
    const params = new URLSearchParams();
    if (selectedCategory) params.set('category', selectedCategory);
    if (selectedStatuses.length > 0) params.set('statuses', selectedStatuses.join(','));
    setLoading(true);
    fetch(`${API_URL}/api/v1/orders/product-consumption/?${params}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => r.ok ? r.json() : null)
      .then(json => {
        if (json) {
          setWeekData(json.results);
          const s = new Date(json.week_start + 'T00:00:00');
          setWeekLabel(`Week of ${s.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`);
        }
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [selectedCategory, selectedStatuses]);

  const fetchTrendData = useCallback(() => {
    const token = localStorage.getItem('accessToken');
    const params = new URLSearchParams();
    if (selectedCategory) params.set('category', selectedCategory);
    if (selectedStatuses.length > 0) params.set('statuses', selectedStatuses.join(','));
    params.set('months', '6');
    params.set('top', '5');
    setLoading(true);
    fetch(`${API_URL}/api/v1/orders/product-consumption-trends/?${params}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => r.ok ? r.json() : null)
      .then(json => { setTrendData(json); setLoading(false); })
      .catch(() => setLoading(false));
  }, [selectedCategory, selectedStatuses]);

  const fetchMomData = useCallback(() => {
    const token = localStorage.getItem('accessToken');
    const params = new URLSearchParams();
    if (selectedCategory) params.set('category', selectedCategory);
    if (selectedStatuses.length > 0) params.set('statuses', selectedStatuses.join(','));
    setLoading(true);
    fetch(`${API_URL}/api/v1/orders/product-consumption-mom/?${params}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => r.ok ? r.json() : null)
      .then(json => { setMomData(json); setLoading(false); })
      .catch(() => setLoading(false));
  }, [selectedCategory, selectedStatuses]);

  useEffect(() => {
    const token = localStorage.getItem('accessToken');
    fetch(`${API_URL}/api/v1/categories/`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => r.ok ? r.json() : null)
      .then(json => {
        if (json?.results) setCategories(json.results);
        else if (Array.isArray(json)) setCategories(json);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (viewMode === 'week') fetchWeekData();
    else if (viewMode === 'trends') fetchTrendData();
    else fetchMomData();
  }, [viewMode, fetchWeekData, fetchTrendData, fetchMomData]);

  const toggleStatus = (s: string) => {
    setSelectedStatuses(prev =>
      prev.includes(s) ? prev.filter(x => x !== s) : [...prev, s]
    );
  };

  // Flatten trend data into recharts format: [{ month: 'Jan 2026', 'Apples': 10, ... }]
  const trendChartData = trendData
    ? trendData.months.map((month, i) => {
        const point: Record<string, string | number> = { month };
        trendData.products.forEach(p => { point[p.product_name] = p.monthly_data[i]?.total_quantity ?? 0; });
        return point;
      })
    : [];

  const cardTitle =
    viewMode === 'week' ? 'Product Consumption This Week'
    : viewMode === 'trends' ? 'Product Consumption Trends'
    : 'Month-over-Month Comparison';
  const cardSubheader =
    viewMode === 'week' ? weekLabel
    : viewMode === 'trends' ? 'Monthly totals — top 5 products'
    : momData ? `${momData.prev_month} → ${momData.current_month}` : '';

  return (
    <Card sx={{ m: 1 }}>
      <CardHeader
        title={cardTitle}
        subheader={cardSubheader}
        action={
          <div style={{ display: 'flex', gap: 6, paddingTop: 8, paddingRight: 8 }}>
            <Chip
              label="This Week"
              size="small"
              color={viewMode === 'week' ? 'primary' : 'default'}
              variant={viewMode === 'week' ? 'filled' : 'outlined'}
              onClick={() => setViewMode('week')}
              sx={{ cursor: 'pointer' }}
            />
            <Chip
              label="Monthly Trends"
              size="small"
              color={viewMode === 'trends' ? 'primary' : 'default'}
              variant={viewMode === 'trends' ? 'filled' : 'outlined'}
              onClick={() => setViewMode('trends')}
              sx={{ cursor: 'pointer' }}
            />
            <Chip
              label="MoM"
              size="small"
              color={viewMode === 'mom' ? 'primary' : 'default'}
              variant={viewMode === 'mom' ? 'filled' : 'outlined'}
              onClick={() => setViewMode('mom')}
              sx={{ cursor: 'pointer' }}
            />
          </div>
        }
      />
      <CardContent>
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 16, alignItems: 'center' }}>
          <select
            value={selectedCategory}
            onChange={e => setSelectedCategory(e.target.value)}
            style={{ padding: '6px 12px', borderRadius: 4, border: '1px solid #ccc', fontSize: '0.875rem' }}
          >
            <option value="">All Categories</option>
            {categories.map(c => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {ALL_STATUSES.map(s => (
              <Chip
                key={s}
                label={s.charAt(0).toUpperCase() + s.slice(1)}
                size="small"
                color={selectedStatuses.includes(s) ? STATUS_CHIP_COLORS[s] : 'default'}
                variant={selectedStatuses.includes(s) ? 'filled' : 'outlined'}
                onClick={() => toggleStatus(s)}
                sx={{ cursor: 'pointer' }}
              />
            ))}
          </div>
        </div>
        {loading ? (
          <Loading />
        ) : viewMode === 'week' ? (
          weekData.length === 0 ? (
            <div style={{ textAlign: 'center', color: '#999', padding: '40px 0' }}>No orders this week</div>
          ) : (
            <ResponsiveContainer width="100%" height={380}>
              <BarChart data={weekData} margin={{ top: 4, right: 16, left: 0, bottom: 10 }}>
                <XAxis
                  dataKey="product_name"
                  interval={0}
                  height={80}
                  tick={({ x, y, payload }) => {
                    const label = payload.value.length > 14 ? payload.value.slice(0, 13) + '…' : payload.value;
                    return (
                      <g transform={`translate(${x},${y})`}>
                        <text x={0} y={0} dy={6} textAnchor="end" fill="#666" fontSize={11} transform="rotate(-40)">
                          {label}
                        </text>
                      </g>
                    );
                  }}
                />
                <YAxis allowDecimals={false} />
                <Tooltip formatter={(value, name) => [value, name === 'total_quantity' ? 'Total Qty' : 'Avg / Order']} />
                <Legend verticalAlign="top" />
                <Bar dataKey="total_quantity" name="total_quantity" fill="#1976d2" radius={[3, 3, 0, 0]} />
                <Bar dataKey="avg_per_order" name="avg_per_order" fill="#00897b" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )
        ) : viewMode === 'trends' ? (
          !trendData || trendData.products.length === 0 ? (
            <div style={{ textAlign: 'center', color: '#999', padding: '40px 0' }}>No historical data found</div>
          ) : (
            <ResponsiveContainer width="100%" height={380}>
              <LineChart data={trendChartData} margin={{ top: 4, right: 24, left: 0, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Legend verticalAlign="top" />
                {trendData.products.map((p, i) => (
                  <Line
                    key={p.product_id}
                    type="monotone"
                    dataKey={p.product_name}
                    stroke={TREND_COLORS[i % TREND_COLORS.length]}
                    strokeWidth={2}
                    dot={{ r: 4 }}
                    activeDot={{ r: 6 }}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          )
        ) : (
          // MoM view
          !momData || momData.results.length === 0 ? (
            <div style={{ textAlign: 'center', color: '#999', padding: '40px 0' }}>No data for comparison</div>
          ) : (
            <>
              <ResponsiveContainer width="100%" height={380}>
                <BarChart
                  data={momData.results}
                  margin={{ top: 4, right: 16, left: 0, bottom: 10 }}
                  layout="vertical"
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" horizontal={false} />
                  <XAxis type="number" allowDecimals={false} />
                  <YAxis
                    type="category"
                    dataKey="product_name"
                    width={130}
                    tick={{ fontSize: 11 }}
                    tickFormatter={(v: string) => v.length > 16 ? v.slice(0, 15) + '…' : v}
                  />
                  <Tooltip
                    formatter={(value, name) => [
                      value,
                      name === 'current_qty' ? momData.current_month
                      : name === 'prev_qty' ? momData.prev_month
                      : 'Change'
                    ]}
                  />
                  <Legend verticalAlign="top" formatter={(v) =>
                    v === 'current_qty' ? momData.current_month
                    : v === 'prev_qty' ? momData.prev_month : v
                  } />
                  <ReferenceLine x={0} stroke="#aaa" />
                  <Bar dataKey="prev_qty" name="prev_qty" fill="#90caf9" radius={[0, 3, 3, 0]} />
                  <Bar dataKey="current_qty" name="current_qty" fill="#1976d2" radius={[0, 3, 3, 0]} />
                </BarChart>
              </ResponsiveContainer>
              <div style={{ marginTop: 12, display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {momData.results.map(item => {
                  const up = item.change > 0;
                  const flat = item.change === 0;
                  const color = flat ? '#888' : up ? '#2e7d32' : '#c62828';
                  const arrow = flat ? '→' : up ? '▲' : '▼';
                  const pct = item.pct_change !== null ? ` (${up ? '+' : ''}${item.pct_change}%)` : ' (new)';
                  return (
                    <div key={item.product_id} style={{
                      fontSize: '0.78rem', padding: '3px 10px', borderRadius: 12,
                      background: flat ? '#f5f5f5' : up ? '#e8f5e9' : '#ffebee',
                      color,
                    }}>
                      <strong>{item.product_name.length > 16 ? item.product_name.slice(0, 15) + '…' : item.product_name}</strong>
                      {' '}{arrow} {up ? '+' : ''}{item.change}{pct}
                    </div>
                  );
                })}
              </div>
            </>
          )
        )}
      </CardContent>
    </Card>
  );
};

export const Dashboard = () => {
  const { total: participantCount, isPending: participantsLoading } = useGetList(
    'participants',
    { pagination: { page: 1, perPage: 1 } }
  );
  const { total: orderCount, isPending: ordersLoading } = useGetList('orders', {
    pagination: { page: 1, perPage: 1 },
  });
  const { total: pendingCount, isPending: pendingLoading } = useGetList('orders', {
    pagination: { page: 1, perPage: 1 },
    filter: { status: 'pending' },
  });
  const { total: voucherCount, isPending: vouchersLoading } = useGetList('vouchers', {
    pagination: { page: 1, perPage: 1 },
    filter: { active: true, state: 'applied' },
  });

  const [activePause, setActivePause] = useState<{ reason: string | null } | null>(null);

  useEffect(() => {
    const token = localStorage.getItem('accessToken');
    fetch(`${API_URL}/api/v1/program-pauses/active/`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => r.ok ? r.json() : [])
      .then(data => setActivePause(data.length > 0 ? data[0] : null))
      .catch(() => null);
  }, []);

  const isLoading =
    participantsLoading || ordersLoading || pendingLoading || vouchersLoading;

  if (isLoading) return <Loading />;

  return (
    <div>
      <Title title="Dashboard" />

      {/* Active pause warning */}
      {activePause && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          <AlertTitle>Program Pause Active</AlertTitle>
          {activePause.reason} — This Pause Is Active
        </Alert>
      )}

      {/* Stats Row */}
      <div style={{ display: 'flex', flexWrap: 'wrap', marginBottom: '20px' }}>
        <StatsCard
          title="Total Participants"
          value={participantCount || 0}
          subtitle="Active participants"
        />
        <StatsCard
          title="Total Orders"
          value={orderCount || 0}
          subtitle="All time"
        />
        <StatsCard
          title="Pending Orders"
          value={pendingCount || 0}
          subtitle="Awaiting confirmation"
        />
        <StatsCard
          title="Active Vouchers"
          value={voucherCount || 0}
          subtitle="Available balance"
        />
      </div>

      {/* Charts Row */}
      <div style={{ display: 'flex', flexWrap: 'wrap' }}>
        <div style={{ flex: 1, minWidth: 300 }}>
          <OrdersByStatusChart />
        </div>
        <div style={{ flex: 1, minWidth: 300 }}>
          <ParticipantsByProgramChart />
        </div>
      </div>

      {/* Recent Orders */}
      <div style={{ marginTop: '20px' }}>
        <RecentOrders />
      </div>

      {/* Product Consumption */}
      <div style={{ marginTop: '20px' }}>
        <ProductConsumptionChart />
      </div>

      {/* Failure Analytics */}
      <div style={{ marginTop: '20px' }}>
        <FailedOrderAnalytics />
      </div>
    </div>
  );
};

export default Dashboard;
