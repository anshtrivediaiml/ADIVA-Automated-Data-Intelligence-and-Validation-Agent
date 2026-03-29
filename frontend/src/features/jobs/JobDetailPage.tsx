import { useState, type ReactNode } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CheckCircle, Circle, Loader2, Clock, AlertTriangle, ArrowRight, FileWarning, ShieldCheck, Sparkles, Trash2 } from 'lucide-react';
import { jobsApi } from '@/lib/api/jobsApi';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { StatusPill } from '@/components/ui/StatusPill';
import { formatDate, formatDuration, isTerminalStatus } from '@/lib/utils';
import type { Job } from '@/types/models';

const STAGE_ORDER = [
  'quality_assessment',
  'text_extraction',
  'document_classification',
  'structured_extraction',
  'persist_outputs',
  'audit_validation',
];

const STAGE_LABELS: Record<string, string> = {
  quality_assessment:         'Preprocessing',
  text_extraction:            'OCR Extraction',
  document_classification:    'Classification',
  structured_extraction:      'Structured Extraction',
  persist_outputs:            'Persist Outputs',
  audit_validation:           'Validation',
};

const STAGE_DESCRIPTIONS: Record<string, string> = {
  quality_assessment: 'Checks file quality, rotation, and whether normalization is needed before OCR.',
  text_extraction: 'Runs OCR and layout parsing to extract machine-readable text from the document.',
  document_classification: 'Determines the most likely document type to select the correct extraction schema.',
  structured_extraction: 'Builds typed structured fields from OCR text using schema-aware extraction logic.',
  persist_outputs: 'Saves structured output and generates downloadable artifacts like JSON, CSV, Excel, and HTML.',
  audit_validation: 'Runs validation, scoring, review-case creation, and recovery eligibility checks.',
};

