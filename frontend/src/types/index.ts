// ─── Job Status ─────────────────────────────────────────────────────────────

export type JobStatus =
  | 'queued'
  | 'processing'
  | 'completed'
  | 'needs_review'
  | 'low_confidence'
  | 'failed';

// ─── Auth ────────────────────────────────────────────────────────────────────

export interface UserInfo {
  name: string;
  email: string;
  role: string;
  username?: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: UserInfo;
}

export interface LoginRequest {
  email: string;
  password: string;
}

// ─── Jobs ────────────────────────────────────────────────────────────────────

export interface Job {
  job_id: string;
  document_id?: string;
  status: JobStatus;
  current_stage?: string | null;
  submitted_at?: string;
  started_at?: string | null;
  finished_at?: string | null;
  retry_count?: number;
  review_required?: boolean;
  review_case_id?: string | null;
  failure_reason?: string | null;
  validation_decision?: string | null;
  doc_type?: string | null;
  file_name?: string | null;
  ocr_conf?: number | null;
  overall_conf?: number | null;
  timings?: Record<string, number>;
}

export interface JobsListResponse {
  jobs: Job[];
  total?: number;
}

// ─── Results ─────────────────────────────────────────────────────────────────

export interface ValidationSummary {
  decision: string;
  is_valid: boolean;
  confidence_score: number;
  error_count: number;
  warning_count: number;
  info_count: number;
  truth_test_count?: number;
  passed_truth_tests?: number;
  reason_codes: string[];
  review_reasons: string[];
  schema_supported: boolean;
  failed_truth_tests: number;
  truth_test_failures?: string[];
  validation_time_seconds: number;
  document_type: string;
}

export interface UnresolvedReviewField {
  field_path: string;
  reason_code: string;
  validation_message: string;
  proposed_value: unknown | null;
  original_value: unknown | null;
}

export interface RecoveryAttempt {
  attempt_number: number;
  mode: string;
  strategy: string;
  status: string;
  accepted: boolean;
  failure_reason?: string | null;
  weak_fields?: string[];
  improvement_score?: number | null;
}

export interface ExtractionResult {
  job_id: string;
  file: string;
  status: JobStatus;
  doc_type?: string | null;
  dt_conf?: number | null;
  dt_source?: string | null;
  lang?: string | null;
  ocr_conf?: number | null;
  overall_conf?: number | null;
  has_struct?: boolean;
  struct_keys?: string[];
  structured_data?: Record<string, unknown> | null;
  validation_summary?: ValidationSummary | null;
  unresolved_review_fields?: UnresolvedReviewField[];
  recovery_attempts?: RecoveryAttempt[];
  artifacts?: Record<string, string>;
  processing_time_seconds?: number;
  stage_timings_seconds?: Record<string, number>;
}

// ─── Reviews ─────────────────────────────────────────────────────────────────

export interface ReviewField {
  id: string;
  field_path: string;
  reason_code: string;
  validation_message: string;
  original_value: unknown | null;
  proposed_value: unknown | null;
  corrected_value?: unknown | null;
  status: 'open' | 'corrected' | 'accepted' | 'skipped';
}

export interface ReviewCase {
  id: string;
  job_id: string;
  file_name?: string | null;
  doc_type?: string | null;
  status: 'open' | 'resolved' | 'in_progress';
  created_at?: string;
  updated_at?: string;
  fields: ReviewField[];
}

export interface ReviewsListResponse {
  reviews: ReviewCase[];
  total?: number;
}

// ─── Health ──────────────────────────────────────────────────────────────────

export interface ServiceStatus {
  name: string;
  status: 'healthy' | 'degraded' | 'down';
  latency_ms?: number | null;
  last_checked?: string | null;
  error?: string | null;
}

export interface HealthResponse {
  status: 'healthy' | 'degraded' | 'down';
  services?: Record<string, ServiceStatus>;
  timestamp?: string;
}
