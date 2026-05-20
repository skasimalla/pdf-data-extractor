"use client";

import { useState, useCallback } from "react";
import useSWR from "swr";
import { FileText, Activity, BookOpen } from "lucide-react";
import { StatsCards } from "@/components/StatsCards";
import { OrderTable } from "@/components/OrderTable";
import { ActivityFeed } from "@/components/ActivityFeed";
import { fetchOrderStats } from "@/lib/api";

export default function DashboardPage() {
  const [refreshKey, setRefreshKey] = useState(0);

  const { data: stats, isLoading: statsLoading, mutate: refreshStats } = useSWR(
    "/orders/stats",
    fetchOrderStats,
    { refreshInterval: 30000 }
  );

  const onDataChange = useCallback(() => {
    refreshStats();
    setRefreshKey((k) => k + 1);
  }, [refreshStats]);

  return (
    <div className="flex h-full min-h-screen flex-col">
      {/* Header */}
      <header className="border-b border-gray-200 bg-white px-6 py-4 shadow-sm">
        <div className="mx-auto flex max-w-screen-2xl items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-600">
              <FileText className="h-5 w-5 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-gray-900 leading-tight">MedOrders</h1>
              <p className="text-xs text-gray-500">Patient Order Management</p>
            </div>
          </div>
          <nav className="hidden items-center gap-6 sm:flex">
            <a
              href="/docs"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-900 transition-colors"
            >
              <BookOpen className="h-4 w-4" />
              API Docs
            </a>
            <a
              href="#activity"
              className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-900 transition-colors"
            >
              <Activity className="h-4 w-4" />
              Activity
            </a>
          </nav>
        </div>
      </header>

      {/* Main content */}
      <main className="mx-auto w-full max-w-screen-2xl flex-1 p-6">
        {/* Stats */}
        <section className="mb-6">
          <StatsCards stats={stats} isLoading={statsLoading} />
        </section>

        {/* Orders + Activity Feed */}
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1fr_360px]" id="activity">
          <OrderTable onDataChange={onDataChange} />
          <aside className="h-[640px] xl:h-auto">
            <ActivityFeed refreshKey={refreshKey} />
          </aside>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-200 bg-white px-6 py-4">
        <div className="mx-auto max-w-screen-2xl text-center text-xs text-gray-400">
          MedOrders v1.0 — FastAPI + Next.js — Deployed on Vercel
        </div>
      </footer>
    </div>
  );
}
