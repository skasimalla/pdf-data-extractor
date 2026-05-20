"use client";

import { useState } from "react";
import useSWR, { mutate } from "swr";
import { format, parseISO } from "date-fns";
import {
  Plus,
  Upload,
  Search,
  Pencil,
  Trash2,
  ChevronLeft,
  ChevronRight,
  FileText,
  RefreshCw,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { OrderForm } from "@/components/OrderForm";
import { UploadModal } from "@/components/UploadModal";
import {
  fetchOrders,
  createOrder,
  updateOrder,
  deleteOrder,
  ordersKey,
} from "@/lib/api";
import type { Order, OrderCreate, OrderUpdate, OrderStatus } from "@/lib/types";

const STATUS_BADGE: Record<OrderStatus, React.ComponentProps<typeof Badge>["variant"]> = {
  pending: "warning",
  processing: "default",
  completed: "success",
  cancelled: "destructive",
};

export function OrderTable({ onDataChange }: { onDataChange?: () => void }) {
  const [page, setPage] = useState(1);
  const [perPage] = useState(15);
  const [statusFilter, setStatusFilter] = useState<OrderStatus | "">("");
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");

  const [createOpen, setCreateOpen] = useState(false);
  const [editOrder, setEditOrder] = useState<Order | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Order | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const key = ordersKey(page, perPage, statusFilter, search);
  const { data, isLoading, error, mutate: revalidate } = useSWR(key, fetchOrders, {
    keepPreviousData: true,
  });

  function refresh() {
    revalidate();
    onDataChange?.();
  }

  async function handleCreate(formData: OrderCreate | OrderUpdate) {
    setSubmitting(true);
    try {
      await createOrder(formData as OrderCreate);
      toast.success("Order created");
      setCreateOpen(false);
      refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create order");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleUpdate(formData: OrderCreate | OrderUpdate) {
    if (!editOrder) return;
    setSubmitting(true);
    try {
      await updateOrder(editOrder.id, formData as OrderUpdate);
      toast.success("Order updated");
      setEditOrder(null);
      refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to update order");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    try {
      await deleteOrder(deleteTarget.id);
      toast.success("Order deleted");
      setDeleteTarget(null);
      refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to delete order");
    }
  }

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setSearch(searchInput);
    setPage(1);
  }

  const orders = data?.items ?? [];
  const total = data?.total ?? 0;
  const pages = data?.pages ?? 1;

  return (
    <>
      <Card>
        <CardHeader>
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <CardTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5 text-blue-600" />
              Patient Orders
              {!isLoading && (
                <span className="ml-1 text-sm font-normal text-gray-400">({total})</span>
              )}
            </CardTitle>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={refresh} title="Refresh">
                <RefreshCw className="h-4 w-4" />
              </Button>
              <Button variant="outline" size="sm" onClick={() => setUploadOpen(true)}>
                <Upload className="mr-1.5 h-4 w-4" />
                Upload PDF
              </Button>
              <Button size="sm" onClick={() => setCreateOpen(true)}>
                <Plus className="mr-1.5 h-4 w-4" />
                New Order
              </Button>
            </div>
          </div>

          {/* Filters */}
          <div className="flex flex-col gap-3 pt-1 sm:flex-row">
            <form onSubmit={handleSearch} className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400 pointer-events-none" />
              <Input
                className="pl-9 pr-4"
                placeholder="Search by patient name…"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
              />
            </form>
            <Select
              value={statusFilter}
              onValueChange={(v) => { setStatusFilter(v as OrderStatus | ""); setPage(1); }}
            >
              <SelectTrigger className="w-40">
                <SelectValue placeholder="All statuses" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">All statuses</SelectItem>
                <SelectItem value="pending">Pending</SelectItem>
                <SelectItem value="processing">Processing</SelectItem>
                <SelectItem value="completed">Completed</SelectItem>
                <SelectItem value="cancelled">Cancelled</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardHeader>

        <CardContent className="p-0">
          {isLoading ? (
            <div className="flex items-center justify-center py-16">
              <RefreshCw className="h-6 w-6 animate-spin text-gray-400" />
            </div>
          ) : error ? (
            <div className="py-16 text-center text-sm text-red-500">
              Failed to load orders. Check your API key and try again.
            </div>
          ) : orders.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-3 py-16 text-gray-500">
              <FileText className="h-10 w-10 text-gray-300" />
              <p className="text-sm">No orders found</p>
              <Button size="sm" variant="outline" onClick={() => setCreateOpen(true)}>
                Create your first order
              </Button>
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-100 bg-gray-50/60">
                      <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
                        Patient
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
                        Date of Birth
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
                        Status
                      </th>
                      <th className="hidden px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500 md:table-cell">
                        Document
                      </th>
                      <th className="hidden px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500 lg:table-cell">
                        Created
                      </th>
                      <th className="px-6 py-3 text-right text-xs font-semibold uppercase tracking-wide text-gray-500">
                        Actions
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {orders.map((order) => (
                      <tr key={order.id} className="hover:bg-gray-50/60 transition-colors">
                        <td className="px-6 py-4">
                          <div className="font-medium text-gray-900">
                            {order.patient_last_name}, {order.patient_first_name}
                          </div>
                          <div className="font-mono text-xs text-gray-400">{order.id.slice(0, 8)}…</div>
                        </td>
                        <td className="px-6 py-4 text-gray-600">
                          {order.patient_dob
                            ? format(parseISO(order.patient_dob), "MMM d, yyyy")
                            : "—"}
                        </td>
                        <td className="px-6 py-4">
                          <Badge variant={STATUS_BADGE[order.status]}>
                            {order.status.charAt(0).toUpperCase() + order.status.slice(1)}
                          </Badge>
                        </td>
                        <td className="hidden px-6 py-4 text-gray-500 md:table-cell">
                          {order.document_filename ? (
                            <span className="flex items-center gap-1.5 text-xs">
                              <FileText className="h-3.5 w-3.5 text-blue-500" />
                              {order.document_filename}
                            </span>
                          ) : (
                            <span className="text-gray-300">—</span>
                          )}
                        </td>
                        <td className="hidden px-6 py-4 text-xs text-gray-400 lg:table-cell">
                          {format(parseISO(order.created_at), "MMM d, yyyy")}
                          {order.created_by && (
                            <div className="text-gray-400">{order.created_by}</div>
                          )}
                        </td>
                        <td className="px-6 py-4">
                          <div className="flex items-center justify-end gap-1">
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8"
                              onClick={() => setEditOrder(order)}
                              title="Edit"
                            >
                              <Pencil className="h-3.5 w-3.5" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8 text-red-500 hover:text-red-600 hover:bg-red-50"
                              onClick={() => setDeleteTarget(order)}
                              title="Delete"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              <div className="flex items-center justify-between border-t border-gray-100 px-6 py-4">
                <p className="text-sm text-gray-500">
                  Showing {(page - 1) * perPage + 1}–{Math.min(page * perPage, total)} of{" "}
                  {total} orders
                </p>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page === 1}
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </Button>
                  <span className="text-sm text-gray-600">
                    {page} / {pages}
                  </span>
                  <Button
                    variant="outline"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => setPage((p) => Math.min(pages, p + 1))}
                    disabled={page === pages}
                  >
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Create Order Dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Create New Order</DialogTitle>
            <DialogDescription>Enter patient information to create a new order.</DialogDescription>
          </DialogHeader>
          <OrderForm
            onSubmit={handleCreate}
            onCancel={() => setCreateOpen(false)}
            isLoading={submitting}
          />
        </DialogContent>
      </Dialog>

      {/* Edit Order Dialog */}
      <Dialog open={!!editOrder} onOpenChange={(v) => !v && setEditOrder(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Edit Order</DialogTitle>
            <DialogDescription>Update the patient order details.</DialogDescription>
          </DialogHeader>
          {editOrder && (
            <OrderForm
              order={editOrder}
              onSubmit={handleUpdate}
              onCancel={() => setEditOrder(null)}
              isLoading={submitting}
            />
          )}
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={!!deleteTarget} onOpenChange={(v) => !v && setDeleteTarget(null)}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Delete Order</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete the order for{" "}
              <strong>
                {deleteTarget?.patient_first_name} {deleteTarget?.patient_last_name}
              </strong>
              ? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDelete}>
              Delete
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Upload PDF Modal */}
      <UploadModal
        open={uploadOpen}
        onOpenChange={setUploadOpen}
        onSuccess={refresh}
      />
    </>
  );
}
