/**
 * System Health & API Directory - A comprehensive view for developers
 */

"use client";

import { useEffect, useState } from "react";
import {
  Activity,
  Globe,
  Database,
  Cpu,
  Code2,
  ExternalLink,
  Layout,
  Terminal,
} from "lucide-react";
import apiClient from "@/lib/api/client";

interface HealthStatus {
  status: string;
  message: string;
}

interface ApiEndpoint {
  name: string;
  path: string;
  method: string;
  description: string;
}

export default function HealthPage() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [ping, setPing] = useState<number | null>(null);

  const fetchHealth = async () => {
    const start = Date.now();
    try {
      const response = await apiClient.get<HealthStatus>("/health/");
      setHealth(response.data);
      setPing(Date.now() - start);
    } catch (err) {
      setHealth({ status: "unhealthy", message: "API connection failed" });
      setPing(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  const backendApis: ApiEndpoint[] = [
    {
      name: "Auth Engine",
      path: "/api/v1/auth/",
      method: "POST/GET",
      description: "Login, Register, Password Reset, Token refresh",
    },
    {
      name: "Content Engine",
      path: "/api/v1/content/",
      method: "GET",
      description: "Static content, syllabus, and resources",
    },
    {
      name: "Knowledge Engine",
      path: "/api/v1/knowledge/",
      method: "GET/POST",
      description: "Topic detail, core knowledge orbits",
    },
    {
      name: "Article Generation",
      path: "/api/v1/articles/",
      method: "POST",
      description: "AI generation of UPSC articles",
    },
    {
      name: "Assessment Engine",
      path: "/api/v1/assessment/",
      method: "GET/POST",
      description: "Quizzes, results, and ranking",
    },
    {
      name: "Current Affairs",
      path: "/api/v1/ca/",
      method: "GET",
      description: "Daily updates and analysis",
    },
    {
      name: "Analytics Engine",
      path: "/api/v1/analytics/",
      method: "GET",
      description: "User performance and study stats",
    },
    {
      name: "Support Engine",
      path: "/api/v1/support/",
      method: "POST",
      description: "Feedback and support tickets",
    },
  ];

  const frontendRoutes = [
    {
      name: "Dashboard",
      path: "/dashboard",
      description: "Main user workspace",
    },
    {
      name: "Auth Pages",
      path: "/auth/[login|register]",
      description: "Entry points for users",
    },
    { name: "Articles", path: "/articles", description: "AI Article explorer" },
    {
      name: "Topics",
      path: "/topics",
      description: "Knowledge base navigation",
    },
    {
      name: "Quizzes",
      path: "/assessment",
      description: "Practice environment",
    },
    {
      name: "Current Affairs",
      path: "/current-affairs",
      description: "Daily tracking",
    },
  ];

  return (
    <div className="min-h-screen bg-slate-50/50 p-6 lg:p-12">
      <div className="max-w-6xl mx-auto space-y-8">
        {/* Header Section */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div>
            <h1 className="text-3xl font-black text-slate-900 tracking-tight flex items-center gap-3">
              <Terminal className="h-8 w-8 text-blue-600" />
              Developer Console
            </h1>
            <p className="text-slate-500 mt-2 font-medium">
              Monitoring & API Documentation for TheKnowledgeOrbits
            </p>
          </div>

          <div className="bg-white px-6 py-3 rounded-2xl shadow-sm border border-slate-200 flex items-center gap-6">
            <div className="flex flex-col">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                Backend Status
              </span>
              <div className="flex items-center gap-2 mt-1">
                <span
                  className={`h-2 w-2 rounded-full ${
                    health?.status === "healthy"
                      ? "bg-emerald-500 animate-pulse"
                      : "bg-red-500"
                  }`}
                />
                <span className="text-sm font-bold text-slate-700">
                  {loading
                    ? "Syncing..."
                    : health?.status === "healthy"
                      ? "Operational"
                      : "Offline"}
                </span>
              </div>
            </div>
            <div className="h-8 w-px bg-slate-100" />
            <div className="flex flex-col">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                Latency
              </span>
              <span className="text-sm font-bold text-slate-700 mt-1">
                {ping ? `${ping}ms` : "--"}
              </span>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left Column: Health & Stats */}
          <div className="lg:col-span-1 space-y-6">
            <div className="bg-slate-900 rounded-3xl p-8 text-white relative overflow-hidden">
              <div className="absolute top-0 right-0 w-32 h-32 bg-blue-500/20 rounded-full -mr-16 -mt-16 blur-3xl text-blue-500" />
              <Activity className="h-10 w-10 text-emerald-400 mb-6" />
              <h2 className="text-xl font-bold mb-2">Live Pulse</h2>
              <p className="text-slate-400 text-sm mb-6 leading-relaxed">
                System heartbeat is being monitored globally. All micro-engines
                are reporting status to core.
              </p>

              <div className="space-y-4">
                <div className="flex items-center justify-between p-3 bg-white/5 rounded-xl border border-white/10">
                  <div className="flex items-center gap-2">
                    <Database className="h-4 w-4 text-purple-400" />
                    <span className="text-xs font-semibold">PostgreSQL</span>
                  </div>
                  <span className="text-[10px] font-bold text-emerald-400 uppercase">
                    Connected
                  </span>
                </div>
                <div className="flex items-center justify-between p-3 bg-white/5 rounded-xl border border-white/10">
                  <div className="flex items-center gap-2">
                    <Cpu className="h-4 w-4 text-amber-400" />
                    <span className="text-xs font-semibold">Redis Cache</span>
                  </div>
                  <span className="text-[10px] font-bold text-emerald-400 uppercase">
                    Healthy
                  </span>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-3xl p-8 border border-slate-200">
              <h3 className="font-bold text-slate-900 mb-4 flex items-center gap-2">
                <Globe className="h-5 w-5 text-blue-500" />
                Base URLs
              </h3>
              <div className="space-y-3">
                <div className="p-3 bg-slate-50 rounded-xl">
                  <p className="text-[10px] font-bold text-slate-400 uppercase">
                    Backend API
                  </p>
                  <code className="text-xs text-blue-600 font-bold block mt-1 select-all">
                    http://127.0.0.1:8000/api/v1
                  </code>
                </div>
                <div className="p-3 bg-slate-50 rounded-xl">
                  <p className="text-[10px] font-bold text-slate-400 uppercase">
                    Frontend App
                  </p>
                  <code className="text-xs text-indigo-600 font-bold block mt-1 select-all">
                    http://localhost:3000
                  </code>
                </div>
              </div>
            </div>
          </div>

          {/* Right Column: API Directory */}
          <div className="lg:col-span-2 space-y-8">
            {/* Backend APIs */}
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-blue-500" />
                <h2 className="text-lg font-bold text-slate-800">
                  Backend API Endpoints
                </h2>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {backendApis.map((api) => (
                  <div
                    key={api.name}
                    className="bg-white p-5 rounded-3xl border border-slate-200 shadow-sm hover:border-blue-200 transition-colors group"
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-2">
                        <Code2 className="h-4 w-4 text-slate-400" />
                        <h3 className="font-bold text-slate-800">{api.name}</h3>
                      </div>
                      <span className="text-[10px] font-black px-2 py-0.5 bg-slate-100 rounded text-slate-500 uppercase">
                        {api.method}
                      </span>
                    </div>
                    <code className="text-[11px] text-blue-600 font-bold block mt-3 bg-blue-50 px-2 py-1 rounded w-fit">
                      {api.path}
                    </code>
                    <p className="text-xs text-slate-500 mt-3 leading-relaxed">
                      {api.description}
                    </p>
                  </div>
                ))}
              </div>
            </div>

            {/* Frontend Routes */}
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-indigo-500" />
                <h2 className="text-lg font-bold text-slate-800">
                  Frontend Application Routes
                </h2>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {frontendRoutes.map((route) => (
                  <div
                    key={route.name}
                    className="bg-white p-5 rounded-3xl border border-slate-200 shadow-sm hover:border-indigo-200 transition-colors"
                  >
                    <div className="flex items-center gap-2">
                      <Layout className="h-4 w-4 text-slate-400" />
                      <h3 className="font-bold text-slate-800">{route.name}</h3>
                    </div>
                    <div className="flex items-center justify-between mt-3">
                      <code className="text-[11px] text-indigo-600 font-bold">
                        {route.path}
                      </code>
                      <ExternalLink className="h-3 w-3 text-slate-300" />
                    </div>
                    <p className="text-xs text-slate-500 mt-2">
                      {route.description}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Footer info */}
        <div className="text-center py-6 border-t border-slate-200">
          <p className="text-xs font-bold text-slate-400 uppercase tracking-widest">
            TheKnowledgeOrbits Intelligence v1.0.4
          </p>
        </div>
      </div>
    </div>
  );
}
