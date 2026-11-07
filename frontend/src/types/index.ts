/**
 * AICTE NIDHI — AICTE Security Deposit and FDR Management Portal
 * Core Domain Type Definitions
 */

export interface Institution {
  id: number;
  aicte_permanent_id: string;
  institution_code?: string | null;
  name: string;
  institution_type?: string | null;
  address?: string | null;
  state?: string | null;
  district?: string | null;
  contact_email?: string | null;
  contact_phone?: string | null;
  record_status?: string | null;
  created_at?: string;
  updated_at?: string;
}

export type LifecycleStatus =
  | 'DRAFT'
  | 'SUBMITTED'
  | 'PENDING_VERIFICATION'
  | 'ACTIVE'
  | 'RENEWAL_REQUIRED'
  | 'RENEWAL_IN_PROGRESS'
  | 'MATURED'
  | 'RELEASE_REQUESTED'
  | 'RELEASED'
  | 'REJECTED'
  | 'SUPERSEDED'
  | 'ARCHIVED';

export type ValidityStatus =
  | 'ACTIVE_VALID'
  | 'EXPIRING_SOON'
  | 'MATURED'
  | 'UNKNOWN_INCOMPLETE';

export type VerificationStatus =
  | 'UNVERIFIED'
  | 'VERIFIED'
  | 'DISCREPANCY_FLAGGED'
  | 'VERIFICATION_FAILED'
  | 'SUSPICIOUS_ANOMALY';

export interface DepositInstrument {
  id: number;
  instrument_number: string;
  institution_id: number;
  institution?: Institution | null;
  instrument_type: string; // 'FDR', 'BANK_GUARANTEE', 'GOVERNMENT_SECURITY'
  issuing_bank: string;
  branch_name?: string | null;
  branch_ifsc?: string | null;
  account_number?: string | null;
  amount: number;
  currency: string;
  issue_date: string;
  maturity_date: string;
  submission_date?: string | null;
  lifecycle_status: LifecycleStatus;
  validity_status: ValidityStatus;
  verification_status: VerificationStatus;
  original_instrument_id?: number | null;
  renewal_count: number;
  lien_marked_to?: string | null;
  joint_holder_name?: string | null;
  purpose?: string | null;
  notes?: string | null;
  created_at: string;
  updated_at: string;
  
  // Computed dynamic properties
  days_to_maturity?: number;
  formatted_amount?: string;
  documents?: InstrumentDocument[];
  verification_records?: VerificationRecord[];
}

export interface ExtractedFieldItem {
  id: number;
  document_id: number;
  field_key: string;
  field_value: string;
  normalized_value?: string | null;
  confidence_score: number;
  page_number: number;
  source_snippet?: string | null;
  bounding_box?: string | null;
  extraction_method: string;
  created_at: string;
}

export interface InstrumentDocument {
  id: number;
  instrument_id: number;
  document_category: 'FDR_RECEIPT' | 'BANK_LIEN_LETTER' | 'JOINT_HOLDERSHIP_LETTER' | 'RENEWAL_ADVICE' | 'RELEASE_ORDER' | 'OTHER';
  original_filename: string;
  storage_path: string;
  file_size_bytes: number;
  mime_type: string;
  sha256_hash: string;
  phash_value?: string | null;
  upload_timestamp: string;
  uploaded_by: string;
  extraction_status: 'SUCCESS' | 'FAILED' | 'PARTIAL' | 'PENDING';
  extracted_fields_json?: Record<string, any> | null;
  extracted_text?: string | null;
  ocr_performed: boolean;
  version: number;
  status: string;
  stream_url?: string;
}

export interface VerificationRecord {
  id: number;
  instrument_id: number;
  check_type: 'OCR_PARSE' | 'FIELD_CONSISTENCY' | 'DOCUMENT_COMPLETENESS' | 'DATE_VALIDATION' | 'DUPLICATE_CHECK' | 'BANK_CONFIRMATION' | 'REGISTRY_VALIDATION';
  status: 'PASSED' | 'FAILED' | 'WARNING' | 'UNAVAILABLE';
  confidence_score?: number | null;
  expected_value?: string | null;
  observed_value?: string | null;
  discrepancy_details?: string | null;
  verification_source: string;
  is_simulated: boolean;
  created_at: string;
}

export interface RenewalRecord {
  id: number;
  original_instrument_id: number;
  replacement_instrument_id?: number | null;
  previous_maturity_date: string;
  new_maturity_date: string;
  submission_date: string;
  review_status: 'SUBMITTED' | 'UNDER_REVIEW' | 'APPROVED' | 'REJECTED' | 'RECTIFICATION_REQUESTED';
  supporting_document_id?: number | null;
  review_observations?: string | null;
  reviewed_by?: string | null;
  completed_at?: string | null;
  created_at: string;
  
