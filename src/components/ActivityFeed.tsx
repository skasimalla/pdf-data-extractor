"use client";

import { useState } from "react";
import useSWR from "swr";
import { formatDistanceToNow, parseISO } from "date-fns";
import { Activity, RefreshCw, ChevronLeft, ChevronRight } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { fetchLogs, logsKey } from "@/lib/api";

const METHOD_COLOR: Record<string, React.ComponentProps<typeof Badge>["variant"]> = {
  GET: "secondary",
  POST: "default",
  PUT: "warning",
  DELETE: "destructive",
  PATCH: "warning",
};

function StatusBadge({ code }: { code: number | null }) {
  if (!code) return null;
  const variant =
    code < 300 ? "success" : code < 400 ? "warning" : "destructive";
  return <Badge variant={variant}>{code}</Badge>;
}

interface ActivityFeedProps {
  refreshKey?: number;
}

export function ActivityFeed({ refreshKey }: ActivityFeedProps) {
  const [page, setPage] = useState(1);
  const perPage = 20;

  const key = logsKey(page, perPage);
  const { data, isLoading, mutate } = useSWR(key, fetchLogs, {
    refreshInterval: 15000,
    keepPreviousData: true,
  });

  const logs = data?.items ?? [];
  const total = data?.total ?? 0;
  const pages = data?.pages ?? 1;

  return (
    <Card className="flex h-full flex-col">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-base">
            <Activity className="h-4 w-4 text-blue-600" />
            Activity Log
            {!isLoading && (
              <span className="text-sm font-normal text-gray-400">({total})</span>
            )}
          </CardTitle>
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => mutate()}>
            <RefreshCw className="h-3.5 w-3.5" />
          </Button>
        </div>
      </CardHeader>

      <CardContent className="flex-1 overflow-y-auto p-0">
        {isLoading ? (
          <div className="flex items-center justify-center py-10">
            <RefreshCw className="h-5 w-5 animate-spin text-gray-300" />
          </div>
        ) : logs.length === 0 ? (
          <div className="py-10 text-center text-sm text-gray-400">No activity yet</div>
        ) : (
          <ul className="divide-y divide-gray-100">
            {logs.map((log) => (
              <li key={log.id} className="px-4 py-3 hover:bg-gray-50 transition-colors">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <Badge variant={METHOD_COLOR[log.request_method] ?? "secondary"} className="shrink-0 font-mono text-xs">
                      {log.request_method}
                    </Badge>
                    <span className="truncate font-mono text-xs text-gray-600">
                      {log.request_path}
                    </span>
                  </div>
                  <StatusBadge code={log.status_code} />
                </div>
                <div className="mt-1 flex items-center gap-2 text-xs text-gray-400">
                  <span>{formatDistanceToNow(parseISO(log.timestamp), { addSuffix: true })}</span>
                  {log.duration_ms !== null && (
                    <span className="text-gray-300">•</span>
                  )}
                  {log.duration_ms !== null && (
                    <span>{log.duration_ms.toFixed(1)}ms</span>
                  )}
                  {log.ip_address && (
                    <>
                      <span className="text-gray-300">•</span>
                      <span>{log.ip_address}</span>
                    </>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>

      {pages > 1 && (
        <div className="flex items-center justify-between border-t border-gray-100 px-4 py-3">
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="text-xs text-gray-500">
            {page} / {pages}
          </span>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={() => setPage((p) => Math.min(pages, p + 1))}
            disabled={page === pages}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      )}
    </Card>
  );
}
