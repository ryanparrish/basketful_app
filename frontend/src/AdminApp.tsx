/**
 * Basketful Admin - Main Application
 */
import { useEffect, type ReactNode } from 'react';
import { Admin, Resource, CustomRoutes, Menu, Layout, useNotify } from 'react-admin';
import { Route } from 'react-router-dom';
import SettingsIcon from '@mui/icons-material/Settings';
import { SESSION_EXPIRED_EVENT } from './lib/api/apiClient';

// Providers
import { authProvider, dataProvider } from './providers';

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
} from './resources';

// Custom Pages
import { Dashboard } from './pages/Dashboard';
import BulkVoucherCreate from './pages/BulkVoucherCreate';
import Settings from './pages/Settings';
import CreateCombinedOrder from './pages/CreateCombinedOrder';
import PrintPackingList from './pages/PrintPackingList';
import PrintOrder from './pages/PrintOrder';
import PrintCustomerList from './pages/PrintCustomerList';
import LoginPage from './pages/Login';

// Branding
import { BrandingSettingsEdit, BrandingSettingsIcon } from './resources/brandingSettings';

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

const CustomMenu = () => (
  <Menu>
    <Menu.DashboardItem />
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
    <Menu.Item to="/branding-settings/current/edit" primaryText="Branding" leftIcon={<BrandingSettingsIcon />} />
    <Menu.Item to="/settings" primaryText="Settings" leftIcon={<SettingsIcon />} />
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

  return <Layout menu={CustomMenu}>{children}</Layout>;
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

    {/* Supporting Resources (no menu items) */}
    <Resource name="subcategories" list={SubcategoryList} edit={SubcategoryEdit} create={SubcategoryCreate} />
    <Resource name="account-balances" />
    <Resource name="order-items" />
    <Resource name="coaches" />

    {/* Branding Settings (singleton — edit only) */}
    <Resource
      name="branding-settings"
      edit={BrandingSettingsEdit}
      icon={BrandingSettingsIcon}
      options={{ label: 'Branding' }}
    />

    {/* Custom Routes */}
    <CustomRoutes>
      <Route path="/vouchers/bulk-create" element={<BulkVoucherCreate />} />
      <Route path="/settings" element={<Settings />} />
      <Route path="/combined-orders/create-wizard" element={<CreateCombinedOrder />} />
      <Route path="/packing-lists/:id/print" element={<PrintPackingList />} />
      <Route path="/orders/:id/print" element={<PrintOrder />} />
      <Route path="/participants/print-customer-list" element={<PrintCustomerList />} />
    </CustomRoutes>
  </Admin>
);

export default App;
