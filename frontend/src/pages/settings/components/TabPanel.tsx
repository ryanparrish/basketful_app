import type { TabPanelProps } from '../types';

export const TabPanel = ({ children, value, index }: TabPanelProps) => (
  <div hidden={value !== index} style={{ padding: '20px 0' }}>
    {value === index && children}
  </div>
);
