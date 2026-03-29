export type JobStatus =
  | 'queued'
  | 'processing'
  | 'completed'
  | 'needs_review'
  | 'low_confidence'
  | 'failed';

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

export interface ValidationSummary {
  decision: string;
  is_valid: boolean;
  confidence_score: number;
  error_count: number;
  warning_count: number;
  info_count: number;
  reason_codes: string[];
  review_reasons: string[];
  schema_supported: boolean;
  failed_truth_tests: number;
  validation_time_seconds: number;
  document_type: string;
}

export interface Job {
  job_id: string;
  document_id?: string | null;
  status: JobStatus;
  current_stage?: string | null;
  submitted_at?: string;
  started_at?: string | null;
  finished_at?: string | null;
  retry_count?: number;
  review_required?: boolean;
  review_case_id?: string | null;
  review_status?: string | null;
  review_priority?: string | null;
  review_open_field_count?: number;
  critical_review_open_field_count?: number;
  failure_reason?: string | null;
  validation_decision?: string | null;
  validation_summary?: ValidationSummary | null;
  recovery_attempt_count?: number;
  doc_type?: string | null;
  file_name?: string | null;
  ocr_conf?: number | null;
  overall_conf?: number | null;
  timings?: Record<string, number>;
}

export interface UnresolvedReviewField {
  id?: string;
  field_path: string;
  display_label?: string;
  label?: string;
  reason_code: string;
  validation_message: string;
  message?: string;
  proposed_value: unknown | null;
  original_value: unknown | null;
  evidence_text?: string | null;
  is_critical?: boolean;
  priority_score?: number;
}

export interface RecoveryAttempt {
  attempt_id?: string;
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
  lang?: string | null;
  ocr_conf?: number | null;
  overall_conf?: number | null;
  structured_data?: Record<string, unknown> | null;
  validation_summary?: ValidationSummary | null;
  unresolved_review_fields?: UnresolvedReviewField[];
  recovery_attempts?: RecoveryAttempt[];
  artifacts?: Record<string, string>;
  processing_time_seconds?: number;
  stage_timings_seconds?: Record<string, number>;
  review_case_id?: string | null;
  review_status?: string | null;
  review_priority?: string | null;
  review_open_field_count?: number;
  critical_review_open_field_count?: number;
  review_summary?: Record<string, unknown>;
  recovery_attempt_count?: number;
}

export interface ReviewField {
  id: string;
  field_path: string;
  display_label?: string | null;
  label?: string | null;
  reason_code: string;
  validation_message: string;
  message?: string | null;
  original_value: unknown | null;
  proposed_value: unknown | null;
  corrected_value?: unknown | null;
  evidence_text?: string | null;
  evidence_snippet?: string | null;
  priority_score?: number;
  is_critical?: boolean;
  status: string;
}

export interface ReviewCase {
  id: string;
  job_id: string;
  file_name?: string | null;
  doc_type?: string | null;
  status: 'open' | 'resolved' | 'in_progress';
  priority?: string | null;
  priority_score?: number;
  created_at?: string;
  updated_at?: string;
  fields: ReviewField[];
  open_field_count?: number;
  critical_open_field_count?: number;
  next_recommended_field?: string | null;
  reason_codes?: string[];
  review_summary?: Record<string, unknown>;
}

export interface DocumentPreviewSource {
  blob: Blob;
  mimeType: string;
  filename: string;
}

export interface ReviewsListResponse {
  reviews: ReviewCase[];
  total?: number;
}

export interface HealthResponse {
  status: 'healthy' | 'degraded' | 'down';
  version?: string;
  dependencies?: Record<string, string>;
  timestamp?: string;
}

export interface SystemDependencyCheck {
  status?: string;
  detail?: string | null;
  latency_ms?: number | null;
  last_checked?: string | null;
  error?: string | null;
}

export interface SystemStatusResponse {
  api: string;
  version: string;
  status: string;
  readiness: string;
  dependencies?: Record<string, SystemDependencyCheck>;
  runtime_metrics?: Record<string, unknown>;
  supported_languages?: string[];
  supported_document_types?: string[];
}
