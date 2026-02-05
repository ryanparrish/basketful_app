/**
 * Permission Context - Provides permission checking throughout the app
 * 
 * This context fetches and caches user permissions from the backend,
 * and provides helper functions to check permissions.
 */
import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import { usePermissions } from 'react-admin';

interface PermissionData {
  groups: string[];
  group_ids: number[];
  is_staff: boolean;
  is_superuser: boolean;
  permissions: string[];
}

interface PermissionContextType {
  permissions: PermissionData | null;
  loading: boolean;
  hasPermission: (permission: string) => boolean;
  hasAnyPermission: (permissions: string[]) => boolean;
  hasGroup: (group: string) => boolean;
  isStaff: boolean;
  isSuperuser: boolean;
  refetch: () => void;
}

const PermissionContext = createContext<PermissionContextType | undefined>(undefined);

export const PermissionProvider = ({ children }: { children: ReactNode }) => {
  const { permissions: rawPermissions, isLoading } = usePermissions();
  const [permissions, setPermissions] = useState<PermissionData | null>(null);
  const [refetchKey, setRefetchKey] = useState(0);

  useEffect(() => {
    if (rawPermissions && !isLoading) {
      setPermissions(rawPermissions as PermissionData);
    }
  }, [rawPermissions, isLoading, refetchKey]);

  const hasPermission = (permission: string): boolean => {
    if (!permissions) return false;
    if (permissions.is_superuser) return true;
    if (permissions.permissions.includes('*')) return true;
    return permissions.permissions.includes(permission);
  };

  const hasAnyPermission = (perms: string[]): boolean => {
    if (!permissions) return false;
    if (permissions.is_superuser) return true;
    if (permissions.permissions.includes('*')) return true;
    return perms.some(p => permissions.permissions.includes(p));
  };

  const hasGroup = (group: string): boolean => {
    if (!permissions) return false;
    return permissions.groups.includes(group);
  };

  const refetch = () => {
    // Clear cache and trigger refetch
    localStorage.removeItem('userPermissions');
    localStorage.removeItem('permissionsCacheTime');
    setRefetchKey(prev => prev + 1);
  };

  return (
    <PermissionContext.Provider
      value={{
        permissions,
        loading: isLoading,
        hasPermission,
        hasAnyPermission,
        hasGroup,
        isStaff: permissions?.is_staff || false,
        isSuperuser: permissions?.is_superuser || false,
        refetch,
      }}
    >
      {children}
    </PermissionContext.Provider>
  );
};

export const usePermissionContext = () => {
  const context = useContext(PermissionContext);
  if (context === undefined) {
    throw new Error('usePermissionContext must be used within a PermissionProvider');
  }
  return context;
};
