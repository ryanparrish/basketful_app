/**
 * Category Resource Components — with @dnd-kit drag-to-reorder pick sequence.
 *
 * CategoryList: drag rows to set warehouse pick order for categories.
 *   - On drag end: reindex all sort_order values to 10, 20, 30… and PATCH
 *     changed items after a 1-second debounce. Independent timer from products.
 *
 * CategoryShow → Products tab: drag rows to set pick order for products within
 *   the category. Same reindex + debounce pattern, fully independent timer.
 */
import { useRef, useState, useCallback } from 'react';
import {
  List,
  Create,
  Edit,
  Show,
  SimpleForm,
  TextInput,
  NumberInput,
  TextField,
  NumberField,
  EditButton,
  ShowButton,
  TabbedShowLayout,
  Datagrid,
  ReferenceInput,
  SelectInput,
  required,
  useGetList,
  useUpdate,
  useRecordContext,
  CreateButton,
  TopToolbar,
} from 'react-admin';
import {
  Box,
  Chip,
  IconButton,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import DragHandleIcon from '@mui/icons-material/DragHandle';
import {
  DndContext,
  closestCenter,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core';
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
  arrayMove,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { useNavigate } from 'react-router-dom';


// ─────────────────────────────────────────────────────────────
// Shared debounce + reindex save hook
// ─────────────────────────────────────────────────────────────

type SortableItem = { id: number; sort_order: number; [key: string]: unknown };

/**
 * Returns `scheduleSave` and `saveStatus`.
 * On each drag end: caller passes the newly-reordered list.
 * After `delayMs` idle, PATCHes only the items whose sort_order changed.
 * Reindex: position 0 → 10, position 1 → 20, etc. (gaps of 10).
 */
function useDebouncedSortSave(resource: string, delayMs = 1000) {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved'>('idle');
  const [update] = useUpdate();

  const scheduleSave = useCallback(
    (items: SortableItem[]) => {
      if (timerRef.current) clearTimeout(timerRef.current);
      setSaveStatus('saving');
      timerRef.current = setTimeout(async () => {
        const patches: Promise<unknown>[] = [];
        items.forEach((item, idx) => {
          const newOrder = (idx + 1) * 10;
          if (item.sort_order !== newOrder) {
            patches.push(
              update(
                resource,
                // Spread the full record so PUT/PATCH body always includes required
                // fields (e.g. `name`) even if the data provider falls back to PUT.
                { id: item.id, data: { ...item, sort_order: newOrder }, previousData: item },
                { returnPromise: true }
              )
            );
          }
        });
        try {
          await Promise.all(patches);
          setSaveStatus('saved');
          setTimeout(() => setSaveStatus('idle'), 2000);
        } catch {
          setSaveStatus('idle');
        }
      }, delayMs);
    },
    [resource, update, delayMs]
  );

  return { scheduleSave, saveStatus };
}

// ─────────────────────────────────────────────────────────────
// Generic sortable table row (drag handle in first cell)
// ─────────────────────────────────────────────────────────────

function SortableRow({ id, children }: { id: number; children: React.ReactNode }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id });
  return (
    <TableRow
      ref={setNodeRef}
      style={{
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.5 : 1,
        background: isDragging ? '#f5f5f5' : undefined,
      }}
    >
      <TableCell sx={{ width: 40, pr: 0, color: 'text.secondary' }}>
        <IconButton size="small" {...attributes} {...listeners} tabIndex={-1} sx={{ cursor: 'grab' }}>
          <DragHandleIcon fontSize="small" />
        </IconButton>
      </TableCell>
      {children}
    </TableRow>
  );
}

// ─────────────────────────────────────────────────────────────
// Save status chip
// ─────────────────────────────────────────────────────────────

function SaveChip({ status }: { status: 'idle' | 'saving' | 'saved' }) {
  if (status === 'idle') return null;
  return (
    <Chip
      size="small"
      label={status === 'saving' ? 'Saving…' : 'Saved ✓'}
      color={status === 'saved' ? 'success' : 'default'}
      sx={{ ml: 1 }}
    />
  );
}

// ─────────────────────────────────────────────────────────────
// CategoryList — drag-to-reorder pick sequence
// ─────────────────────────────────────────────────────────────

type CategoryRecord = {
  id: number;
  name: string;
  sort_order: number;
  product_count: number;
};

