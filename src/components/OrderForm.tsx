"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { Order, OrderCreate, OrderUpdate } from "@/lib/types";

const schema = z.object({
  patient_first_name: z.string().min(1, "First name is required").max(100),
  patient_last_name: z.string().min(1, "Last name is required").max(100),
  patient_dob: z.string().min(1, "Date of birth is required"),
  status: z.enum(["pending", "processing", "completed", "cancelled"]),
  notes: z.string().max(2000).optional(),
  created_by: z.string().max(100).optional(),
});

type FormData = z.infer<typeof schema>;

interface OrderFormProps {
  order?: Order;
  onSubmit: (data: OrderCreate | OrderUpdate) => Promise<void>;
  onCancel: () => void;
  isLoading?: boolean;
}

export function OrderForm({ order, onSubmit, onCancel, isLoading }: OrderFormProps) {
  const {
    register,
    handleSubmit,
    setValue,
    watch,
    formState: { errors },
  } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: {
      patient_first_name: order?.patient_first_name ?? "",
      patient_last_name: order?.patient_last_name ?? "",
      patient_dob: order?.patient_dob ?? "",
      status: order?.status ?? "pending",
      notes: order?.notes ?? "",
      created_by: order?.created_by ?? "",
    },
  });

  const status = watch("status");

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1.5">
          <Label htmlFor="first_name">First Name *</Label>
          <Input
            id="first_name"
            placeholder="Jane"
            {...register("patient_first_name")}
          />
          {errors.patient_first_name && (
            <p className="text-xs text-red-500">{errors.patient_first_name.message}</p>
          )}
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="last_name">Last Name *</Label>
          <Input
            id="last_name"
            placeholder="Doe"
            {...register("patient_last_name")}
          />
          {errors.patient_last_name && (
            <p className="text-xs text-red-500">{errors.patient_last_name.message}</p>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1.5">
          <Label htmlFor="dob">Date of Birth *</Label>
          <Input id="dob" type="date" {...register("patient_dob")} />
          {errors.patient_dob && (
            <p className="text-xs text-red-500">{errors.patient_dob.message}</p>
          )}
        </div>

        <div className="space-y-1.5">
          <Label>Status</Label>
          <Select
            value={status}
            onValueChange={(v) => setValue("status", v as FormData["status"])}
          >
            <SelectTrigger>
              <SelectValue placeholder="Select status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="pending">Pending</SelectItem>
              <SelectItem value="processing">Processing</SelectItem>
              <SelectItem value="completed">Completed</SelectItem>
              <SelectItem value="cancelled">Cancelled</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="created_by">Created By</Label>
        <Input
          id="created_by"
          placeholder="Dr. Smith"
          {...register("created_by")}
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="notes">Notes</Label>
        <Textarea
          id="notes"
          placeholder="Clinical notes or additional context…"
          rows={3}
          {...register("notes")}
        />
      </div>

      <div className="flex justify-end gap-2 pt-2">
        <Button type="button" variant="outline" onClick={onCancel} disabled={isLoading}>
          Cancel
        </Button>
        <Button type="submit" disabled={isLoading}>
          {isLoading ? "Saving…" : order ? "Save Changes" : "Create Order"}
        </Button>
      </div>
    </form>
  );
}
