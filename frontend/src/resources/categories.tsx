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
  useCreate,
  useNotify,
  useRefresh,
  useRecordContext,
  CreateButton,
  TopToolbar,
} from 'react-admin';
import {
  Alert,
  Box,
  Button,
  Chip,
  Divider,
  IconButton,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField as MuiTextField,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
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
import { BackNavButton } from '../components/BackNavButton';


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
            // Send only sort_order — a PATCH (not PUT) so no other fields are required.
            // Exclude file/image fields: DRF's ImageField rejects URL strings in JSON
            // bodies, which would cause a silent 400 and leave the DB unchanged.
            // eslint-disable-next-line @typescript-eslint/no-unused-vars
            const { image: _image, ...safeItem } = item as SortableItem & { image?: unknown };
            patches.push(
              update(
                resource,
                { id: item.id, data: { ...safeItem, sort_order: newOrder }, previousData: item },
                { returnPromise: true }
              )
            );
          }
        });
        try {
          await Promise.all(patches);
          setSaveStatus('saved');
          setTimeout(() => setSaveStatus('idle'), 2000);
        } catch (err) {
          console.error('[pick-order] Failed to save sort order:', err);
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
  const lastDataRef = useRef<typeof data | null>(null);

  // Sync server data into local state whenever the fetched data identity changes
  // (initial load AND after React-Admin invalidates the cache post-save).
  if (!isLoading && data && data !== lastDataRef.current) {
    lastDataRef.current = data;
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
      <Alert severity="info" sx={{ mb: 2 }}>
        <strong>How pick order works:</strong>&nbsp; This list sets the order categories appear on
        the packing list. To reorder products or subcategories within a category, click
        &nbsp;<strong>👁 View</strong>&nbsp;on any row below, then use the
        &nbsp;<strong>Products (Pick Order)</strong>&nbsp;or&nbsp;<strong>Subcategories</strong>
        &nbsp;tabs to drag items into position.
      </Alert>
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

/** Toolbar shown inside CategoryShow — back link + edit button. */
function CategoryShowActions() {
  return (
    <TopToolbar sx={{ alignItems: 'center' }}>
      <BackNavButton to="/categories" label="All Categories" />
      <EditButton />
    </TopToolbar>
  );
}

type ProductRecord = {
  id: number;
  name: string;
  sort_order: number;
  subcategory_sort_order: number;
  subcategory_name: string | null;
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
  const lastDataRef = useRef<typeof data | null>(null);

  // Sync whenever server data identity changes (load + post-save re-fetch)
  if (!isLoading && data && data !== lastDataRef.current) {
    lastDataRef.current = data;
    const sorted = [...data].sort(
      (a, b) =>
        (a.subcategory_sort_order ?? 9999) - (b.subcategory_sort_order ?? 9999) ||
        a.sort_order - b.sort_order ||
        a.name.localeCompare(b.name)
    );
    Promise.resolve().then(() => setItems(sorted));
  }

  // Completely independent debounce timer — separate useRef inside this hook instance
  const { scheduleSave, saveStatus } = useDebouncedSortSave('products');
  const notify = useNotify();

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } })
  );
  const navigate = useNavigate();

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    const oldIdx = items.findIndex((i) => i.id === active.id);
    const newIdx = items.findIndex((i) => i.id === over.id);
    const dragged = items[oldIdx];
    const target = items[newIdx];

    // Block cross-subcategory drags: a product cannot be moved into a
    // position occupied by a product from a different subcategory group.
    // This preserves the category → subcategory → product pick hierarchy.
    const draggedSub = dragged.subcategory_sort_order ?? 9999;
    const targetSub  = target.subcategory_sort_order ?? 9999;

    if (draggedSub !== targetSub) {
      const draggedLabel = dragged.subcategory_name ?? 'no subcategory';
      const targetLabel  = target.subcategory_name  ?? 'no subcategory';
      notify(
        `Cannot move "${dragged.name}" (${draggedLabel}) into the "${targetLabel}" group. ` +
        `Reorder subcategory pick positions in the Subcategories tab to change group order.`,
        { type: 'warning', autoHideDuration: 6000 }
      );
      return; // leave items unchanged — no optimistic update, no DB write
    }

    const reordered = arrayMove(items, oldIdx, newIdx);
    setItems(reordered);
    scheduleSave(reordered as SortableItem[]);
  };

  if (isLoading) return <Box sx={{ p: 2, color: 'text.secondary' }}>Loading products…</Box>;
  if (!items.length)
    return <Box sx={{ p: 2, color: 'text.secondary' }}>No products in this category.</Box>;

  return (
    <Box>
      <Alert severity="info" sx={{ mb: 2 }}>
        Products are grouped by subcategory pick order. You can drag products within their
        subcategory group to reorder them, but <strong>cannot drag across subcategory
        boundaries</strong> — use the <strong>Subcategories</strong> tab to change group order.
        Products with no subcategory always appear after all subcategorised groups.
      </Alert>
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
                  <TableCell>Subcategory</TableCell>
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
                    <TableCell>
                      {product.subcategory_name
                        ? <Chip label={product.subcategory_name} size="small" variant="outlined" color="primary" />
                        : <Typography variant="caption" color="text.disabled">—</Typography>
                      }
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
  <Show title={<CategoryTitle />} actions={<CategoryShowActions />}>
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
        <CategoryShowSubcategoriesTab />
      </TabbedShowLayout.Tab>
    </TabbedShowLayout>
  </Show>
);

