import React, { createContext, useState, useContext, ReactNode, useEffect } from 'react';

interface TenantContextType {
  tenantId: string | null;
  setTenantId: (tenantId: string | null) => void;
}

const TenantContext = createContext<TenantContextType | undefined>(undefined);

export const TenantProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [tenantId, setTenantIdState] = useState<string | null>(() => {
    try {
      return localStorage.getItem('ui_tenant_id');
    } catch {
      return null;
    }
  });

  const setTenantId = (newTenantId: string | null) => {
    try {
      if (newTenantId) {
        localStorage.setItem('ui_tenant_id', newTenantId);
      } else {
        localStorage.removeItem('ui_tenant_id');
      }
    } catch (e) {
      console.error('Failed to update tenantId in localStorage', e);
    }
    setTenantIdState(newTenantId);
  };

  useEffect(() => {
    const handleStorageChange = () => {
      try {
        setTenantIdState(localStorage.getItem('ui_tenant_id'));
      } catch (e) {
        console.error('Failed to read tenantId from localStorage', e);
      }
    };

    window.addEventListener('storage', handleStorageChange);
    return () => {
      window.removeEventListener('storage', handleStorageChange);
    };
  }, []);

  return (
    <TenantContext.Provider value={{ tenantId, setTenantId }}>
      {children}
    </TenantContext.Provider>
  );
};

export const useTenant = (): TenantContextType => {
  const context = useContext(TenantContext);
  if (context === undefined) {
    throw new Error('useTenant must be used within a TenantProvider');
  }
  return context;
};
