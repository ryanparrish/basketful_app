/**
 * Basketful Admin - Main Application
 */
import { useEffect, type ReactNode } from 'react';
import { Admin, Resource, CustomRoutes, Menu, Layout, useNotify } from 'react-admin';
import { Route } from 'react-router-dom';
import SettingsIcon from '@mui/icons-material/Settings';
import { SESSION_EXPIRED_EVENT } from './lib/api/apiClient.ts';

// Providers
import { authProvider, dataProvider } from './providers';
import { PermissionProvider } from './contexts/PermissionContext';

// Resources
import {
  ParticipantList,
  ParticipantShow,
  ParticipantEdit,
  ParticipantCreate,
  ProgramList,
  ProgramShow,
  ProgramEdit,
  ProgramCreate,
  OrderList,
  OrderShow,
  OrderEdit,
  OrderCreate,
  ProductList,
  ProductShow,
  ProductEdit,
  ProductCreate,
  VoucherList,
  VoucherShow,
  VoucherEdit,
  VoucherCreate,
  CategoryList,
  CategoryShow,
  CategoryEdit,
  CategoryCreate,
  SubcategoryList,
  SubcategoryEdit,
  SubcategoryCreate,
  CombinedOrderList,
  CombinedOrderShow,
  CombinedOrderEdit,
  PackingListList,
  PackingListShow,
  TagList,
  TagShow,
  TagEdit,
  TagCreate,
  ProductLimitList,
  ProductLimitShow,
  ProductLimitEdit,
  ProductLimitCreate,
  GroupList,
  GroupShow,
  GroupEdit,
  GroupCreate,
  PermissionList,
  PermissionShow,
  UserList,
  UserShow,
  UserEdit,
  UserCreate,
  OrderPackerList,
  OrderPackerShow,
  OrderPackerCreate,
  OrderPackerEdit,
  FailedOrderAttemptList,
  FailedOrderAttemptShow,
  CoachList,
  CoachShow,
  CoachEdit,
  CoachCreate,
} from './resources';
import CoachDashboard from './pages/CoachDashboard';

// Custom Pages
import { Dashboard } from './pages/Dashboard';
import BulkVoucherCreate from './pages/BulkVoucherCreate';
import BulkVoucherStatusUpdate from './pages/BulkVoucherStatusUpdate';
import Settings from './pages/Settings';
import CreateCombinedOrder from './pages/CreateCombinedOrder';
import PrintPackingList from './pages/PrintPackingList';
import PrintOrder from './pages/PrintOrder';
import PrintCustomerList from './pages/PrintCustomerList';
import BulkParticipantCreate from './pages/BulkParticipantCreate';
import PrintWelcomeCards from './pages/PrintWelcomeCards';
import LoginPage from './pages/Login';
import StaffOrderPage from './pages/StaffOrderPage';

// Branding
import { BrandingSettingsEdit, BrandingSettingsIcon } from './resources/brandingSettings';

// Log Resources
import {
  EmailTypeList, EmailTypeShow, EmailTypeEdit, EmailTypeCreate,
  EmailLogList, EmailLogShow,
  UserLoginLogList, UserLoginLogShow,
  GraceAllowanceLogList, GraceAllowanceLogShow,
  OrderValidationLogList, OrderValidationLogShow,
  VoucherLogList, VoucherLogShow,
} from './resources/logs';

// Icons
import PeopleIcon from '@mui/icons-material/People';
import SchoolIcon from '@mui/icons-material/School';
import ShoppingCartIcon from '@mui/icons-material/ShoppingCart';
import InventoryIcon from '@mui/icons-material/Inventory';
import LocalOfferIcon from '@mui/icons-material/LocalOffer';
import CategoryIcon from '@mui/icons-material/Category';
import MergeIcon from '@mui/icons-material/Merge';
import ViewListIcon from '@mui/icons-material/ViewList';
import LabelIcon from '@mui/icons-material/Label';
import RuleIcon from '@mui/icons-material/Rule';
import GroupIcon from '@mui/icons-material/Group';
import SecurityIcon from '@mui/icons-material/Security';
import ManageAccountsIcon from '@mui/icons-material/ManageAccounts';
import BackpackIcon from '@mui/icons-material/Backpack';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import SportsIcon from '@mui/icons-material/Sports';
import DashboardCustomizeIcon from '@mui/icons-material/DashboardCustomize';
import AddShoppingCartIcon from '@mui/icons-material/AddShoppingCart';
import ArticleIcon from '@mui/icons-material/Article';
import EmailIcon from '@mui/icons-material/Email';
import LoginIcon from '@mui/icons-material/Login';
import SavingsIcon from '@mui/icons-material/Savings';
import FactCheckIcon from '@mui/icons-material/FactCheck';
import ConfirmationNumberIcon from '@mui/icons-material/ConfirmationNumber';