type SubcategoryRecord = {
  id: number;
  name: string;
  sort_order: number;
  category: number;
  category_name: string;
};

/** Sortable subcategory list for the Subcategories tab — mirrors SortableProductsTab. */
function SortableSubcategoriesTab({ categoryId }: { categoryId: number }) {
  const { data, isLoading } = useGetList<SubcategoryRecord>('subcategories', {
    pagination: { page: 1, perPage: 500 },
    sort: { field: 'sort_order', order: 'ASC' },
    filter: { category: categoryId },
  });

  const [items, setItems] = useState<SubcategoryRecord[]>([]);
  const lastDataRef = useRef<typeof data | null>(null);
  const [newName, setNewName] = useState('');
  const [adding, setAdding] = useState(false);

  if (!isLoading && data && data !== lastDataRef.current) {
    lastDataRef.current = data;
    const sorted = [...data].sort(
      (a, b) => a.sort_order - b.sort_order || a.name.localeCompare(b.name)
    );
    Promise.resolve().then(() => setItems(sorted));
  }

  const { scheduleSave, saveStatus } = useDebouncedSortSave('subcategories');
  const [create] = useCreate();
  const notify = useNotify();
  const refresh = useRefresh();

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

  const handleAdd = async () => {
    const name = newName.trim();
    if (!name) return;
    setAdding(true);
    try {
      await create(
        'subcategories',
        { data: { name, category: categoryId, sort_order: 0 } },
        { returnPromise: true }
      );
      setNewName('');
      refresh();
      notify(`Subcategory "${name}" added`, { type: 'success' });
    } catch {
      notify('Failed to add subcategory', { type: 'error' });
    } finally {
      setAdding(false);
    }
  };

  const AddSubcategoryForm = (
    <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', mt: 2 }}>
      <MuiTextField
        size="small"
        label="New subcategory name"
        value={newName}
        onChange={(e) => setNewName(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Enter') handleAdd(); }}
        sx={{ flex: 1, maxWidth: 320 }}
        disabled={adding}
      />
      <Button
        variant="contained"
        size="small"
        startIcon={<AddIcon />}
        onClick={handleAdd}
        disabled={adding || !newName.trim()}
      >
        Add Subcategory
      </Button>
    </Box>
  );

  if (isLoading) return <Box sx={{ p: 2, color: 'text.secondary' }}>Loading subcategories…</Box>;

  if (!items.length)
    return (
      <Box sx={{ p: 1 }}>
        <Alert severity="info" sx={{ mb: 2 }}>
          No subcategories yet. Add one below — they'll appear in pick order on packing lists.
        </Alert>
        {AddSubcategoryForm}
      </Box>
    );

  return (
    <Box>
      <Alert severity="info" sx={{ mb: 2 }}>
        Drag rows to set the order subcategories appear on packing lists within this category.
        Subcategory pick order applies after category order and before individual products.
      </Alert>
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 1.5 }}>
        <Typography variant="body2" color="text.secondary">
          Drag rows to set the pick sequence for subcategories within this category.
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
                  <TableCell>Pick #</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {items.map((sub, idx) => (
                  <SortableRow key={sub.id} id={sub.id}>
                    <TableCell
                      sx={{ cursor: 'pointer', '&:hover': { textDecoration: 'underline' } }}
                      onClick={() => navigate(`/subcategories/${sub.id}`)}
                    >
                      {sub.name}
                    </TableCell>
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
      <Divider sx={{ mt: 2, mb: 1 }} />
      {AddSubcategoryForm}
    </Box>
  );
}

/** Thin wrapper — pulls categoryId from RA record context. */
function CategoryShowSubcategoriesTab() {
  const record = useRecordContext();
  if (!record) return null;
  return <SortableSubcategoriesTab categoryId={record.id as number} />;
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
  <List sort={{ field: 'sort_order', order: 'ASC' }}>
    <Datagrid rowClick="edit">
      <TextField source="name" />
      <TextField source="category_name" label="Category" />
      <NumberField source="sort_order" label="Pick #" />
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
      <NumberInput
        source="sort_order"
        label="Pick Position"
        helperText="0 = floats to top; drag to reorder in the Category detail view"
      />
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
      <NumberInput
        source="sort_order"
        label="Pick Position (optional)"
        defaultValue={0}
        helperText="Leave at 0 to appear at top, then drag into position"
      />
    </SimpleForm>
  </Create>
);
