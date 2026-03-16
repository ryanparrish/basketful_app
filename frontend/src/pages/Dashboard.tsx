/**
 * Dashboard Component
 */
import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, Chip } from '@mui/material';
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
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    fetch(`${apiUrl}/api/v1/orders/failure-analytics/?days=7`, {
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

  const isLoading =
    participantsLoading || ordersLoading || pendingLoading || vouchersLoading;

  if (isLoading) return <Loading />;

  return (
    <div>
      <Title title="Dashboard" />
      
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

      {/* Failure Analytics */}
      <div style={{ marginTop: '20px' }}>
        <FailedOrderAnalytics />
      </div>
    </div>
  );
};

export default Dashboard;