  // Enriched relations
  original_instrument?: DepositInstrument | null;
  replacement_instrument?: DepositInstrument | null;
}

export interface ChecklistItem {
  condition_key: string;
  label: string;
  satisfied: boolean;
  notes?: string;
}

export interface ReleaseRefundRequest {
  id: number;
  instrument_id: number;
  institution_id: number;
  request_number: string;
  request_type: 'FULL_RELEASE' | 'DISCHARGE' | 'PARTIAL_REFUND' | string;
  request_date: string;
  reason: string;
  conditions_checklist_json?: string | null;
  review_status: 'PENDING_OFFICER_REVIEW' | 'PENDING_FINAL_APPROVAL' | 'APPROVED' | 'REJECTED' | 'RETURNED_FOR_CORRECTION' | string;
  scrutiny_observations?: string | null;
  decision_record?: string | null;
  decision_date?: string | null;
  decided_by?: string | null;
  decision_remarks?: string | null;
  rejection_reason?: string | null;
  created_at: string;
  updated_at: string;
  institution_name?: string | null;
  instrument_number?: string | null;
}

export interface NotificationItem {
  id: number;
  institution_id?: number | null;
  instrument_id?: number | null;
  request_id?: number | null;
  notification_type: 'MATURITY_WARNING' | 'MATURED_OVERDUE' | 'DISCREPANCY_FLAGGED' | 'VERIFICATION_PENDING' | 'RELEASE_AWAITING_ACTION';
  trigger_date: string;
  target_role: 'OFFICER' | 'APPROVER' | 'APPLICANT' | 'ALL';
  title: string;
  message: string;
  severity: 'INFO' | 'WARNING' | 'CRITICAL';
  is_read: boolean;
  created_at: string;
}

export interface AuditEvent {
  id: number;
  instrument_id?: number | null;
  application_id?: number | null;
  entity_type?: string;
  entity_id?: number;
  event_type: string;
  action?: string;
  actor: string;
  details?: Record<string, any>;
  details_json?: any;
  previous_hash: string;
  event_hash: string;
  timestamp?: string;
  created_at?: string;
}

export interface UpcomingMaturityItem {
  id: number;
  instrument_number: string;
  institution_name: string;
  issuing_bank: string;
  amount: number;
  formatted_amount: string;
  maturity_date: string;
  days_remaining: number;
  validity_status: ValidityStatus;
  lifecycle_status: LifecycleStatus;
}

export interface BankDistributionItem {
  bank: string;
  count: number;
  total_amount: number;
}

export interface DashboardMetrics {
  total_instruments: number;
  active_valid_instruments: number;
  expiring_soon_instruments: number;
  matured_instruments: number;
  pending_verification: number;
  renewals_pending: number;
  release_requests_pending: number;
  total_deposit_value: number;
  formatted_total_value: string;
  warning_window_days: number;
  upcoming_maturities: UpcomingMaturityItem[];
  status_distribution: Array<{ status: string; count: number }>;
  recent_activity: Array<Record<string, any>>;
  bank_distribution: BankDistributionItem[];
  // UI aliases retained for existing dashboard cards
  active_valid?: number;
  expiring_soon_30d?: number;
  matured?: number;
  total_portfolio_amount?: number;
  formatted_portfolio_amount?: string;
}

export interface InstrumentDetail extends DepositInstrument {
  documents: InstrumentDocument[];
  verification_records: VerificationRecord[];
  audit_events?: AuditEvent[];
  renewals?: RenewalRecord[];
  release_requests?: ReleaseRefundRequest[];
  discrepancies?: VerificationRecord[];
}

export interface UserInfo {
  id?: number | null;
  username: string;
  full_name: string;
  role: 'OFFICER' | 'APPROVER' | 'ADMIN' | 'APPLICANT';
  designation: string;
  institution_id?: string | null;
  email?: string | null;
}

// -------------------------------------------------------------------------
// Backward-compatibility Aliases & Legacy DTOs
// -------------------------------------------------------------------------
export type Application = DepositInstrument;
export type ApplicationDetail = InstrumentDetail;
export interface Finding {
  id: number;
  finding_code: string;
  category: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  title: string;
  description: string;
  rule_code?: string;
  rule_description?: string;
  review_status: string;
}
export interface AlertItem {
  id: number;
  title: string;
  message: string;
  severity: string;
  created_at: string;
}
export interface IntegrationServiceItem {
  id: string;
  name: string;
  category: string;
  mode: string;
  status: string;
  is_simulated: boolean;
  endpoint: string;
  external_target: string;
  protocol: string;
  last_checked: string;
  notes: string;
}
export interface CategoryInfo {
  code: string;
  title: string;
  description?: string;
}
