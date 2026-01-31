/**
 * Basketful Admin - Main Application
 */
import { Admin, Resource, CustomRoutes } from 'react-admin';
import { Route } from 'react-router-dom';

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
  CombinedOrderCreate,
} from './resources';

// Custom Pages
import { Dashboard } from './pages/Dashboard';
import { BulkVoucherCreate } from './pages/BulkVoucherCreate';
import { Settings } from './pages/Settings';

// Icons
import PeopleIcon from '@mui/icons-material/People';
import SchoolIcon from '@mui/icons-material/School';
import ShoppingCartIcon from '@mui/icons-material/ShoppingCart';
import InventoryIcon from '@mui/icons-material/Inventory';
import LocalOfferIcon from '@mui/icons-material/LocalOffer';
import CategoryIcon from '@mui/icons-material/Category';
import MergeIcon from '@mui/icons-material/Merge';

const App = () => (
  <Admin
    authProvider={authProvider}
    dataProvider={dataProvider}
    dashboard={Dashboard}
    title="Basketful Admin"
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
      create={CombinedOrderCreate}
      icon={MergeIcon}
      options={{ label: 'Combined Orders' }}
    />

    {/* Supporting Resources (no menu items) */}
    <Resource name="subcategories" list={SubcategoryList} edit={SubcategoryEdit} create={SubcategoryCreate} />
    <Resource name="tags" />
    <Resource name="account-balances" />
    <Resource name="order-items" />
    <Resource name="packing-lists" />
    <Resource name="coaches" />
    <Resource name="users" />

    {/* Custom Routes */}
    <CustomRoutes>
      <Route path="/vouchers/bulk-create" element={<BulkVoucherCreate />} />
      <Route path="/settings" element={<Settings />} />
    </CustomRoutes>
  </Admin>
);

export default App;