const CustomMenu = () => (
  <Menu>
    <Menu.DashboardItem />
    <Menu.Item to="/place-order" primaryText="Place Order for Participant" leftIcon={<AddShoppingCartIcon />} />
    <Menu.ResourceItem name="participants" />
    <Menu.ResourceItem name="programs" />
    <Menu.ResourceItem name="orders" />
    <Menu.ResourceItem name="products" />
    <Menu.ResourceItem name="vouchers" />
    <Menu.ResourceItem name="categories" />
    <Menu.ResourceItem name="combined-orders" />
    <Menu.ResourceItem name="packing-lists" />
    <Menu.ResourceItem name="tags" />
    <Menu.ResourceItem name="product-limits" />
    <Menu.ResourceItem name="order-packers" />
    <Menu.ResourceItem name="failed-order-attempts" />
    <Menu.ResourceItem name="users" />
    <Menu.ResourceItem name="groups" />
    <Menu.ResourceItem name="permissions" />
    <Menu.ResourceItem name="coaches" />
    <Menu.Item to="/coach-dashboard" primaryText="Coach Dashboard" leftIcon={<DashboardCustomizeIcon />} />
    <Menu.Item to="/branding-settings/current/edit" primaryText="Branding" leftIcon={<BrandingSettingsIcon />} />
    <Menu.Item to="/settings" primaryText="Settings" leftIcon={<SettingsIcon />} />
    <Menu.Item to="/email-types" primaryText="Email Types" leftIcon={<EmailIcon />} />
    <Menu.Item to="/email-logs" primaryText="Email Logs" leftIcon={<ArticleIcon />} />
    <Menu.Item to="/login-logs" primaryText="Login Logs" leftIcon={<LoginIcon />} />
    <Menu.Item to="/grace-allowance-logs" primaryText="Grace Allowance Logs" leftIcon={<SavingsIcon />} />
    <Menu.Item to="/order-validation-logs" primaryText="Validation Logs" leftIcon={<FactCheckIcon />} />
    <Menu.Item to="/voucher-logs" primaryText="Voucher Logs" leftIcon={<ConfirmationNumberIcon />} />
  </Menu>
);

const CustomLayout = ({ children }: { children: ReactNode }) => {
  const notify = useNotify();

  useEffect(() => {
    const handleSessionExpired = () => {
      notify('Your session has expired. Please log in again.', { type: 'error' });
    };

    window.addEventListener(SESSION_EXPIRED_EVENT, handleSessionExpired);

    return () => {
      window.removeEventListener(SESSION_EXPIRED_EVENT, handleSessionExpired);
    };
  }, [notify]);

  return (
    <PermissionProvider>
      <Layout menu={CustomMenu}>{children}</Layout>
    </PermissionProvider>
  );
};

