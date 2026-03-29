import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardCheck,
  Download,
  FileWarning,
  Loader2,
  Sparkles,
} from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { StatePanel } from '@/components/ui/StatePanel';
import { DataPreview } from '@/components/ui/DataPreview';
import { StatusPill } from '@/components/ui/StatusPill';
import { jobsApi } from '@/lib/api/jobsApi';
import { resultsApi } from '@/lib/api/resultsApi';
import { reviewsApi } from '@/lib/api/reviewsApi';
import { formatConfidence, formatDuration } from '@/lib/utils';
import type { ExtractionResult, RecoveryAttempt, ReviewCase, UnresolvedReviewField } from '@/types/models';

const DOWNLOAD_FORMATS: Array<{ key: 'json' | 'csv' | 'xlsx' | 'html'; label: string; hint: string }> = [
  { key: 'json', label: 'JSON', hint: 'Structured machine-readable payload.' },
  { key: 'csv', label: 'CSV', hint: 'Spreadsheet-friendly flat export.' },
  { key: 'xlsx', label: 'Excel', hint: 'Workbook export for operator sharing.' },
  { key: 'html', label: 'HTML', hint: 'Readable rendered output snapshot.' },
];

export default function ResultInsightsPage() {
  const { id } = useParams<{ id: string }>();
  const [downloadingFormat, setDownloadingFormat] = useState<string | null>(null);

  const { data: result, isLoading, isError, refetch } = useQuery<ExtractionResult>({
    queryKey: ['result', 'detail', id],
    queryFn: () => resultsApi.get(id!),
    enabled: !!id,
  });

  const { data: recoveryData, isLoading: recoveryLoading } = useQuery({
    queryKey: ['recovery', 'job', id],
    queryFn: () => jobsApi.getRecoveryAttempts(id!),
    enabled: !!id,
  });

  const { data: reviewCase } = useQuery<ReviewCase>({
    queryKey: ['review', 'detail', result?.review_case_id],
    queryFn: () => reviewsApi.get(result!.review_case_id!),
    enabled: !!result?.review_case_id,
  });

  const flaggedFields = useMemo(() => getFlaggedFields(result, reviewCase), [result, reviewCase]);
  const stageTimings = Object.entries(result?.stage_timings_seconds ?? {});
  const recoveryAttempts = normalizeRecoveryAttempts(recoveryData);

  if (isLoading) {
    return (
      <div className="page-shell">
        <div className="page-container">
          <StatePanel
            title="Loading result"
            message="Pulling the final output, validation summary, and review linkage."
            loading
          />
        </div>
      </div>
    );
  }

  if (isError || !result) {
    return (
      <div className="page-shell">
        <div className="page-container">
          <StatePanel
            title="Result unavailable"
            message="The result is not ready yet or the API could not return it."
            actionLabel="Retry"
            onAction={() => refetch()}
            tone="error"
          />
        </div>
      </div>
    );
  }

  const validation = result.validation_summary;
  const reviewCount = flaggedFields.length;

  return (
    <div className="page-shell">
      <div className="page-container">
        <PageHeader
          eyebrow="Result Workspace"
          title={result.file}
          subtitle="Inspect the extracted output, understand the validation decision, and move directly into review or download actions."
          actions={
            <div className="flex flex-wrap gap-2">
              <Link to={`/jobs/${result.job_id}`} className="btn-secondary">
                Back to job
              </Link>
              {result.review_case_id ? (
                <Link to={`/reviews/${result.review_case_id}`} className="btn-primary">
                  Open review case
                </Link>
              ) : null}
            </div>
          }
          badges={
            <>
              <span className="soft-badge">
                <StatusPill status={result.status} />
              </span>
              <span className="soft-badge">
                <Sparkles className="h-3.5 w-3.5 text-[#A5B4FC]" />
                {result.doc_type ?? 'Unknown document'}
              </span>
              <span className="soft-badge">
                <ClipboardCheck className="h-3.5 w-3.5 text-green-300" />
                OCR {formatConfidence(result.ocr_conf)}
              </span>
              <span className="soft-badge">
                <FileWarning className="h-3.5 w-3.5 text-amber-300" />
                Overall {formatConfidence(result.overall_conf)}
              </span>
            </>
          }
        />

        <div className="space-y-6">
          <section className="grid gap-4 xl:grid-cols-4">
            <ResultMetric title="Processing time" value={formatDuration(result.processing_time_seconds)} note="Total visible pipeline time." tone="brand" />
            <ResultMetric
              title="Validation"
              value={validation ? `${Math.round(validation.confidence_score * 100)}%` : 'Not returned'}
              note={validation ? `${validation.error_count} errors · ${validation.warning_count} warnings` : 'Validation summary unavailable.'}
              tone={validation?.decision === 'pass' ? 'green' : 'amber'}
            />
            <ResultMetric
              title="Review routing"
              value={result.review_case_id ? 'Linked' : 'None'}
              note={result.review_case_id ? `${reviewCount} flagged field${reviewCount === 1 ? '' : 's'} surfaced` : 'No linked review case'}
              tone={result.review_case_id ? 'amber' : 'slate'}
            />
            <ResultMetric
              title="Recovery attempts"
              value={String(result.recovery_attempt_count ?? recoveryAttempts.length ?? 0)}
              note="Attempts to recover weak extraction output."
              tone={(result.recovery_attempt_count ?? 0) > 0 ? 'brand' : 'slate'}
            />
          </section>

          <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
            <section className="section-frame">
              <div className="section-frame-header">
                <div>
                  <h2 className="section-title">Structured data</h2>
                  <p className="section-subtitle">
                    The extracted output, grouped and rendered in a readable form instead of raw object text.
                  </p>
                </div>
              </div>

              {result.structured_data && Object.keys(result.structured_data).length > 0 ? (
                <div className="space-y-4">
                  {Object.entries(result.structured_data).map(([key, value]) => (
                    <div key={key} className="rounded-2xl border border-[#2A2A3E] bg-[#11111F]/80 p-5">
                      <div className="mb-4 text-sm font-medium text-gray-300">{humanize(key)}</div>
                      <DataPreview value={value} />
                    </div>
                  ))}
                </div>
              ) : (
                <StatePanel
                  title="No structured output"
                  message="This result did not return any structured payload to display."
                  compact
                />
              )}
            </section>

            <div className="space-y-6">
              <section className="section-frame">
                <div className="section-frame-header">
                  <div>
                    <h2 className="section-title">Validation</h2>
                    <p className="section-subtitle">What the backend thinks about the quality of this result.</p>
                  </div>
                </div>

                {validation ? (
                  <div className="space-y-4">
                    <ValidationBanner decision={validation.decision} />
                    <div className="grid gap-3 sm:grid-cols-3">
                      <MiniPanel label="Confidence" value={`${(validation.confidence_score * 100).toFixed(1)}%`} />
                      <MiniPanel label="Errors" value={String(validation.error_count)} tone="red" />
                      <MiniPanel label="Warnings" value={String(validation.warning_count)} tone="amber" />
                    </div>
                    {(validation.review_reasons ?? []).length > 0 ? (
                      <div>
                        <div className="mb-2 text-sm font-medium text-white">Review reasons</div>
                        <div className="flex flex-wrap gap-2">
                          {validation.review_reasons.map((reason) => (
                            <span
                              key={reason}
                              className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs text-gray-300"
                            >
                              {reason}
                            </span>
                          ))}
                        </div>
                      </div>
                    ) : null}
                  </div>
                ) : (
                  <StatePanel
                    title="No validation summary"
                    message="The backend did not return validation detail for this result."
                    compact
                  />
                )}
              </section>

              <section className="section-frame">
                <div className="section-frame-header">
                  <div>
                    <h2 className="section-title">Review linkage</h2>
                    <p className="section-subtitle">
                      Human-review context and unresolved fields surfaced from the backend.
                    </p>
                  </div>
                </div>

                {result.review_case_id ? (
                  <div className="space-y-4">
                    <div className="rounded-2xl border border-amber-500/15 bg-[#1A1320]/85 p-4">
                      <div className="flex items-center justify-between gap-4">
                        <div>
                          <div className="text-sm font-semibold text-white">Review case linked</div>
                          <div className="mt-1 text-sm text-gray-300">
                            {reviewCount} field{reviewCount === 1 ? '' : 's'} are currently flagged for review.
                          </div>
                        </div>
                        <Link to={`/reviews/${result.review_case_id}`} className="btn-primary">
                          Open case
                        </Link>
                      </div>
                    </div>

                    {flaggedFields.length > 0 ? (
                      <div className="space-y-3">
                        {flaggedFields.map((field, index) => (
                          <div key={`${field.field_path}-${index}`} className="rounded-2xl border border-[#2A2A3E] bg-[#11111F]/80 p-4">
                            <div className="flex flex-wrap items-center gap-2">
                              <div className="text-sm font-medium text-white">
                                {field.display_label ?? field.label ?? humanize(field.field_path)}
                              </div>
                              {field.is_critical ? (
                                <span className="rounded-full border border-red-500/20 bg-red-500/10 px-2.5 py-1 text-[11px] font-medium text-red-200">
                                  Critical
                                </span>
                              ) : null}
                            </div>
                            <div className="mt-2 text-sm leading-6 text-gray-400">
                              {field.message ?? field.validation_message}
                            </div>
                            <div className="mt-4 grid gap-3">
                              <FieldValue title="Extracted value" value={field.original_value} />
                              {field.proposed_value != null ? (
                                <FieldValue title="AI proposed value" value={field.proposed_value} />
                              ) : null}
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <StatePanel
                        title="No unresolved fields surfaced"
                        message="A review case exists, but no field-level items were returned to the result page."
                        compact
                      />
                    )}
                  </div>
                ) : (
                  <StatePanel
                    title="No review case linked"
                    message="This result currently stands on its own without a review workflow attached."
                    tone="success"
                    compact
                  />
                )}
              </section>

              <section className="section-frame">
                <div className="section-frame-header">
                  <div>
                    <h2 className="section-title">Downloads</h2>
                    <p className="section-subtitle">Export the result in the format needed by downstream users.</p>
                  </div>
                </div>

                <div className="space-y-3">
                  {DOWNLOAD_FORMATS.map((format) => (
                    <button
                      key={format.key}
                      type="button"
                      className="flex w-full items-center justify-between rounded-2xl border border-[#2A2A3E] bg-[#121224]/70 px-4 py-4 text-left transition-colors hover:border-[#4F46E5]/35 hover:bg-[#17172B]"
                      onClick={async () => {
                        setDownloadingFormat(format.key);
                        try {
                          await resultsApi.download(result.job_id, format.key);
                        } finally {
                          setDownloadingFormat(null);
                        }
                      }}
                    >
                      <div>
                        <div className="text-sm font-medium text-white">{format.label}</div>
                        <div className="mt-1 text-sm text-gray-400">{format.hint}</div>
                      </div>
                      <div className="text-[#A5B4FC]">
                        {downloadingFormat === format.key ? (
                          <Loader2 className="h-5 w-5 animate-spin" />
                        ) : (
                          <Download className="h-5 w-5" />
                        )}
                      </div>
                    </button>
                  ))}
                </div>
              </section>
            </div>
          </div>

          <section className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
            <div className="section-frame">
              <div className="section-frame-header">
                <div>
                  <h2 className="section-title">Pipeline timings</h2>
                  <p className="section-subtitle">How long each visible stage took.</p>
                </div>
              </div>

              {stageTimings.length > 0 ? (
                <div className="space-y-3">
                  {stageTimings.map(([stage, seconds]) => (
                    <div key={stage} className="rounded-2xl border border-[#2A2A3E] bg-[#121224]/70 p-4">
                      <div className="flex items-center justify-between gap-4">
                        <div className="text-sm font-medium text-white">{humanize(stage)}</div>
                        <div className="text-sm text-[#A5B4FC]">{formatDuration(seconds)}</div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <StatePanel
                  title="No stage timings returned"
                  message="Stage-level duration data is not available for this result."
                  compact
                />
              )}
            </div>

            <div className="section-frame">
              <div className="section-frame-header">
                <div>
                  <h2 className="section-title">Recovery attempts</h2>
                  <p className="section-subtitle">Recovery history for weak-field handling and retries.</p>
                </div>
              </div>

              {recoveryLoading ? (
                <StatePanel
                  title="Loading recovery attempts"
                  message="Pulling recovery history for this result."
                  loading
                  compact
                />
              ) : recoveryAttempts.length > 0 ? (
                <div className="space-y-3">
                  {recoveryAttempts.map((attempt) => (
                    <div key={`${attempt.attempt_number}-${attempt.mode}-${attempt.strategy}`} className="rounded-2xl border border-[#2A2A3E] bg-[#121224]/70 p-4">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <div className="text-sm font-medium text-white">
                            Attempt {attempt.attempt_number} · {humanize(attempt.strategy)}
                          </div>
                          <div className="mt-1 text-sm text-gray-400">
                            {humanize(attempt.mode)} · {capitalize(attempt.status)}
                          </div>
                        </div>
                        <span className="soft-badge">
                          {attempt.improvement_score != null
                            ? `Improvement ${attempt.improvement_score.toFixed(2)}`
                            : attempt.accepted
                              ? 'Accepted'
                              : 'Not accepted'}
                        </span>
                      </div>
                      {(attempt.weak_fields ?? []).length > 0 ? (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {attempt.weak_fields?.map((field) => (
                            <span
                              key={field}
                              className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs text-gray-300"
                            >
                              {humanize(field)}
                            </span>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  ))}
                </div>
              ) : (
                <StatePanel
                  title="No recovery attempts"
                  message="This result does not show any recorded recovery history."
                  compact
                />
              )}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

function ResultMetric({
  title,
  value,
  note,
  tone,
}: {
  title: string;
  value: string;
  note: string;
  tone: 'brand' | 'green' | 'amber' | 'slate';
}) {
  const tones = {
    brand: 'border-[#4F46E5]/18 bg-[#12152C] text-[#A5B4FC]',
    green: 'border-green-500/15 bg-[#111D1B] text-green-300',
    amber: 'border-amber-500/15 bg-[#1D1711] text-amber-300',
    slate: 'border-[#2A2A3E] bg-[#121224] text-gray-300',
  };

  return (
    <div className={`rounded-2xl border p-5 ${tones[tone]}`}>
      <div className="text-xs font-medium uppercase tracking-[0.18em] text-gray-500">{title}</div>
      <div className="mt-3 text-2xl font-semibold text-white">{value}</div>
      <div className="mt-2 text-sm leading-6 text-gray-400">{note}</div>
    </div>
  );
}

function ValidationBanner({ decision }: { decision: string }) {
  const tone =
    decision === 'pass'
      ? 'border-green-500/20 bg-[#111D1B] text-green-300'
      : decision === 'fail'
        ? 'border-red-500/20 bg-[#1E1318] text-red-300'
        : 'border-amber-500/20 bg-[#1D1711] text-amber-300';

  return (
    <div className={`inline-flex items-center gap-2 rounded-full border px-3 py-2 text-sm font-medium ${tone}`}>
      {decision === 'pass' ? <CheckCircle2 className="h-4 w-4" /> : <AlertTriangle className="h-4 w-4" />}
      {decision === 'pass' ? 'Validation passed' : decision === 'fail' ? 'Validation failed' : 'Needs review'}
    </div>
  );
}

function MiniPanel({
  label,
  value,
  tone = 'slate',
}: {
  label: string;
  value: string;
  tone?: 'slate' | 'amber' | 'red';
}) {
  const toneClasses = {
    slate: 'text-gray-300',
    amber: 'text-amber-300',
    red: 'text-red-300',
  };
  return (
    <div className="rounded-2xl border border-[#2A2A3E] bg-[#11111F]/80 p-4 text-center">
      <div className={`text-2xl font-semibold ${toneClasses[tone]}`}>{value}</div>
      <div className="mt-1 text-xs uppercase tracking-[0.16em] text-gray-500">{label}</div>
    </div>
  );
}

function FieldValue({ title, value }: { title: string; value: unknown }) {
  return (
    <div className="rounded-xl border border-[#2A2A3E] bg-[#121224] p-4">
      <div className="mb-2 text-[11px] uppercase tracking-[0.16em] text-gray-500">{title}</div>
      <DataPreview value={value} compact />
    </div>
  );
}

function getFlaggedFields(result?: ExtractionResult, reviewCase?: ReviewCase): UnresolvedReviewField[] {
  if (!result) {
    return [];
  }

  if ((result.unresolved_review_fields ?? []).length > 0) {
    return result.unresolved_review_fields ?? [];
  }

  return (reviewCase?.fields ?? [])
    .filter((field) => field.status !== 'resolved')
    .map((field) => ({
      id: field.id,
      field_path: field.field_path,
      display_label: field.display_label ?? field.label ?? undefined,
      label: field.label ?? field.display_label ?? undefined,
      reason_code: field.reason_code,
      validation_message: field.validation_message,
      message: field.message ?? field.validation_message,
      original_value: field.original_value,
      proposed_value: field.proposed_value,
      evidence_text: field.evidence_text ?? field.evidence_snippet ?? undefined,
      is_critical: field.is_critical,
      priority_score: field.priority_score,
    }));
}

function normalizeRecoveryAttempts(value: unknown): RecoveryAttempt[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value as RecoveryAttempt[];
}

function capitalize(value: string) {
  return value.charAt(0).toUpperCase() + value.slice(1).replace(/_/g, ' ');
}

function humanize(value: string) {
  return value
    .replace(/_/g, ' ')
    .replace(/\./g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}
