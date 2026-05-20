export type OrderStatus = "pending" | "processing" | "completed" | "cancelled";

export interface Order {
  id: string;
  patient_first_name: string;
  patient_last_name: string;
  patient_dob: string;
  status: OrderStatus;
  notes: string | null;
  document_filename: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface OrderListResponse {
  items: Order[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

export interface OrderCreate {
  patient_first_name: string;
  patient_last_name: string;
  patient_dob: string;
  status?: OrderStatus;
  notes?: string;
  created_by?: string;
}

export interface OrderUpdate {
  patient_first_name?: string;
  patient_last_name?: string;
  patient_dob?: string;
  status?: OrderStatus;
  notes?: string;
}

export interface ExtractedPatientInfo {
  first_name: string;
  last_name: string;
  date_of_birth: string;
  confidence: number;
}

export interface UploadResponse {
  extracted_info: ExtractedPatientInfo;
  order: Order;
  message: string;
}

export interface ActivityLog {
  id: string;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  ip_address: string | null;
  request_path: string;
  request_method: string;
  status_code: number | null;
  duration_ms: number | null;
  extra_data: Record<string, unknown> | null;
  timestamp: string;
}

export interface ActivityLogListResponse {
  items: ActivityLog[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

export interface OrderStats {
  total: number;
  pending: number;
  processing: number;
  completed: number;
  cancelled: number;
}

export interface ApiError {
  detail: string;
}
