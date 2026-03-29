import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useState, type ReactNode } from 'react';
import { Download, AlertTriangle, CheckCircle2, XCircle, Info, FileWarning, ClipboardCheck, Sparkles, Loader2 } from 'lucide-react';
import { resultsApi } from '@/lib/api/resultsApi';
import { jobsApi } from '@/lib/api/jobsApi';
import { reviewsApi } from '@/lib/api/reviewsApi';
import { StatusPill } from '@/components/ui/StatusPill';
import { DataPreview } from '@/components/ui/DataPreview';
import { formatDuration, formatConfidence } from '@/lib/utils';
import type { ExtractionResult, RecoveryAttempt, ReviewCase, UnresolvedReviewField } from '@/types/models';

type Tab = 'data' | 'validation' | 'recovery' | 'downloads';

export default function ResultPage() {
  const { id } = useParams<{ id: string }>();
  const [activeTab, setActiveTab] = useState<Tab>('data');

  const { data: result, isLoading, isError, refetch } = useQuery<ExtractionResult>({
    queryKey: ['result', 'detail', id],
    queryFn: () => resultsApi.get(id!),
    enabled: !!id,
  });

  const { data: recoveryData, isLoading: isRecoveryLoading, isFetching: isRecoveryFetching } = useQuery({
    queryKey: ['recovery', 'job', id],
    queryFn: () => jobsApi.getRecoveryAttempts(id!),
    enabled: !!id,
  });

  const {
    data: reviewCase,
    isLoading: isReviewCaseLoading,
    isFetching: isReviewCaseFetching,
  } = useQuery<ReviewCase>({
    queryKey: ['review', 'detail', result?.review_case_id],
    queryFn: () => reviewsApi.get(result!.review_case_id!),
    enabled: !!result?.review_case_id,
  });

  if (isLoading) {
    return (
      <div className="p-8">
        <div className="card p-8 space-y-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="h-8 bg-[#0F0F1A] rounded animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (isError || !result) {
    return (
      <div className="p-8 max-w-4xl mx-auto">
        <div className="card p-8 text-center">
          <AlertTriangle className="w-12 h-12 text-red-400 mx-auto mb-3" />
          <p className="text-gray-400 text-sm">Could not load result. It may not be ready yet.</p>
          <div className="mt-4 flex items-center justify-center gap-3">
            <button onClick={() => refetch()} className="btn-secondary">
              Retry
            </button>
            <Link to="/jobs" className="btn-primary inline-block">Back to Jobs</Link>
          </div>
        </div>
      </div>
    );
  }

  const tabs: { id: Tab; label: string }[] = [
    { id: 'data',       label: 'Structured Data' },
    { id: 'validation', label: 'Validation Report' },
    { id: 'recovery',   label: 'Recovery Attempts' },
    { id: 'downloads',  label: 'Downloads' },
  ];

  const validationDecision =
    result.validation_summary?.decision ??
    (result.status === 'completed'
      ? 'pass'
      : result.status === 'failed'
        ? 'fail'
        : result.status);
  const flaggedFields = resolveFlaggedFields(result, reviewCase);
  const hasStructuredData = !!result.structured_data && Object.keys(result.structured_data).length > 0;
  const reviewSummaryText = result.review_case_id
    ? `${flaggedFields.length} flagged field${flaggedFields.length === 1 ? '' : 's'} linked to this result`
    : 'No review case attached';

  return (
    <div className="p-8">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-gray-400 mb-6">
        <Link to="/jobs" className="hover:text-white">Jobs</Link>
        <span>/</span>
        <Link to={`/jobs/${id}`} className="hover:text-white font-mono text-xs">{id?.slice(0, 8)}...</Link>
        <span>/</span>
        <span className="text-white">Result</span>
      </div>

      <div className="card p-6 mb-6">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h2 className="text-xl font-semibold text-white mb-1">{result.file}</h2>
            <div className="flex gap-4 text-sm text-gray-400 flex-wrap">
              <span>Doc Type: <span className="text-white">{result.doc_type ?? '-'}</span></span>
              <span>Language: <span className="text-white">{result.lang ?? '-'}</span></span>
              <span>OCR Conf: <span className="text-white">{formatConfidence(result.ocr_conf)}</span></span>
              <span>Overall Conf: <span className="text-white">{formatConfidence(result.overall_conf)}</span></span>
              <span>Time: <span className="text-white">{formatDuration(result.processing_time_seconds)}</span></span>
            </div>
          </div>
          <StatusPill status={result.status} />
        </div>

        <ValidationBanner decision={validationDecision} />

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-5">
          <SummaryCard
            icon={<Sparkles className="w-4 h-4" />}
            title="Extraction Coverage"
            value={hasStructuredData ? `${Object.keys(result.structured_data ?? {}).length} sections` : 'No structured output'}
            hint={hasStructuredData ? 'Structured fields are available in the data tab below.' : 'This result has little or no structured payload.'}
            tone="brand"
          />
          <SummaryCard
            icon={<ClipboardCheck className="w-4 h-4" />}
            title="Validation"
            value={result.validation_summary ? `${Math.round(result.validation_summary.confidence_score * 100)}% confidence` : 'Not available'}
            hint={
              result.validation_summary
                ? `${result.validation_summary.error_count} errors, ${result.validation_summary.warning_count} warnings`
                : 'Validation summary was not returned for this result.'
            }
            tone={validationDecision === 'pass' ? 'green' : validationDecision === 'fail' ? 'red' : 'amber'}
          />
          <SummaryCard
            icon={<FileWarning className="w-4 h-4" />}
            title="Review Routing"
            value={result.review_case_id ? 'Review case linked' : 'No review case'}
            hint={reviewSummaryText}
            tone={result.review_case_id ? 'amber' : 'slate'}
          />
        </div>
      </div>

      <div className="card">
        <div className="flex border-b border-[#2A2A3E]">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-6 py-4 text-sm font-medium transition-colors ${
                activeTab === tab.id
                  ? 'text-white border-b-2 border-[#4F46E5] -mb-px'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div key={activeTab} className="p-6 tab-panel-transition">
          {activeTab === 'data' && <StructuredDataTab result={result} />}
          {activeTab === 'validation' && (
            <ValidationTab
              result={result}
              reviewCase={reviewCase}
              flaggedFields={flaggedFields}
              isLoading={isReviewCaseLoading || isReviewCaseFetching}
            />
          )}
          {activeTab === 'recovery' && (
            <RecoveryTab data={recoveryData} isLoading={isRecoveryLoading || isRecoveryFetching} />
          )}
          {activeTab === 'downloads' && <DownloadsTab result={result} />}
        </div>
      </div>
    </div>
  );
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function ValidationBanner({ decision }: { decision: string }) {
  const configs: Record<string, { icon: ReactNode; label: string; cls: string }> = {
    pass:          { icon: <CheckCircle2 className="w-4 h-4" />, label: 'Validation Passed', cls: 'bg-green-900/20 border-green-800/40 text-green-400' },
    needs_review:  { icon: <AlertTriangle className="w-4 h-4" />, label: 'Needs Review', cls: 'bg-amber-900/20 border-amber-800/40 text-amber-400' },
    low_confidence:{ icon: <Info className="w-4 h-4" />, label: 'Low Confidence', cls: 'bg-orange-900/20 border-orange-800/40 text-orange-400' },
    fail:          { icon: <XCircle className="w-4 h-4" />, label: 'Validation Failed', cls: 'bg-red-900/20 border-red-800/40 text-red-400' },
  };
  const cfg = configs[decision] ?? configs.needs_review;
  return (
    <div className={`flex items-center gap-2 px-4 py-2.5 rounded-lg border text-sm font-medium w-fit ${cfg.cls}`}>
      {cfg.icon}
      {cfg.label}
    </div>
  );
}

function StructuredDataTab({ result }: { result: ExtractionResult }) {
  const data = result.structured_data;
  if (!data || Object.keys(data).length === 0) {
    return (
      <div className="rounded-lg border border-[#2A2A3E] bg-[#0F0F1A] p-4 text-sm text-gray-400">
        No structured data extracted for this document.
      </div>
    );
  }
  return (
    <div className="space-y-4">
      {Object.entries(data).map(([key, val]) => (
        <div key={key} className="rounded-xl border border-[#2A2A3E] bg-[#0F0F1A] p-4">
          <h4 className="text-sm font-medium text-gray-300 mb-3 capitalize">{key.replace(/_/g, ' ')}</h4>
          <DataPreview value={val} />
        </div>
      ))}
    </div>
  );
}

function ValidationTab({
  result,
  reviewCase,
  flaggedFields,
  isLoading,
}: {
  result: ExtractionResult;
  reviewCase?: ReviewCase;
  flaggedFields: UnresolvedReviewField[];
  isLoading: boolean;
}) {
  const vs = result.validation_summary;
  if (!vs) return <p className="text-gray-500 text-sm">No validation report available.</p>;
  if (isLoading && result.review_case_id) {
    return (
      <div className="rounded-lg border border-[#2A2A3E] bg-[#0F0F1A] p-4 text-sm text-gray-400">
        Loading validation and review context...
      </div>
    );
  }
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-[#0F0F1A] rounded-lg p-4 text-center">
          <div className="text-2xl font-semibold text-white mb-1">{(vs.confidence_score * 100).toFixed(1)}%</div>
          <div className="text-xs text-gray-400">Confidence Score</div>
        </div>
        <div className="bg-[#0F0F1A] rounded-lg p-4 text-center">
          <div className="text-2xl font-semibold text-red-400 mb-1">{vs.error_count}</div>
          <div className="text-xs text-gray-400">Errors</div>
        </div>
        <div className="bg-[#0F0F1A] rounded-lg p-4 text-center">
          <div className="text-2xl font-semibold text-amber-400 mb-1">{vs.warning_count}</div>
          <div className="text-xs text-gray-400">Warnings</div>
        </div>
      </div>

      {vs.review_reasons.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-gray-300 mb-3">Review Reasons</h4>
          <div className="flex gap-2 flex-wrap">
            {vs.review_reasons.map((r) => (
              <span key={r} className="px-2.5 py-1 rounded-full text-xs bg-amber-900/30 text-amber-300">{r}</span>
            ))}
          </div>
        </div>
      )}

      {flaggedFields.length > 0 && (
        <div>
          <div className="flex items-center justify-between gap-4 mb-3">
            <h4 className="text-sm font-medium text-gray-300">Flagged Fields</h4>
            {result.review_case_id && (
              <Link to={`/reviews/${result.review_case_id}`} className="text-sm text-[#A5B4FC] hover:text-white transition-colors">
                Open review case
              </Link>
            )}
          </div>
          <div className="space-y-3">
            {flaggedFields.map((f, i) => (
              <div key={i} className="p-4 bg-[#0F0F1A] rounded-lg border border-[#2A2A3E]">
                <div className="flex items-center gap-2 mb-2 flex-wrap">
                  <span className="font-mono text-xs text-[#4F46E5]">{f.field_path}</span>
                  <span className="px-2 py-0.5 rounded text-xs bg-amber-900/30 text-amber-300">{f.reason_code}</span>
                </div>
                <p className="text-sm text-gray-300">{f.validation_message}</p>
                <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div className="rounded-lg border border-[#2A2A3E] bg-[#121224] p-3">
                    <div className="text-xs uppercase tracking-wider text-gray-500 mb-1">Extracted Value</div>
                    <DataPreview value={f.original_value} compact emptyLabel="No extracted value" />
                  </div>
                  <div className="rounded-lg border border-[#2A2A3E] bg-[#121224] p-3">
                    <div className="text-xs uppercase tracking-wider text-gray-500 mb-1">AI Proposed Value</div>
                    <DataPreview value={f.proposed_value} compact emptyLabel="No AI proposal" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {flaggedFields.length === 0 && result.review_case_id && (
        <div className="rounded-lg border border-[#2A2A3E] bg-[#0F0F1A] p-4 flex items-center justify-between gap-4">
          <div>
            <div className="text-sm font-medium text-white mb-1">Review case exists, but no field payload is attached to this result.</div>
            <div className="text-sm text-gray-400">Open the review case to inspect the outstanding field-level decisions directly.</div>
          </div>
          <Link to={`/reviews/${result.review_case_id}`} className="btn-secondary">
            Open Review
          </Link>
        </div>
      )}

      {reviewCase && reviewCase.reason_codes && reviewCase.reason_codes.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-gray-300 mb-3">Review Case Reasons</h4>
          <div className="flex gap-2 flex-wrap">
            {reviewCase.reason_codes.map((reason) => (
              <span key={reason} className="px-2.5 py-1 rounded-full text-xs bg-[#1A1A2E] text-gray-300">
                {reason}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function RecoveryTab({ data, isLoading }: { data: unknown; isLoading: boolean }) {
  if (isLoading) {
    return <p className="text-gray-500 text-sm">Loading recovery attempts...</p>;
  }

  const attempts: RecoveryAttempt[] = Array.isArray(data)
    ? data as RecoveryAttempt[]
    : ((data as { attempts?: RecoveryAttempt[] } | undefined)?.attempts ?? []);

  if (attempts.length === 0) {
    return (
      <div className="rounded-lg border border-[#2A2A3E] bg-[#0F0F1A] p-4 text-sm text-gray-400">
        No recovery attempts were run for this job. Current policy keeps recovery conservative and only runs it when the validator marks eligible weak fields.
      </div>
    );
  }
  return (
    <div className="space-y-3">
      <p className="text-xs text-gray-500 mb-4">Recovery attempts are audit information. They do not guarantee auto-correction.</p>
      {attempts.map((attempt, i) => {
        const attemptNumber = typeof attempt.attempt_number === 'number' ? attempt.attempt_number : i + 1;
        return (
          <div key={i} className="p-4 bg-[#0F0F1A] rounded-lg border border-[#2A2A3E]">
            <div className="flex items-center gap-3 mb-2">
              <span className="text-sm font-medium text-white">Attempt #{attemptNumber}</span>
              <span className={`px-2 py-0.5 rounded text-xs ${attempt.accepted ? 'bg-green-900/30 text-green-300' : 'bg-red-900/20 text-red-300'}`}>
                {attempt.accepted ? 'Accepted' : 'Not Accepted'}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs text-gray-400">
              <span>Mode: <span className="text-white">{attempt.mode ?? '-'}</span></span>
              <span>Strategy: <span className="text-white">{attempt.strategy ?? '-'}</span></span>
              <span>Status: <span className="text-white">{attempt.status ?? '-'}</span></span>
              <span>
                Improvement:{' '}
                <span className="text-white">
                  {typeof attempt.improvement_score === 'number' ? `${Math.round(attempt.improvement_score * 100)}%` : '-'}
                </span>
              </span>
            </div>
            {attempt.weak_fields && attempt.weak_fields.length > 0 && (
              <div className="mt-3">
                <div className="text-xs uppercase tracking-wider text-gray-500 mb-1">Weak Fields</div>
                <div className="flex flex-wrap gap-2">
                  {attempt.weak_fields.map((field) => (
                    <span key={field} className="rounded-full bg-[#1A1A2E] px-3 py-1 text-xs text-gray-200">
                      {field}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function DownloadsTab({ result }: { result: ExtractionResult }) {
  const [downloading, setDownloading] = useState<string | null>(null);
  const artifacts = result.artifacts ?? {};
  const formats = [
    { key: 'json', label: 'JSON', desc: 'Full structured extraction result' },
    { key: 'csv', label: 'CSV', desc: 'Tabular extracted fields' },
    { key: 'xlsx', label: 'Excel (.xlsx)', desc: 'Formatted spreadsheet' },
    { key: 'html', label: 'HTML Report', desc: 'Styled extraction report' },
  ] as const;

  async function handleDownload(format: 'json' | 'csv' | 'xlsx' | 'html') {
    try {
      setDownloading(format);
      await resultsApi.download(result.job_id, format);
    } finally {
      setDownloading(null);
    }
  }

  return (
    <div className="grid grid-cols-2 gap-4">
      {formats.map(({ key, label, desc }) => {
        const url = artifacts[key];
        return (
          <div key={key} className={`p-5 rounded-lg border ${url ? 'border-[#2A2A3E] bg-[#0F0F1A]' : 'border-[#1F1F2E] bg-[#0F0F1A]/50 opacity-50'}`}>
            <div className="flex items-center justify-between mb-2">
              <span className="font-medium text-white text-sm">{label}</span>
              {url ? (
                <button
                  type="button"
                  onClick={() => handleDownload(key)}
                  disabled={downloading === key}
                  className="p-2 text-[#4F46E5] hover:text-white hover:bg-[#2A2A3E] rounded transition-colors disabled:opacity-50"
                >
                  {downloading === key ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                </button>
              ) : (
                <span className="text-xs text-gray-600">Unavailable</span>
              )}
            </div>
            <p className="text-xs text-gray-400">{desc}</p>
          </div>
        );
      })}
    </div>
  );
}

function SummaryCard({
  icon,
  title,
  value,
  hint,
  tone,
}: {
  icon: ReactNode;
  title: string;
  value: string;
  hint: string;
  tone: 'brand' | 'green' | 'amber' | 'red' | 'slate';
}) {
  const toneClasses: Record<string, string> = {
    brand: 'text-[#A5B4FC]',
    green: 'text-green-300',
    amber: 'text-amber-300',
    red: 'text-red-300',
    slate: 'text-gray-300',
  };

  return (
    <div className="rounded-xl border border-[#2A2A3E] bg-[#0F0F1A] p-4">
      <div className="flex items-center gap-2 text-xs uppercase tracking-wider text-gray-500 mb-2">
        <span className={toneClasses[tone]}>{icon}</span>
        {title}
      </div>
      <div className={`text-lg font-semibold mb-1 ${toneClasses[tone]}`}>{value}</div>
      <div className="text-xs text-gray-500 leading-relaxed">{hint}</div>
    </div>
  );
}

function resolveFlaggedFields(result: ExtractionResult, reviewCase?: ReviewCase): UnresolvedReviewField[] {
  if (result.unresolved_review_fields && result.unresolved_review_fields.length > 0) {
    return result.unresolved_review_fields;
  }

  if (!reviewCase) {
    return [];
  }

  return reviewCase.fields
    .filter((field) => field.status === 'open' || field.status === 'pending')
    .map((field) => ({
      field_path: field.field_path,
      reason_code: field.reason_code,
      validation_message: field.validation_message,
      original_value: field.original_value,
      proposed_value: field.proposed_value,
    }));
}
