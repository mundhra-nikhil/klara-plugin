export type FindingSeverity = "critical" | "major" | "minor" | "suggestion";

export type FindingStatus = "open" | "accepted" | "rejected" | "deferred";

export type FindingType =
  "formatting" | "spelling" | "consistency" | "compliance" | "style" | "metadata";

export type AIJobStatus = "queued" | "running" | "analysing" | "completed" | "failed" | "cancelled";

export type AIJobType =
  "compliance_audit" | "formatting_check" | "style_validation" | "proofreading" | "pdf_comparison";

export type UserRole =
  | "intake_coordinator"
  | "document_specialist"
  | "qc_operator"
  | "proofreader"
  | "manager"
  | "admin";

export interface AuthUser {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  department_id?: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface Finding {
  id: string;
  document_id: string;
  ai_job_id: string;
  type: FindingType;
  severity: FindingSeverity;
  status: FindingStatus;
  title: string;
  description: string;
  rule_name: string;
  line_number?: number;
  page_number?: number;
  location?: string;
  suggested_fix?: string;
  original_text?: string;
  replacement_text?: string;
  confidence: number;
  resolved_by?: string;
  resolved_at?: string;
}

export interface FormattingOperation {
  type:
    | "keep_with_next"
    | "page_break_before"
    | "widow_orphan_control"
    | "line_spacing"
    | "alignment"
    | "font";
  value?: boolean | number | string;
  description?: string;
  fontName?: string;
  fontSize?: number;
}

export interface QCFinding {
  id: string;
  document_id: string;
  review_id: string;
  type: FindingType;
  severity: FindingSeverity;
  status: FindingStatus;
  title: string;
  description: string;
  location?: string;
  suggested_fix?: string;
  original_text?: string;
  anchor_text?: string;
  replacement_text?: string;
  confidence: number;
  rule_name?: string;
  paragraph_index?: number;
  resolved_by?: string;
  resolved_at?: string;
  resolution_notes?: string;
  formatting_fix?: FormattingOperation;
  template_data?: any;
}

export interface AIJob {
  id: string;
  document_id: string;
  job_type: AIJobType;
  status: AIJobStatus;
  progress_pct?: number;
  started_at?: string;
  completed_at?: string;
  error_message?: string;
  findings_count?: number;
  token_usage?: number;
  latency_ms?: number;
  model_used?: string;
  created_at: string;
}

export interface QCReview {
  id: string;
  document_id: string;
  document_title: string;
  reviewer_id: string;
  reviewer_name: string;
  status: "in_progress" | "completed" | "rejected" | "deferred";
  checklist_id: string;
  total_items: number;
  completed_items: number;
  findings_count: number;
  started_at: string;
  completed_at?: string;
  notes?: string;
}

export interface ChecklistItem {
  id: string;
  group: string;
  title: string;
  description?: string;
  is_automated: boolean;
  ai_finding_type_mapping?: string | null;
  result: "pass" | "fail" | "warn" | "pending" | "na";
  details?: string;
  order: number;
}

export interface Checklist {
  id: string;
  name: string;
  description?: string;
  document_type: string;
  client_id?: string;
  items: ChecklistItem[];
  total_items: number;
}

export interface Document {
  id: string;
  title: string;
  client_id: string;
  client_name?: string;
  document_type: string;
  status: string;
  priority: string;
  pages: number;
  file_url?: string;
  blob_url?: string;
  assigned_specialist_id?: string;
  assigned_specialist_name?: string;
  checks_total: number;
  checks_passed: number;
  issues_count: number;
}

export interface ResolveFindingRequest {
  status: FindingStatus;
  applied_text?: string;
  note?: string;
  resolution_notes?: string; // Backend will use this if note is not provided
  auto_resolved?: boolean;
  not_found_in_document?: boolean;
}

export interface TriggerAIJobRequest {
  document_id: string;
  job_type: AIJobType;
  rule_set_id?: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: number;
}