export default function JobDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);

  const { data: job, isLoading, isError } = useQuery<Job>({
    queryKey: ['job', id],
    queryFn: () => jobsApi.get(id!),
    enabled: !!id,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && isTerminalStatus(status) ? false : 3000;
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (jobId: string) => jobsApi.remove(jobId),
    onSuccess: (_, jobId) => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
      queryClient.invalidateQueries({ queryKey: ['reviews'] });
      queryClient.invalidateQueries({ queryKey: ['result'] });
      queryClient.invalidateQueries({ queryKey: ['recovery'] });
      navigate('/jobs');
    },
  });

  if (isLoading) {
    return (
      <div className="p-8 max-w-3xl mx-auto">
        <div className="card p-8 space-y-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-10 bg-[#0F0F1A] rounded-lg animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (isError || !job) {
    return (
      <div className="p-8 max-w-3xl mx-auto">
        <div className="card p-8 text-center">
          <AlertTriangle className="w-12 h-12 text-red-400 mx-auto mb-3" />
          <p className="text-gray-400 text-sm">Could not load job. Check that the job ID is valid.</p>
          <Link to="/jobs" className="btn-primary mt-4 inline-block">Back to Jobs</Link>
        </div>
      </div>
    );
  }

  const timings = job.timings ?? {};
  const terminal = isTerminalStatus(job.status);
  const resolvedStageIdx = STAGE_ORDER.indexOf(job.current_stage ?? '');
  const activeStageKey = !terminal && resolvedStageIdx >= 0 ? STAGE_ORDER[resolvedStageIdx] : null;

  const currentStageIdx =
    terminal && job.status !== 'failed'
      ? STAGE_ORDER.length
      : job.status === 'queued' && resolvedStageIdx < 0
        ? -1
        : resolvedStageIdx;

  const handleDelete = () => {
    setShowDeleteDialog(true);
  };

  const confirmDelete = () => {
    if (deleteMutation.isPending) {
      return;
    }
    deleteMutation.mutate(job.job_id, {
      onSuccess: () => {
        setShowDeleteDialog(false);
      },
    });
  };

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <ConfirmDialog
        open={showDeleteDialog}
        title="Delete job?"
        description={`Delete the job for "${job.file_name ?? job.job_id}"? This removes the job, its outputs, and any linked review data permanently.`}
        confirmLabel={deleteMutation.isPending ? 'Deleting...' : 'Delete Job'}
        cancelLabel="Keep Job"
        tone="danger"
        busy={deleteMutation.isPending}
        onCancel={() => setShowDeleteDialog(false)}
        onConfirm={confirmDelete}
      />

      <div className="mb-6">
        <div className="flex items-center gap-2 text-sm text-gray-400 mb-2">
          <Link to="/jobs" className="hover:text-white transition-colors">Jobs</Link>
          <span>/</span>
          <span className="font-mono text-xs">{job.job_id.slice(0, 8)}...</span>
        </div>
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-2xl font-semibold text-white">Job Status</h2>
            <p className="text-sm text-gray-400 mt-1">Track the backend pipeline stage by stage for this document.</p>
          </div>
          <button
            type="button"
            onClick={handleDelete}
            disabled={deleteMutation.isPending}
            className="btn-secondary inline-flex items-center gap-2 border-red-500/30 text-red-300 hover:bg-red-500/10 hover:text-red-200 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {deleteMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
            Delete Job
          </button>
        </div>
      </div>

      <div className="card p-8">
        {/* Job header */}
        <div className="mb-8 pb-6 border-b border-[#2A2A3E]">
          <div className="flex items-start justify-between mb-4">
            <div className="flex-1">
              <h3 className="text-lg font-medium text-white mb-3">{job.file_name ?? `Job ${job.job_id.slice(0, 8)}`}</h3>
              <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-sm">
                <MetaRow label="Job ID" value={<span className="font-mono text-xs">{job.job_id}</span>} />
                <MetaRow label="Doc Type" value={job.doc_type ?? '-'} />
                <MetaRow label="Submitted" value={formatDate(job.submitted_at)} />
                <MetaRow label="Finished" value={formatDate(job.finished_at)} />
              </div>
            </div>
            <StatusPill status={job.status} />
          </div>

          {/* Failure reason */}
          {job.failure_reason && (
            <div className="mt-3 p-3 rounded-lg bg-red-900/20 border border-red-800/40">
              <p className="text-sm text-red-400"><span className="font-medium">Failure: </span>{job.failure_reason}</p>
            </div>
          )}
        </div>

        <div className="grid grid-cols-3 gap-4 mb-8">
          <SummaryPanel
            label="Current State"
            value={terminal ? resolveTerminalLabel(job.status) : activeStageKey ? STAGE_LABELS[activeStageKey] : 'Queued'}
            hint={terminal ? resolveTerminalHint(job.status) : activeStageKey ? STAGE_DESCRIPTIONS[activeStageKey] : 'Waiting for a worker to begin processing.'}
            icon={terminal ? resolveTerminalIcon(job.status) : <Sparkles className="w-4 h-4" />}
            tone={terminal ? resolveTerminalTone(job.status) : 'brand'}
          />
          <SummaryPanel
            label="Review Routing"
            value={job.review_case_id ? 'Review Case Open' : job.status === 'needs_review' ? 'Review Pending' : 'No Review Case'}
            hint={job.review_case_id ? 'Human correction is required before the result can be finalized.' : 'No human review case is currently attached to this job.'}
            icon={<FileWarning className="w-4 h-4" />}
            tone={job.review_case_id ? 'amber' : 'slate'}
          />
          <SummaryPanel
            label="Pipeline Mode"
            value={terminal ? 'Terminal' : 'Refreshing live'}
            hint={terminal ? 'This job is no longer changing automatically.' : 'The page refreshes every 3 seconds while work is still running.'}
            icon={<ShieldCheck className="w-4 h-4" />}
            tone={terminal ? 'green' : 'blue'}
          />
        </div>

        {/* Stage timeline */}
        <div className="mb-8">
          <h4 className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-6">
            Processing Stages
          </h4>
          <div className="relative">
            <div className="absolute left-3 top-0 bottom-0 w-0.5 bg-[#2A2A3E]" />
            <div className="space-y-0">
              {STAGE_ORDER.map((stageKey, idx) => {
                const isFailedStage = terminal && job.status === 'failed' && idx === currentStageIdx;
                const isDone = terminal && job.status !== 'failed'
                  ? true
                  : currentStageIdx >= 0 && idx < currentStageIdx;
                const isActive = !terminal && currentStageIdx >= 0 && idx === currentStageIdx;
                const duration = timings[stageKey] ?? timings[STAGE_LABELS[stageKey]];

                return (
                  <div key={stageKey} className="relative flex items-start gap-6 pb-7 last:pb-0">
                    <div className="relative z-10 flex-shrink-0">
                      {isDone ? (
                        <div className="w-6 h-6 rounded-full bg-green-500/20 flex items-center justify-center">
                          <CheckCircle className="w-4 h-4 text-green-400" />
                        </div>
                      ) : isFailedStage ? (
                        <div className="w-6 h-6 rounded-full bg-red-500/20 flex items-center justify-center">
                          <AlertTriangle className="w-4 h-4 text-red-400" />
                        </div>
                      ) : isActive ? (
                        <div className="w-6 h-6 rounded-full bg-[#4F46E5]/20 flex items-center justify-center">
                          <Loader2 className="w-4 h-4 text-[#4F46E5] animate-spin" />
                        </div>
                      ) : (
                        <div className="w-6 h-6 rounded-full bg-[#2A2A3E] flex items-center justify-center">
                          <Circle className="w-3 h-3 text-gray-600" />
                        </div>
                      )}
                    </div>
                    <div className="flex-1 pt-0.5">
                      <div className="flex items-center justify-between mb-0.5">
                        <span className={`font-medium text-sm ${
                          isDone ? 'text-green-400' : isFailedStage ? 'text-red-400' : isActive ? 'text-white' : 'text-gray-500'
                        }`}>
                          {STAGE_LABELS[stageKey]}
                        </span>
                        {duration != null && (
                          <span className="flex items-center gap-1 text-xs text-gray-400">
                            <Clock className="w-3 h-3" />
                            {formatDuration(duration)}
                          </span>
                        )}
                      </div>
                      <p className={`text-xs ${
                        isDone ? 'text-gray-500' : isFailedStage ? 'text-red-400/90' : isActive ? 'text-gray-400' : 'text-gray-600'
                      }`}>
                        {isFailedStage ? 'Pipeline stopped here.' : STAGE_DESCRIPTIONS[stageKey]}
                      </p>
                      {isActive && (
                        <div className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-[#4F46E5]/10 px-2.5 py-1 text-[11px] text-[#A5B4FC]">
                          <Loader2 className="w-3 h-3 animate-spin" />
                          In progress
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* CTA */}
        {terminal && (
          <div className="flex gap-3 pt-6 border-t border-[#2A2A3E] justify-center">
            {(job.status === 'completed' || job.status === 'needs_review' || job.status === 'low_confidence') && (
              <Link to={`/jobs/${job.job_id}/result`} className="btn-primary">
                View Result
              </Link>
            )}
            {job.status === 'needs_review' && job.review_case_id && (
              <Link to={`/reviews/${job.review_case_id}`} className="btn-secondary" style={{ background: '#78350f20', borderColor: '#92400e50', color: '#fcd34d' }}>
                Open Review Case
              </Link>
            )}
            <Link to="/jobs" className="btn-secondary">
              Back to Jobs
            </Link>
          </div>
        )}

        {!terminal && (
          <div className="rounded-lg border border-[#2A2A3E] bg-[#0F0F1A] px-4 py-3 text-sm text-gray-400 flex items-center justify-between">
            <span>Refreshing every 3 seconds while this job is active.</span>
            <div className="inline-flex items-center gap-2 text-[#A5B4FC]">
              <Loader2 className="w-4 h-4 animate-spin" />
              Live tracking
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function MetaRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex gap-2">
      <span className="text-gray-400 whitespace-nowrap">{label}:</span>
      <span className="text-white">{value}</span>
    </div>
  );
}

function SummaryPanel({
  label,
  value,
  hint,
  icon,
  tone,
}: {
  label: string;
  value: string;
  hint: string;
  icon: ReactNode;
  tone: 'brand' | 'green' | 'amber' | 'blue' | 'red' | 'slate';
}) {
  const toneClasses: Record<string, string> = {
    brand: 'text-[#A5B4FC]',
    green: 'text-green-300',
    amber: 'text-amber-300',
    blue: 'text-blue-300',
    red: 'text-red-300',
    slate: 'text-gray-300',
  };

  return (
    <div className="rounded-xl border border-[#2A2A3E] bg-[#0F0F1A] p-4">
      <div className="flex items-center gap-2 text-xs uppercase tracking-wider text-gray-500 mb-2">
        <span className={toneClasses[tone]}>{icon}</span>
        {label}
      </div>
      <div className={`text-lg font-semibold mb-1 ${toneClasses[tone]}`}>{value}</div>
      <div className="text-xs text-gray-500 leading-relaxed">{hint}</div>
    </div>
  );
}

function resolveTerminalLabel(status: Job['status']): string {
  switch (status) {
    case 'completed':
      return 'Completed';
    case 'needs_review':
      return 'Needs Review';
    case 'low_confidence':
      return 'Low Confidence';
    case 'failed':
      return 'Failed';
    default:
      return 'Finished';
  }
}

function resolveTerminalHint(status: Job['status']): string {
  switch (status) {
    case 'completed':
      return 'Processing finished successfully and the result is ready to inspect.';
    case 'needs_review':
      return 'Extraction finished, but human review is required before the result should be trusted.';
    case 'low_confidence':
      return 'Extraction finished with weak confidence and should be reviewed carefully.';
    case 'failed':
      return 'The pipeline stopped before completion. Check the failure reason shown above.';
    default:
      return 'This job has reached a terminal state.';
  }
}

function resolveTerminalTone(status: Job['status']): 'green' | 'amber' | 'red' {
  switch (status) {
    case 'completed':
      return 'green';
    case 'failed':
      return 'red';
    default:
      return 'amber';
  }
}

function resolveTerminalIcon(status: Job['status']): ReactNode {
  switch (status) {
    case 'completed':
      return <CheckCircle className="w-4 h-4" />;
    case 'failed':
      return <AlertTriangle className="w-4 h-4" />;
    default:
      return <ArrowRight className="w-4 h-4" />;
  }
}
