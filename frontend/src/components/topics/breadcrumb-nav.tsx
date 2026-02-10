/**
 * Breadcrumb navigation for topic hierarchy
 */

'use client';

import Link from 'next/link';
import { Topic } from '@/lib/types';
import {
    Breadcrumb,
    BreadcrumbItem,
    BreadcrumbLink,
    BreadcrumbList,
    BreadcrumbPage,
    BreadcrumbSeparator,
} from '@/components/ui/breadcrumb';
import { Home } from 'lucide-react';

interface BreadcrumbNavProps {
    topic?: Topic;
    currentPage?: string;
}

export default function BreadcrumbNav({ topic, currentPage }: BreadcrumbNavProps) {
    return (
        <Breadcrumb>
            <BreadcrumbList>
                <BreadcrumbItem>
                    <BreadcrumbLink asChild>
                        <Link href="/" className="flex items-center gap-1">
                            <Home className="h-4 w-4" />
                            <span>Home</span>
                        </Link>
                    </BreadcrumbLink>
                </BreadcrumbItem>

                <BreadcrumbSeparator />

                <BreadcrumbItem>
                    <BreadcrumbLink asChild>
                        <Link href="/topics">Topics</Link>
                    </BreadcrumbLink>
                </BreadcrumbItem>

                {topic && (
                    <>
                        <BreadcrumbSeparator />

                        {topic.subject && (
                            <>
                                <BreadcrumbItem>
                                    <BreadcrumbLink>{topic.subject_name}</BreadcrumbLink>
                                </BreadcrumbItem>
                                <BreadcrumbSeparator />
                            </>
                        )}

                        {topic.module && (
                            <>
                                <BreadcrumbItem>
                                    <BreadcrumbLink>{topic.module_name}</BreadcrumbLink>
                                </BreadcrumbItem>
                                <BreadcrumbSeparator />
                            </>
                        )}

                        <BreadcrumbItem>
                            <BreadcrumbPage>{currentPage || topic.name}</BreadcrumbPage>
                        </BreadcrumbItem>
                    </>
                )}
            </BreadcrumbList>
        </Breadcrumb>
    );
}
