/**
 * Dashboard Layout
 */

import React from 'react';
import Sidebar from '@/components/layout/sidebar';

export default function DashboardLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <>
            {children}
        </>
    );
}
