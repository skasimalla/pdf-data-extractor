import type {
  Order,
  OrderCreate,
  OrderUpdate,
  OrderListResponse,
  UploadResponse,
  ActivityLogListResponse,
  OrderStats,
  OrderStatus,
} from "./types";

const BASE = "/v1";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY ?? "dev-api-key-change-me";

async function request<T>(
  path: string,
  init: RequestInit = {}
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "X-API-Key": API_KEY,
      ...(init.headers ?? {}),
    },
  });

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {}
    throw new Error(detail);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

// ─── Orders ───────────────────────────────────────────────────────────────

export function ordersKey(
  page: number,
  perPage: number,
  status?: OrderStatus | "",
  search?: string
) {
  const params = new URLSearchParams({ page: String(page), per_page: String(perPage) });
  if (status) params.set("status", status);
  if (search) params.set("search", search);
  return `/orders?${params}`;
}

export async function fetchOrders(key: string): Promise<OrderListResponse> {
  return request<OrderListResponse>(key);
}

export async function fetchOrder(id: string): Promise<Order> {
  return request<Order>(`/orders/${id}`);
}

export async function createOrder(data: OrderCreate): Promise<Order> {
  return request<Order>("/orders", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function updateOrder(id: string, data: OrderUpdate): Promise<Order> {
  return request<Order>(`/orders/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function deleteOrder(id: string): Promise<void> {
  return request<void>(`/orders/${id}`, { method: "DELETE" });
}

export async function fetchOrderStats(): Promise<OrderStats> {
  return request<OrderStats>("/orders/stats");
}

// ─── Upload ───────────────────────────────────────────────────────────────

export async function uploadDocument(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  return request<UploadResponse>("/upload", { method: "POST", body: form });
}

// ─── Activity logs ────────────────────────────────────────────────────────

export function logsKey(page: number, perPage: number) {
  return `/logs?page=${page}&per_page=${perPage}`;
}

export async function fetchLogs(key: string): Promise<ActivityLogListResponse> {
  return request<ActivityLogListResponse>(key);
}
