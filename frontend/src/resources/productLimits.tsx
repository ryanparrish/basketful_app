/**
 * ProductLimit Resource Components
 */
import {
  List,
  Datagrid,
  TextField,
  NumberField,
  Edit,
  Create,
  SimpleForm,
  TextInput,
  NumberInput,
  SelectInput,
  ReferenceInput,
  Show,
  SimpleShowLayout,
  EditButton,
  ShowButton,
  required,
  ReferenceField,
  FunctionField,
  type RaRecord,
} from 'react-admin';
import { Chip, Box } from '@mui/material';

// Limit scope choices matching Django model
const limitScopeChoices = [
  { id: 'per_adult', name: 'Per Adult' },
  { id: 'per_child', name: 'Per Child' },
  { id: 'per_infant', name: 'Per Infant' },
  { id: 'per_household', name: 'Per Household' },
  { id: 'per_order', name: 'Per Order' },
];

// Helper function to format limit explanation
const getLimitExplanation = (record: RaRecord) => {
  if (!record) return '';
  
  const scope = record.limit_scope || 'per_household';
  const limit = record.limit || 0;
  const multiplier = record.active_pause_multiplier || 1;
  const effectiveLimit = record.effective_limit || limit;
  const pauseName = record.pause_name;
  
  // Base explanation text
  const explanations: { [key: string]: (l: number, el: number) => string } = {
    'per_adult': (l, el) => `${l}${multiplier > 1 ? ` → ${el}` : ''} per adult (e.g., 2 adults = ${el * 2} allowed)`,
    'per_child': (l, el) => `${l}${multiplier > 1 ? ` → ${el}` : ''} per child (e.g., 3 children = ${el * 3} allowed)`,
    'per_infant': (l, el) => `${l}${multiplier > 1 ? ` → ${el}` : ''} per infant (e.g., 1 infant = ${el * 1} allowed)`,
    'per_household': (l, el) => `${l}${multiplier > 1 ? ` → ${el}` : ''} per household member (e.g., household of 4 = ${el * 4} allowed)`,
    'per_order': (l, el) => `${l}${multiplier > 1 ? ` → ${el}` : ''} total per order (fixed limit)`,
  };
  
  const explanationText = (explanations[scope] || (() => `${limit} items`))(limit, effectiveLimit);
  
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
      {multiplier > 1 && (
        <Chip 
          label={`${multiplier}x Pause`} 
          color="warning" 
          size="small"
          title={pauseName || 'Active Program Pause'}
        />
      )}
      <span>{explanationText}</span>
    </Box>
  );
};

export const ProductLimitList = () => (
  <List sort={{ field: 'category_name', order: 'ASC' }}>
    <Datagrid rowClick="edit">
      <TextField source="name" />
      <TextField source="category_name" label="Category" />
      <TextField source="subcategory_name" label="Subcategory" emptyText="All" />
      <NumberField source="limit" />
      <FunctionField 
        label="Limit Scope" 
        render={(record: RaRecord) => {
          const choice = limitScopeChoices.find(c => c.id === record.limit_scope);
          return choice ? choice.name : record.limit_scope;
        }}
      />
      <FunctionField 
        label="How It Works" 
        render={getLimitExplanation}
      />
      <EditButton />
      <ShowButton />
    </Datagrid>
  </List>
);

export const ProductLimitShow = () => (
  <Show>
    <SimpleShowLayout>
      <TextField source="name" />
      <ReferenceField source="category" reference="categories" link="show">
        <TextField source="name" />
      </ReferenceField>
      <ReferenceField source="subcategory" reference="subcategories" link={false} emptyText="All products in category">
        <TextField source="name" />
      </ReferenceField>
      <NumberField source="limit" />
      <FunctionField 
        label="Limit Scope" 
        render={(record: RaRecord) => {
          const choice = limitScopeChoices.find(c => c.id === record.limit_scope);
          return choice ? choice.name : record.limit_scope;
        }}
      />
      <FunctionField 
        label="How This Limit Works" 
        render={getLimitExplanation}
      />
      <TextField source="notes" />
    </SimpleShowLayout>
  </Show>
);

export const ProductLimitEdit = () => (
  <Edit>
    <SimpleForm>
      <TextInput source="name" validate={required()} helperText="Give this limit a descriptive name" fullWidth />
      
      <ReferenceInput source="category" reference="categories">
        <SelectInput optionText="name" label="Category" helperText="Select the category this limit applies to" validate={required()} />
      </ReferenceInput>
      
      <ReferenceInput source="subcategory" reference="subcategories">
        <SelectInput 
          optionText="name" 
          label="Subcategory (Optional)" 
          helperText="Leave empty to apply limit to ALL products in the category, or select a specific subcategory" 
        />
      </ReferenceInput>
      
      <NumberInput 
        source="limit" 
        validate={required()} 
        min={1}
        helperText="Base number allowed"
      />
      
      <SelectInput 
        source="limit_scope" 
        choices={limitScopeChoices}
        validate={required()}
        helperText="How the limit is multiplied: per adult/child/infant/household member, or fixed per order"
      />
      
      <TextInput 
        source="notes" 
        multiline 
        rows={3} 
        fullWidth
        helperText="Optional notes about this limit"
      />
    </SimpleForm>
  </Edit>
);

export const ProductLimitCreate = () => (
  <Create>
    <SimpleForm>
      <TextInput source="name" validate={required()} helperText="Give this limit a descriptive name" fullWidth />
      
      <ReferenceInput source="category" reference="categories">
        <SelectInput optionText="name" label="Category" helperText="Select the category this limit applies to" validate={required()} />
      </ReferenceInput>
      
      <ReferenceInput source="subcategory" reference="subcategories">
        <SelectInput 
          optionText="name" 
          label="Subcategory (Optional)" 
          helperText="Leave empty to apply limit to ALL products in the category, or select a specific subcategory" 
        />
      </ReferenceInput>
      
      <NumberInput 
        source="limit" 
        validate={required()} 
        min={1}
        defaultValue={2}
        helperText="Base number allowed"
      />
      
      <SelectInput 
        source="limit_scope" 
        choices={limitScopeChoices}
        validate={required()}
        defaultValue="per_household"
        helperText="How the limit is multiplied: per adult/child/infant/household member, or fixed per order"
      />
      
      <TextInput 
        source="notes" 
        multiline 
        rows={3} 
        fullWidth
        helperText="Optional notes about this limit"
      />
    </SimpleForm>
  </Create>
);
