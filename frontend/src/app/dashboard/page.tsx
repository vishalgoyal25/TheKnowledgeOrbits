/**
 * Enhanced User Dashboard - Rebuilt with Analytics & Quick Actions
 */

'use client';

import { useDashboard } from '@/lib/hooks/useDashboard';
import DashboardOverview from '@/components/dashboard/DashboardOverview';
import PerformanceChart from '@/components/dashboard/PerformanceChart';
import TopicMasterySection from '@/components/dashboard/TopicMasterySection';
import InsightsSection from '@/components/dashboard/InsightsSection';
import RecentActivity from '@/components/dashboard/RecentActivity';
import { useAuth } from '@/lib/auth/useAuth';
import { Button } from '@/components/ui/button';
import { Loader2, Sparkles, BookOpen, FileText, Zap } from 'lucide-react';
import Link from 'next/link';

const MOCK_DATA = {
    overview: {
        total_articles_read: 12,
        total_quizzes_taken: 5,
        current_streak: 4,
        syllabus_coverage: 15.5,
    },
    performance: {
        weekly: {
            period: 'Feb 10 - Feb 16',
            start_date: '2026-02-10',
            end_date: '2026-02-16',
            total_articles: 8,
            total_quizzes: 3,
            average_score: 85,
            daily_data: [
                { date: '2026-02-10', articles: 1, quizzes: 0, avg_score: 0 },
                { date: '2026-02-11', articles: 2, quizzes: 1, avg_score: 80 },
                { date: '2026-02-12', articles: 1, quizzes: 0, avg_score: 0 },
                { date: '2026-02-13', articles: 2, quizzes: 1, avg_score: 90 },
                { date: '2026-02-14', articles: 0, quizzes: 0, avg_score: 0 },
                { date: '2026-02-15', articles: 1, quizzes: 1, avg_score: 85 },
                { date: '2026-02-16', articles: 1, quizzes: 0, avg_score: 0 },
            ],
        },
        topic_count: 5,
        average_mastery: 72,
    },
    topics: {
        weak: [
            { topic_id: '1', topic_name: 'Vedic Period', mastery_score: 35, questions_attempted: 10 },
            { topic_id: '2', topic_name: 'Preamble', mastery_score: 42, questions_attempted: 8 },
        ],
        strong: [
            { topic_id: '3', topic_name: 'Fundamental Rights', mastery_score: 88, questions_attempted: 15 },
            { topic_id: '4', topic_name: 'Indus Valley', mastery_score: 82, questions_attempted: 12 },
        ],
    },
    recent_activity: [
        { event_type: 'article_read', event_data: { title: 'Mauryan Empire' }, created_at: new Date().toISOString() },
        { event_type: 'quiz_completed', event_data: { title: 'Polity Basics', score: 90 }, created_at: new Date(Date.now() - 86400000).toISOString() },
    ],
    insights: [
        { type: 'strength', data: { message: 'You are performing exceptionally well in Ancient History!' }, generated_at: new Date().toISOString() },
        { type: 'warning', data: { message: 'Your streak is at risk! Read one article today.' }, generated_at: new Date().toISOString() },
    ],
};

