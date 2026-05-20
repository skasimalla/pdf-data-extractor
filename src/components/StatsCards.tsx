"use client";

import { ClipboardList, Clock, CheckCircle, XCircle, Loader2 } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import type { OrderStats } from "@/lib/types";

interface StatCardProps {
  label: string;
  value: number;
  icon: React.ReactNode;
  color: string;
  bgColor: string;
}

function StatCard({ label, value, icon, color, bgColor }: StatCardProps) {
  return (
    <Card className="overflow-hidden">
      <CardContent className="p-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-gray-500">{label}</p>
            <p className="mt-1 text-3xl font-bold text-gray-900">{value.toLocaleString()}</p>
          </div>
          <div className={`rounded-full ${bgColor} p-3`}>
            <div className={color}>{icon}</div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

interface StatsCardsProps {
  stats: OrderStats | undefined;
  isLoading: boolean;
}

export function StatsCards({ stats, isLoading }: StatsCardsProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {Array.from({ length: 5 }).map((_, i) => (
          <Card key={i} className="overflow-hidden">
            <CardContent className="p-6">
              <div className="animate-pulse">
                <div className="h-4 w-20 rounded bg-gray-200" />
                <div className="mt-2 h-8 w-12 rounded bg-gray-200" />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  if (!stats) return null;

  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
      <StatCard
        label="Total Orders"
        value={stats.total}
        icon={<ClipboardList className="h-6 w-6" />}
        color="text-blue-600"
        bgColor="bg-blue-50"
      />
      <StatCard
        label="Pending"
        value={stats.pending}
        icon={<Clock className="h-6 w-6" />}
        color="text-yellow-600"
        bgColor="bg-yellow-50"
      />
      <StatCard
        label="Processing"
        value={stats.processing}
        icon={<Loader2 className="h-6 w-6" />}
        color="text-purple-600"
        bgColor="bg-purple-50"
      />
      <StatCard
        label="Completed"
        value={stats.completed}
        icon={<CheckCircle className="h-6 w-6" />}
        color="text-green-600"
        bgColor="bg-green-50"
      />
      <StatCard
        label="Cancelled"
        value={stats.cancelled}
        icon={<XCircle className="h-6 w-6" />}
        color="text-red-500"
        bgColor="bg-red-50"
      />
    </div>
  );
}