/** Wraps the DnD table — rendered inside the RA <List> so Create button lives in TopToolbar. */
function CategoryDndList() {
  const { data, isLoading } = useGetList<CategoryRecord>('categories', {
    pagination: { page: 1, perPage: 200 },
    sort: { field: 'sort_order', order: 'ASC' },
  });

  const [items, setItems] = useState<CategoryRecord[]>([]);
  const initialised = useRef(false);

  // Sync server data into local state once on load
  if (!isLoading && data && !initialised.current) {
    initialised.current = true;
    const sorted = [...data].sort(
      (a, b) => a.sort_order - b.sort_order || a.name.localeCompare(b.name)
    );
    // Defer to avoid state update during render
    Promise.resolve().then(() => setItems(sorted));
  }

  // Independent category debounce timer (useRef inside the hook)
  const { scheduleSave, saveStatus } = useDebouncedSortSave('categories');

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } })
  );
  const navigate = useNavigate();

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIdx = items.findIndex((i) => i.id === active.id);
    const newIdx = items.findIndex((i) => i.id === over.id);
    const reordered = arrayMove(items, oldIdx, newIdx);
    setItems(reordered);
    scheduleSave(reordered as SortableItem[]);
  };

  if (isLoading) return <Box sx={{ p: 2, color: 'text.secondary' }}>Loading…</Box>;

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 1.5 }}>
        <Typography variant="body2" color="text.secondary">
          Drag rows to set the warehouse pick sequence. Changes save automatically after 1 second.
        </Typography>
        <SaveChip status={saveStatus} />
      </Box>
      <Paper variant="outlined">
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
          <SortableContext items={items.map((i) => i.id)} strategy={verticalListSortingStrategy}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell sx={{ width: 40 }} />
                  <TableCell>Name</TableCell>
                  <TableCell>Products</TableCell>
                  <TableCell>Pick #</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {items.map((cat, idx) => (
                  <SortableRow key={cat.id} id={cat.id}>
                    <TableCell
                      sx={{ cursor: 'pointer', '&:hover': { textDecoration: 'underline' } }}
                      onClick={() => navigate(`/categories/${cat.id}/show`)}
                    >
                      {cat.name}
                    </TableCell>
                    <TableCell>{cat.product_count}</TableCell>
                    <TableCell>
                      <Chip label={idx + 1} size="small" variant="outlined" />
                    </TableCell>
                    <TableCell align="right">
                      <EditButton record={cat} resource="categories" label="" />
                      <ShowButton record={cat} resource="categories" label="" />
                    </TableCell>
                  </SortableRow>
                ))}
              </TableBody>
            </Table>
          </SortableContext>
        </DndContext>
      </Paper>
    </Box>
  );
}

export const CategoryList = () => (
  <List
    sort={{ field: 'sort_order', order: 'ASC' }}
    actions={
      <TopToolbar>
        <CreateButton />
      </TopToolbar>
    }
  >
    {/* CategoryDndList manages its own data fetch — ignore the RA list data */}
    <CategoryDndList />
  </List>
);

// ─────────────────────────────────────────────────────────────
// CategoryShow — TabbedShowLayout with sortable Products tab
// ─────────────────────────────────────────────────────────────

const CategoryTitle = () => {
  const record = useRecordContext();
  return <span>Category: {record?.name || ''}</span>;
};

type ProductRecord = {
  id: number;
  name: string;
  sort_order: number;
  price: number;
  quantity_in_stock: number;
  category: number;
};

