'use client';

import React, { createContext, useContext, useState, useEffect } from 'react';

interface SidebarContextType {
    isCollapsed: boolean;
    setIsCollapsed: (value: boolean) => void;
    toggleSidebar: () => void;
}

const SidebarContext = createContext<SidebarContextType | undefined>(undefined);

export function SidebarProvider({ children }: { children: React.ReactNode }) {
    const [isCollapsed, setIsCollapsed] = useState(false);

    // Initialize from localStorage if available
    useEffect(() => {
        const saved = localStorage.getItem('sidebar-collapsed');
        if (saved !== null) {
            setIsCollapsed(JSON.parse(saved));
        }
    }, []);

    const handleSetCollapsed = (value: boolean) => {
        setIsCollapsed(value);
        localStorage.setItem('sidebar-collapsed', JSON.stringify(value));
    };

    const toggleSidebar = () => {
        handleSetCollapsed(!isCollapsed);
    };

    return (
        <SidebarContext.Provider
            value={{
                isCollapsed,
                setIsCollapsed: handleSetCollapsed,
                toggleSidebar
            }}
        >
            {children}
        </SidebarContext.Provider>
    );
}

export function useSidebar() {
    const context = useContext(SidebarContext);
    if (context === undefined) {
        throw new Error('useSidebar must be used within a SidebarProvider');
    }
    return context;
}