const App = () => (
  <Admin
    authProvider={authProvider}
    dataProvider={dataProvider}
    dashboard={Dashboard}
    title="Basketful Admin"
    layout={CustomLayout}
    loginPage={LoginPage}
  >
    {/* Core Resources */}
    <Resource
      name="participants"
      list={ParticipantList}
      show={ParticipantShow}
      edit={ParticipantEdit}
      create={ParticipantCreate}
      icon={PeopleIcon}
      options={{ label: 'Participants' }}
    />
    <Resource
      name="programs"
      list={ProgramList}
      show={ProgramShow}
      edit={ProgramEdit}
      create={ProgramCreate}
      icon={SchoolIcon}
      options={{ label: 'Programs' }}
    />
    <Resource
      name="orders"
      list={OrderList}
      show={OrderShow}
      edit={OrderEdit}
      create={OrderCreate}
      icon={ShoppingCartIcon}
      options={{ label: 'Orders' }}
    />
    <Resource
      name="products"
      list={ProductList}
      show={ProductShow}
      edit={ProductEdit}
      create={ProductCreate}
      icon={InventoryIcon}
      options={{ label: 'Products' }}
    />
    <Resource
      name="vouchers"
      list={VoucherList}
      show={VoucherShow}
      edit={VoucherEdit}
      create={VoucherCreate}
      icon={LocalOfferIcon}
      options={{ label: 'Vouchers' }}
    />
    <Resource
      name="categories"
      list={CategoryList}
      show={CategoryShow}
      edit={CategoryEdit}
      create={CategoryCreate}
      icon={CategoryIcon}
      options={{ label: 'Categories' }}
    />
    <Resource
      name="combined-orders"
      list={CombinedOrderList}
      show={CombinedOrderShow}
      edit={CombinedOrderEdit}
      icon={MergeIcon}
      options={{ label: 'Combined Orders' }}
    />
    <Resource
      name="packing-lists"
      list={PackingListList}
      show={PackingListShow}
      icon={ViewListIcon}
      options={{ label: 'Packing Lists' }}
    />
    <Resource
      name="tags"
      list={TagList}
      show={TagShow}
      edit={TagEdit}
      create={TagCreate}
      icon={LabelIcon}
      options={{ label: 'Tags' }}
    />
    <Resource
      name="product-limits"
      list={ProductLimitList}
      show={ProductLimitShow}
      edit={ProductLimitEdit}
      create={ProductLimitCreate}
      icon={RuleIcon}
      options={{ label: 'Product Limits' }}
    />

    {/* Packing Resources */}
    <Resource
      name="order-packers"
      list={OrderPackerList}
      show={OrderPackerShow}
      create={OrderPackerCreate}
      edit={OrderPackerEdit}
      icon={BackpackIcon}
      options={{ label: 'Packers' }}
    />
    <Resource
      name="failed-order-attempts"
      list={FailedOrderAttemptList}
      show={FailedOrderAttemptShow}
      icon={ErrorOutlineIcon}
      options={{ label: 'Failed Order Attempts' }}
    />

    {/* User Management Resources */}
    <Resource
      name="users"
      list={UserList}
      show={UserShow}
      edit={UserEdit}
      create={UserCreate}
      icon={ManageAccountsIcon}
      options={{ label: 'Users' }}
    />
    <Resource
      name="groups"
      list={GroupList}
      show={GroupShow}
      edit={GroupEdit}
      create={GroupCreate}
      icon={GroupIcon}
      options={{ label: 'Groups' }}
    />
    <Resource
      name="permissions"
      list={PermissionList}
      show={PermissionShow}
      icon={SecurityIcon}
      options={{ label: 'Permissions' }}
    />

    {/* Coaches */}
    <Resource
      name="coaches"
      list={CoachList}
      show={CoachShow}
      edit={CoachEdit}
      create={CoachCreate}
      icon={SportsIcon}
      options={{ label: 'Coaches' }}
    />

    {/* Supporting Resources (no menu items) */}
    <Resource name="subcategories" list={SubcategoryList} edit={SubcategoryEdit} create={SubcategoryCreate} />
    <Resource name="account-balances" />
    <Resource name="order-items" />

    {/* Branding Settings (singleton — edit only) */}
    <Resource
      name="branding-settings"
      edit={BrandingSettingsEdit}
      icon={BrandingSettingsIcon}
      options={{ label: 'Branding' }}
    />

    {/* Log Resources */}
    <Resource
      name="email-types"
      list={EmailTypeList}
      show={EmailTypeShow}
      edit={EmailTypeEdit}
      create={EmailTypeCreate}
      icon={EmailIcon}
      options={{ label: 'Email Types' }}
    />
    <Resource
      name="email-logs"
      list={EmailLogList}
      show={EmailLogShow}
      icon={ArticleIcon}
      options={{ label: 'Email Logs' }}
    />
    <Resource
      name="login-logs"
      list={UserLoginLogList}
      show={UserLoginLogShow}
      icon={LoginIcon}
      options={{ label: 'Login Logs' }}
    />
    <Resource
      name="grace-allowance-logs"
      list={GraceAllowanceLogList}
      show={GraceAllowanceLogShow}
      icon={SavingsIcon}
      options={{ label: 'Grace Allowance Logs' }}
    />
    <Resource
      name="order-validation-logs"
      list={OrderValidationLogList}
      show={OrderValidationLogShow}
      icon={FactCheckIcon}
      options={{ label: 'Order Validation Logs' }}
    />
    <Resource
      name="voucher-logs"
      list={VoucherLogList}
      show={VoucherLogShow}
      icon={ConfirmationNumberIcon}
      options={{ label: 'Voucher Logs' }}
    />

    {/* Custom Routes */}
    <CustomRoutes>
      <Route path="/place-order" element={<StaffOrderPage />} />
      <Route path="/vouchers/bulk-create" element={<BulkVoucherCreate />} />
      <Route path="/vouchers/bulk-status-update" element={<BulkVoucherStatusUpdate />} />
      <Route path="/settings" element={<Settings />} />
      <Route path="/combined-orders/create-wizard" element={<CreateCombinedOrder />} />
      <Route path="/packing-lists/:id/print" element={<PrintPackingList />} />
      <Route path="/orders/:id/print" element={<PrintOrder />} />
      <Route path="/participants/print-customer-list" element={<PrintCustomerList />} />
      <Route path="/participants/bulk-create" element={<BulkParticipantCreate />} />
      <Route path="/participants/welcome-cards/:batchId" element={<PrintWelcomeCards />} />
      <Route path="/participants/welcome-cards" element={<PrintWelcomeCards />} />
      <Route path="/coach-dashboard" element={<CoachDashboard />} />
    </CustomRoutes>
  </Admin>
);

export default App;