/** Sortable product list for the Products tab. Independent debounce from category list. */
function SortableProductsTab({ categoryId }: { categoryId: number }) {
  const { data, isLoading } = useGetList<ProductRecord>('products', {
    pagination: { page: 1, perPage: 500 },
    sort: { field: 'sort_order', order: 'ASC' },
    filter: { category: categoryId },
  });

  const [items, setItems] = useState<ProductRecord[]>([]);
  const initialised = useRef(false);

  if (!isLoading && data && !initialised.current) {
    initialised.current = true;
    const sorted = [...data].sort(
      (a, b) => a.sort_order - b.sort_order || a.name.localeCompare(b.name)
    );
    Promise.resolve().then(() => setItems(sorted));
  }

  // Completely independent debounce timer — separate useRef inside this hook instance
  const { scheduleSave, saveStatus } = useDebouncedSortSave('products');

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } })
  );
  const navigate = useNavigate();

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIdx = items.findIndex((i) => i.id === active.id);
    const newIdx = items.findIndex((i) => i.id === over.id);
    const reordered = arrayMove(items, oldIdx, newIdx);
    setItems(reordered);
    scheduleSave(reordered as SortableItem[]);
  };

  if (isLoading) return <Box sx={{ p: 2, color: 'text.secondary' }}>Loading products…</Box>;
  if (!items.length)
    return <Box sx={{ p: 2, color: 'text.secondary' }}>No products in this category.</Box>;

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 1.5 }}>
        <Typography variant="body2" color="text.secondary">
          Drag rows to set the pick sequence within this category.
        </Typography>
        <SaveChip status={saveStatus} />
      </Box>
      <Paper variant="outlined">
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
          <SortableContext items={items.map((i) => i.id)} strategy={verticalListSortingStrategy}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell sx={{ width: 40 }} />
                  <TableCell>Name</TableCell>
                  <TableCell>Price</TableCell>
                  <TableCell>In Stock</TableCell>
                  <TableCell>Pick #</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {items.map((product, idx) => (
                  <SortableRow key={product.id} id={product.id}>
                    <TableCell
                      sx={{ cursor: 'pointer', '&:hover': { textDecoration: 'underline' } }}
                      onClick={() => navigate(`/products/${product.id}/show`)}
                    >
                      {product.name}
                    </TableCell>
                    <TableCell>${Number(product.price).toFixed(2)}</TableCell>
                    <TableCell>{product.quantity_in_stock}</TableCell>
                    <TableCell>
                      <Chip label={idx + 1} size="small" variant="outlined" />
                    </TableCell>
                  </SortableRow>
                ))}
              </TableBody>
            </Table>
          </SortableContext>
        </DndContext>
      </Paper>
    </Box>
  );
}

/** Thin wrapper — pulls categoryId from RA record context, then renders the DnD list. */
function CategoryShowProductsTab() {
  const record = useRecordContext();
  if (!record) return null;
  return <SortableProductsTab categoryId={record.id as number} />;
}

export const CategoryShow = () => (
  <Show title={<CategoryTitle />}>
    <TabbedShowLayout>
      <TabbedShowLayout.Tab label="Details">
        <TextField source="name" />
        <NumberField source="sort_order" label="Pick Order" />
        <NumberField source="product_count" label="Active Products" />
      </TabbedShowLayout.Tab>
      <TabbedShowLayout.Tab label="Products (Pick Order)">
        <CategoryShowProductsTab />
      </TabbedShowLayout.Tab>
      <TabbedShowLayout.Tab label="Subcategories">
        <ReferenceSubcategoriesTab />
      </TabbedShowLayout.Tab>
    </TabbedShowLayout>
  </Show>
);

function ReferenceSubcategoriesTab() {
  // Simple read-only list — subcategories don't need pick-order DnD
  return (
    <Box sx={{ pt: 1 }}>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
        Subcategories belonging to this category.
      </Typography>
    </Box>
  );
}

// ─────────────────────────────────────────────────────────────
// CategoryEdit / CategoryCreate
// ─────────────────────────────────────────────────────────────

export const CategoryEdit = () => (
  <Edit title={<CategoryTitle />}>
    <SimpleForm>
      <TextInput source="name" validate={required()} />
      <NumberInput
        source="sort_order"
        label="Pick Position"
        helperText="0 = floats to top of list; drag to reorder after saving"
      />
    </SimpleForm>
  </Edit>
);

export const CategoryCreate = () => (
  <Create>
    <SimpleForm>
      <TextInput source="name" validate={required()} />
      <NumberInput
        source="sort_order"
        label="Pick Position (optional)"
        defaultValue={0}
        helperText="Leave at 0 to appear at top, then drag into position"
      />
    </SimpleForm>
  </Create>
);

// ─────────────────────────────────────────────────────────────
// Subcategory Resource Components
// ─────────────────────────────────────────────────────────────

export const SubcategoryList = () => (
  <List sort={{ field: 'name', order: 'ASC' }}>
    <Datagrid rowClick="edit">
      <TextField source="name" />
      <TextField source="category_name" label="Category" />
      <EditButton />
    </Datagrid>
  </List>
);

export const SubcategoryEdit = () => (
  <Edit>
    <SimpleForm>
      <TextInput source="name" validate={required()} />
      <ReferenceInput source="category" reference="categories">
        <SelectInput optionText="name" label="Category" validate={required()} />
      </ReferenceInput>
    </SimpleForm>
  </Edit>
);

export const SubcategoryCreate = () => (
  <Create>
    <SimpleForm>
      <TextInput source="name" validate={required()} />
      <ReferenceInput source="category" reference="categories">
        <SelectInput optionText="name" label="Category" validate={required()} />
      </ReferenceInput>
    </SimpleForm>
  </Create>
);