export default function DashboardPage() {
    const { isAuthenticated, isLoading: authLoading } = useAuth();
    const { data: realData, isLoading: dataLoading, error } = useDashboard(isAuthenticated);

    // Determine loading state
    const isLoading = authLoading || (isAuthenticated && dataLoading);

    // Choose data: Real if authenticated and available, Mock as fallback
    const data = (isAuthenticated && realData) ? realData : MOCK_DATA;

    if (isLoading) {
        return (
            <div className="flex items-center justify-center min-h-screen bg-gray-50">
                <div className="text-center space-y-4">
                    <Loader2 className="h-12 w-12 animate-spin text-blue-600 mx-auto" />
                    <p className="text-gray-500 font-medium animate-pulse">Loading your dashboard...</p>
                </div>
            </div>
        );
    }

    if (isAuthenticated && error) {
        return (
            <div className="p-8 text-center max-w-md mx-auto mt-20">
                <div className="bg-red-50 border border-red-200 rounded-lg p-6">
                    <h2 className="text-red-800 font-bold mb-2">Error Loading Dashboard</h2>
                    <p className="text-red-600 mb-4">We couldn't fetch your learning data right now.</p>
                    <Button onClick={() => window.location.reload()} variant="outline" className="border-red-200 text-red-700 hover:bg-red-100">
                        Try Refreshing
                    </Button>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-50">
            <div className="max-w-7xl mx-auto p-6 space-y-8">
                {/* Guest CTA Banner */}
                {!isAuthenticated && (
                    <div className="bg-gradient-to-r from-blue-600 to-indigo-700 rounded-2xl p-6 text-white shadow-lg flex flex-col md:flex-row items-center justify-between gap-6">
                        <div className="space-y-2">
                            <h2 className="text-2xl font-bold italic">Unlock Your Full Potential! 🚀</h2>
                            <p className="text-blue-100 max-w-lg">
                                You are currently viewing a <span className="font-bold underline">preview</span> of the dashboard. Sign up now to track your actual syllabus coverage, get AI-powered insights, and ace the UPSC exam!
                            </p>
                        </div>
                        <div className="flex gap-4">
                            <Link href="/auth/register">
                                <Button className="bg-white text-blue-600 hover:bg-blue-50 font-bold px-8">
                                    Join Now - It's Free
                                </Button>
                            </Link>
                            <Link href="/auth/login">
                                <Button variant="outline" className="border-white text-white bg-blue-600/20 hover:bg-white hover:text-blue-600 transition-all font-semibold">
                                    Sign In
                                </Button>
                            </Link>
                        </div>
                    </div>
                )}

                {/* Dashboard Header */}
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div>
                        <h1 className="text-4xl font-extrabold text-gray-900 tracking-tight">Dashboard</h1>
                        <p className="text-gray-500 mt-1">
                            {isAuthenticated ? 'Track your progress and orbits of knowledge.' : 'Experience the future of UPSC preparation.'}
                        </p>
                    </div>
                    {isAuthenticated && (
                        <div className="flex items-center gap-3">
                            <Link href="/generate">
                                <Button className="bg-blue-600 hover:bg-blue-700 shadow-md transition-all hover:scale-105 gap-2">
                                    <Sparkles className="h-4 w-4" />
                                    New Article
                                </Button>
                            </Link>
                        </div>
                    )}
                </div>

                {/* 1. Statistics Overview */}
                <DashboardOverview data={data!.overview} />

                {/* 2. Main Analytics Section */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                    <PerformanceChart data={data!.performance.weekly} />
                    <InsightsSection insights={data!.insights} />
                </div>

                {/* 3. Mastery Section */}
                <TopicMasterySection
                    weak={data!.topics.weak}
                    strong={data!.topics.strong}
                />

                {/* 4. Quick Actions */}
                <section className="bg-white p-8 rounded-2xl border border-gray-100 shadow-sm">
                    <h2 className="text-2xl font-bold mb-6 text-gray-900 flex items-center gap-2">
                        <Zap className="h-6 w-6 text-yellow-500" />
                        Quick Actions
                    </h2>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        <Link href="/generate">
                            <Button variant="outline" className="w-full h-32 flex-col gap-2 hover:bg-blue-50 hover:border-blue-200 transition-all group" size="lg">
                                <Sparkles className="h-8 w-8 text-blue-600 group-hover:scale-110 transition-transform" />
                                <span className="font-semibold text-gray-700">Generate Article</span>
                            </Button>
                        </Link>

                        <Link href="/topics">
                            <Button variant="outline" className="w-full h-32 flex-col gap-2 hover:bg-green-50 hover:border-green-200 transition-all group" size="lg">
                                <BookOpen className="h-8 w-8 text-green-600 group-hover:scale-110 transition-transform" />
                                <span className="font-semibold text-gray-700">Browse Topics</span>
                            </Button>
                        </Link>

                        <Link href="/articles">
                            <Button variant="outline" className="w-full h-32 flex-col gap-2 hover:bg-purple-50 hover:border-purple-200 transition-all group" size="lg">
                                <FileText className="h-8 w-8 text-purple-600 group-hover:scale-110 transition-transform" />
                                <span className="font-semibold text-gray-700">Read Articles</span>
                            </Button>
                        </Link>
                    </div>
                </section>

                {/* 5. Recent Activity Feed */}
                <RecentActivity activities={data!.recent_activity} />
            </div>
        </div>
    );
}


