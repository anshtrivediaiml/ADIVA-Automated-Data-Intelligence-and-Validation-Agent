import { useQuery } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  ClipboardList,
  Clock3,
  Layers3,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Upload,
  Workflow,
  XCircle,
} from 'lucide-react';
import { StatusPill } from '@/components/ui/StatusPill';
import { dashboardApi } from '@/lib/api/dashboardApi';
import { formatDate } from '@/lib/utils';
import type { DashboardRecentJob, DashboardReviewSpotlight } from '@/types/models';

export default function DashboardLandingPage() {
  const {
    data: summary,
    isLoading: summaryLoading,
    isError: summaryError,
    refetch: refetchSummary,
  } = useQuery({
    queryKey: ['dashboard-summary'],
    queryFn: () => dashboardApi.summary(),
    staleTime: 10_000,
    refetchOnWindowFocus: false,
  });

  const jobsLoading = summaryLoading;
  const jobsError = summaryError;
  const reviewsLoading = summaryLoading;
  const reviewsError = summaryError;
  const totalJobs = summary?.total_jobs ?? 0;
  const jobsToday = summary?.jobs_today ?? 0;
  const completedToday = summary?.completed_today ?? 0;
  const completedCount = summary?.completed_count ?? 0;
  const successRate = summary?.success_rate != null ? `${summary.success_rate.toFixed(1)}%` : '-';
  const needsReviewCount = summary?.needs_review_count ?? 0;
  const lowConfidenceCount = summary?.low_confidence_count ?? 0;
  const queuedCount = summary?.queued_count ?? 0;
  const processingCount = summary?.processing_count ?? 0;
  const failedCount = summary?.failed_count ?? 0;
  const activeCount = summary?.active_count ?? 0;
  const openReviewCount = summary?.open_review_cases ?? 0;
  const recentJobs: DashboardRecentJob[] = summary?.recent_jobs ?? [];
  const commonReviewDocType = summary?.common_review_doc_type ?? null;
  const totalOpenFields = summary?.total_open_review_fields ?? 0;
  const healthStatus = summary?.health_status ?? 'unknown';
  const reviewSpotlight: DashboardReviewSpotlight[] = summary?.review_spotlight ?? [];

  return (
    <div className="p-8">
      <div className="mb-8 flex items-start justify-between gap-6">
        <div>
          <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-[#4F46E5]/30 bg-[#4F46E5]/10 px-3 py-1 text-xs font-medium uppercase tracking-[0.22em] text-[#A5B4FC]">
            <Sparkles className="h-3.5 w-3.5" />
            Live Operations Overview
          </div>
          <h2 className="mb-2 text-3xl font-semibold tracking-tight text-white">Dashboard</h2>
          <p className="max-w-3xl text-sm leading-6 text-gray-400">
            Monitor document throughput, review pressure, and operator workload from one place. This
            view is optimized for awareness and direction, while detailed row-level actions stay in the
            jobs and reviews workspaces.
          </p>
        </div>

        <button
          onClick={() => {
            refetchSummary();
          }}
          className="btn-ghost flex shrink-0 items-center gap-2"
          title="Refresh dashboard"
        >
          <RefreshCw className="h-4 w-4" />
          Refresh
        </button>
      </div>

      <div className="mb-8 grid grid-cols-[1.7fr_1fr] gap-6">
        <div className="card overflow-hidden p-0">
          <div className="border-b border-[#2A2A3E] bg-[radial-gradient(circle_at_top_left,rgba(79,70,229,0.22),transparent_36%),linear-gradient(180deg,rgba(25,25,44,0.96),rgba(18,18,32,0.94))] px-7 py-7">
            <div className="mb-6 flex flex-wrap items-start justify-between gap-5">
              <div>
                <div className="mb-2 flex items-center gap-2 text-sm font-medium text-[#A5B4FC]">
                  <Activity className="h-4 w-4" />
                  Control Tower
                </div>
                <div className="text-2xl font-semibold text-white">
                  {jobsLoading ? 'Loading dashboard signal...' : `${activeCount} active jobs in motion`}
                </div>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-gray-400">
                  Keep an eye on live processing, review escalation, and quality drop-offs before they
                  affect turnaround time.
                </p>
              </div>

              <div className="flex flex-wrap gap-2">
                <HeroBadge icon={<Clock3 className="h-4 w-4" />} label="Queued" value={queuedCount} tone="slate" />
                <HeroBadge icon={<Workflow className="h-4 w-4" />} label="Processing" value={processingCount} tone="blue" />
                <HeroBadge icon={<ClipboardList className="h-4 w-4" />} label="Open Reviews" value={openReviewCount} tone="amber" />
                <HeroBadge
                  icon={<ShieldCheck className="h-4 w-4" />}
                  label="System"
                  value={capitalize(healthStatus)}
                  tone={healthStatus === 'healthy' ? 'green' : healthStatus === 'degraded' ? 'amber' : 'red'}
                />
              </div>
            </div>

            <div className="grid grid-cols-4 gap-4">
              <FocusCard
                title="Today"
                value={String(jobsToday)}
                description={`${completedToday} completed today`}
                tone="brand"
                icon={<Sparkles className="h-4 w-4" />}
              />
              <FocusCard
                title="Review Pressure"
                value={String(needsReviewCount)}
                description={`${totalOpenFields} unresolved flagged fields`}
                tone="amber"
                icon={<ClipboardList className="h-4 w-4" />}
              />
              <FocusCard
                title="Success Rate"
                value={successRate}
                description={`${completedCount} of ${totalJobs} jobs completed`}
                tone="green"
                icon={<CheckCircle2 className="h-4 w-4" />}
              />
              <FocusCard
                title="Low Confidence"
                value={String(lowConfidenceCount)}
                description={`${failedCount} failed jobs in the visible window`}
                tone="orange"
                icon={<AlertTriangle className="h-4 w-4" />}
              />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-4 px-7 py-6">
            <ActionLink
              to="/upload"
              icon={<Upload className="h-4 w-4" />}
              title="Upload a document"
              description="Start a single extraction job and jump straight into tracking."
            />
            <ActionLink
              to="/batch"
              icon={<Layers3 className="h-4 w-4" />}
              title="Run a batch"
              description="Queue multiple files together when you need throughput over inspection."
            />
            <ActionLink
              to="/reviews"
              icon={<ClipboardList className="h-4 w-4" />}
              title="Open review queue"
              description="Resolve weak fields before they block operator confidence."
            />
          </div>
        </div>

        <div className="card p-6">
          <div className="mb-5 flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-white">Control Signals</h3>
              <p className="mt-1 text-sm text-gray-400">High-level operating pressure</p>
            </div>
            <Link to="/jobs" className="text-sm text-[#818CF8] transition-colors hover:text-[#A5B4FC]">
              Jobs workspace
            </Link>
          </div>

          {jobsLoading ? (
            <MetricGridSkeleton compact />
          ) : jobsError ? (
            <InlineError message="Failed to load dashboard signals." onAction={() => refetchSummary()} compact />
          ) : (
            <div className="space-y-4">
              <SignalRow
                label="Pipeline health"
                value={healthStatus === 'healthy' ? 'Stable' : capitalize(healthStatus)}
                subtext={healthStatus === 'healthy' ? 'No immediate backend issues detected' : 'Operational attention recommended'}
                tone={healthStatus === 'healthy' ? 'green' : healthStatus === 'degraded' ? 'amber' : 'red'}
              />
              <SignalRow
                label="Backlog"
                value={`${queuedCount} queued`}
                subtext={processingCount > 0 ? `${processingCount} currently processing` : 'No jobs are actively running'}
                tone={queuedCount > 0 || processingCount > 0 ? 'blue' : 'slate'}
              />
              <SignalRow
                label="Human review"
                value={`${openReviewCount} open cases`}
                subtext={
                  commonReviewDocType
                    ? `Most frequent document type: ${commonReviewDocType}`
                    : 'No pending review load'
                }
                tone={openReviewCount > 0 ? 'amber' : 'green'}
              />
              <SignalRow
                label="Failures"
                value={`${failedCount} jobs`}
                subtext={failedCount > 0 ? 'Investigate the jobs workspace for recent failures' : 'No recent failed jobs'}
                tone={failedCount > 0 ? 'red' : 'green'}
              />
              <div className="rounded-xl border border-[#312F54] bg-[#141427] px-4 py-4">
                <div className="mb-2 text-xs font-medium uppercase tracking-[0.18em] text-[#818CF8]">
                  Operator Note
                </div>
                <p className="text-sm leading-6 text-gray-300">
                  Use this page for awareness. Use the jobs workspace for row-level action and the review
                  queue for human correction.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>



      <div className="grid grid-cols-[1.5fr_1fr] gap-6">
        <div className="card p-6">
          <div className="mb-5 flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-white">Pipeline Lanes</h3>
              <p className="mt-1 text-sm text-gray-400">
                Proportion of {totalJobs} tracked jobs by status
              </p>
            </div>
            <Link to="/jobs" className="text-sm text-[#818CF8] transition-colors hover:text-[#A5B4FC]">
              Open jobs workspace
            </Link>
          </div>

          {jobsLoading ? (
            <MetricGridSkeleton />
          ) : jobsError ? (
            <InlineError message="Failed to load pipeline summary." onAction={() => refetchSummary()} />
          ) : (
            <div className="grid grid-cols-[1.2fr_0.8fr] gap-5">
              <div className="space-y-4">
                <WorkflowLane
                  label="Queued intake"
                  value={queuedCount}
                  max={Math.max(totalJobs, 1)}
                  tone="slate"
                  caption="Waiting to enter the pipeline"
                />
                <WorkflowLane
                  label="In processing"
                  value={processingCount}
                  max={Math.max(totalJobs, 1)}
                  tone="blue"
                  caption="Currently in OCR, extraction, or validation"
                />
                <WorkflowLane
                  label="Completed"
                  value={completedCount}
                  max={Math.max(totalJobs, 1)}
                  tone="green"
                  caption="Finished successfully — results are ready"
                />
                <WorkflowLane
                  label="Needs review"
                  value={needsReviewCount}
                  max={Math.max(totalJobs, 1)}
                  tone="amber"
                  caption="Requires human confirmation before trust increases"
                />
                <WorkflowLane
                  label="Low confidence"
                  value={lowConfidenceCount}
                  max={Math.max(totalJobs, 1)}
                  tone="orange"
                  caption="Useful result available, but confidence remains weak"
                />
                <WorkflowLane
                  label="Failed"
                  value={failedCount}
                  max={Math.max(totalJobs, 1)}
                  tone="red"
                  caption="Execution terminated before a usable result"
                />
              </div>

              <div className="rounded-xl border border-[#2A2A3E] bg-[#0F0F1A] p-5">
                <div className="mb-4 text-xs font-medium uppercase tracking-[0.18em] text-gray-500">
                  Outcome Summary
                </div>
                <div className="space-y-4">
                  <MiniMetric label="Completed" value={completedCount} tone="green" />
                  <MiniMetric label="Active" value={activeCount} tone="blue" />
                  <MiniMetric label="Review queue" value={openReviewCount} tone="amber" />
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="grid gap-6">
          <div className="card p-6">
            <div className="mb-5 flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-white">Recent Activity</h3>
                <p className="mt-1 text-sm text-gray-400">Latest movement across your workspace</p>
              </div>
            </div>

            {jobsLoading ? (
              <ActivitySkeleton />
            ) : jobsError ? (
              <InlineError message="Failed to load recent activity." onAction={() => refetchSummary()} />
            ) : recentJobs.length === 0 ? (
              <EmptyHint
                icon={<Workflow className="h-10 w-10 opacity-30" />}
                message="No jobs yet. Start with a document upload."
                actionLabel="Upload document"
                actionTo="/upload"
              />
            ) : (
              <div className="space-y-3">
                {recentJobs.map((job, index) => (
                  <Link
                    key={job.job_id}
                    to={`/jobs/${job.job_id}`}
                    className="group flex items-start gap-4 rounded-xl border border-[#2A2A3E] bg-[#0F0F1A] px-4 py-4 transition-colors hover:border-[#4F46E5]/35 hover:bg-[#141428]"
                  >
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-[#353553] bg-[#17172A] text-xs font-semibold text-[#A5B4FC]">
                      {index + 1}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <div
                          title={job.file_name ?? undefined}
                          className="truncate text-sm font-medium text-white"
                        >
                          {job.file_name ?? `Job ${job.job_id.slice(0, 8)}`}
                        </div>
                        <StatusPill status={job.status} />
                      </div>
                      <div className="mt-1 text-xs text-gray-400">
                        {(job.doc_type ?? 'Unknown type')} · {formatDate(job.submitted_at)}
                      </div>
                      <div className="mt-2 text-xs uppercase tracking-[0.16em] text-gray-500">
                        Job ID · {job.job_id.slice(0, 8)}
                      </div>
                    </div>
                    <ArrowRight className="mt-1 h-4 w-4 shrink-0 text-gray-500 transition-transform group-hover:translate-x-0.5" />
                  </Link>
                ))}
              </div>
            )}
          </div>

          <div className="card p-6">
            <div className="mb-5 flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-white">Review Spotlight</h3>
                <p className="mt-1 text-sm text-gray-400">Cases most likely to need human attention</p>
              </div>
            </div>

            {reviewsLoading ? (
              <MetricGridSkeleton compact />
            ) : reviewsError ? (
              <InlineError message="Failed to load review summary." onAction={() => refetchSummary()} />
            ) : (
              <>
                <div className="mb-4 rounded-xl border border-[#3F3223] bg-[linear-gradient(180deg,rgba(54,37,18,0.42),rgba(23,18,13,0.92))] p-4">
                  <div className="mb-2 text-xs uppercase tracking-[0.18em] text-amber-300/80">Open cases</div>
                  <div className="text-3xl font-semibold text-amber-300">{openReviewCount}</div>
                  <div className="mt-1 text-sm text-amber-100/80">
                    {commonReviewDocType ? `Most common: ${commonReviewDocType}` : 'No pending review pressure'}
                  </div>
                </div>

                <div className="mb-4 space-y-3">
                  {reviewSpotlight.map((review) => (
                    <Link
                      key={review.id}
                      to={`/reviews/${review.id}`}
                      className="block rounded-lg border border-[#2A2A3E] bg-[#0F0F1A] px-4 py-3 transition-colors hover:border-[#4F46E5]/30"
                    >
                      <div className="truncate text-sm font-medium text-white">
                        {review.file_name ?? 'Review case'}
                      </div>
                      <div className="mt-1 text-xs text-gray-400">
                        {(review.doc_type ?? 'Unknown type')} · {review.open_field_count ?? 0} open fields
                      </div>
                    </Link>
                  ))}
                </div>

                <Link to="/reviews" className="btn-secondary inline-flex w-full items-center justify-center gap-2 text-center">
                  Open Review Queue
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  sub,
  accent,
  pulse = false,
  loading = false,
}: {
  label: string;
  value: string;
  sub: string;
  accent: 'brand' | 'green' | 'amber' | 'red';
  pulse?: boolean;
  loading?: boolean;
}) {
  const accentClasses: Record<string, string> = {
    brand: 'text-[#4F46E5]',
    green: 'text-green-400',
    amber: 'text-amber-400',
    red: 'text-red-400',
  };
  const borderHover: Record<string, string> = {
    brand: 'hover:border-[#4F46E5]/30',
    green: 'hover:border-green-500/30',
    amber: 'hover:border-amber-500/30',
    red: 'hover:border-red-500/30',
  };

  return (
    <div className={`card p-6 transition-colors ${borderHover[accent]}`}>
      <div className="mb-2 flex items-center gap-2 text-sm text-gray-400">
        {label}
        {pulse && <span className="h-2 w-2 rounded-full bg-green-400 animate-pulse" />}
      </div>
      {loading ? (
        <>
          <div className="mb-1 h-9 w-16 animate-pulse rounded-lg bg-[#2A2A3E]" />
          <div className="h-3 w-24 animate-pulse rounded bg-[#2A2A3E]" />
        </>
      ) : (
        <>
          <div className={`mb-1 text-3xl font-semibold ${accentClasses[accent]}`}>{value}</div>
          <div className="text-xs text-gray-500">{sub}</div>
        </>
      )}
    </div>
  );
}

function HeroBadge({
  icon,
  label,
  value,
  tone,
}: {
  icon: ReactNode;
  label: string;
  value: string | number;
  tone: 'green' | 'amber' | 'red' | 'blue' | 'slate';
}) {
  const toneClass: Record<string, string> = {
    green: 'border-green-500/20 bg-green-500/10 text-green-300',
    amber: 'border-amber-500/20 bg-amber-500/10 text-amber-300',
    red: 'border-red-500/20 bg-red-500/10 text-red-300',
    blue: 'border-blue-500/20 bg-blue-500/10 text-blue-300',
    slate: 'border-[#3A3A4E] bg-[#1A1A2E] text-gray-300',
  };

  return (
    <div className={`rounded-full border px-3 py-2 ${toneClass[tone]}`}>
      <div className="flex items-center gap-2 text-xs">
        {icon}
        <span className="font-medium uppercase tracking-[0.16em]">{label}</span>
      </div>
      <div className="mt-1 text-sm font-semibold">{value}</div>
    </div>
  );
}

function FocusCard({
  title,
  value,
  description,
  tone,
  icon,
}: {
  title: string;
  value: string;
  description: string;
  tone: 'brand' | 'green' | 'amber' | 'orange';
  icon: ReactNode;
}) {
  const toneClass: Record<string, string> = {
    brand: 'border-[#4F46E5]/30 bg-[#191935] text-[#C7D2FE]',
    green: 'border-green-500/20 bg-green-500/10 text-green-300',
    amber: 'border-amber-500/20 bg-amber-500/10 text-amber-300',
    orange: 'border-orange-500/20 bg-orange-500/10 text-orange-300',
  };

  return (
    <div className={`rounded-xl border p-4 ${toneClass[tone]}`}>
      <div className="mb-3 flex items-center justify-between text-xs uppercase tracking-[0.16em]">
        <span>{title}</span>
        {icon}
      </div>
      <div className="text-2xl font-semibold text-white">{value}</div>
      <div className="mt-2 text-xs leading-5 text-gray-300">{description}</div>
    </div>
  );
}

function SignalRow({
  label,
  value,
  subtext,
  tone,
}: {
  label: string;
  value: string;
  subtext: string;
  tone: 'green' | 'amber' | 'red' | 'blue' | 'slate';
}) {
  const dotClass: Record<string, string> = {
    green: 'bg-green-400',
    amber: 'bg-amber-400',
    red: 'bg-red-400',
    blue: 'bg-blue-400',
    slate: 'bg-gray-400',
  };

  return (
    <div className="rounded-xl border border-[#2A2A3E] bg-[#0F0F1A] px-4 py-4">
      <div className="mb-1 flex items-center justify-between gap-4">
        <div className="flex items-center gap-2 text-sm font-medium text-white">
          <span className={`h-2.5 w-2.5 rounded-full ${dotClass[tone]}`} />
          {label}
        </div>
        <span className="text-sm font-semibold text-white">{value}</span>
      </div>
      <div className="text-xs leading-5 text-gray-400">{subtext}</div>
    </div>
  );
}

function WorkflowLane({
  label,
  value,
  max,
  tone,
  caption,
}: {
  label: string;
  value: number;
  max: number;
  tone: 'slate' | 'blue' | 'green' | 'amber' | 'orange' | 'red';
  caption: string;
}) {
  const barClass: Record<string, string> = {
    slate: 'bg-gray-400/80',
    blue: 'bg-blue-400/90',
    green: 'bg-green-400/90',
    amber: 'bg-amber-400/90',
    orange: 'bg-orange-400/90',
    red: 'bg-red-400/90',
  };

  const percentage = max <= 0 ? 0 : Math.min((value / max) * 100, 100);

  return (
    <div className="rounded-xl border border-[#2A2A3E] bg-[#0F0F1A] p-4">
      <div className="mb-2 flex items-center justify-between gap-4">
        <div>
          <div className="text-sm font-medium text-white">{label}</div>
          <div className="text-xs text-gray-400">{caption}</div>
        </div>
        <div className="text-lg font-semibold text-white">{value}</div>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-[#1A1A2E]">
        <div
          className={`h-full rounded-full transition-[width] duration-700 ease-out ${barClass[tone]}`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}

function MiniMetric({
  label,
  value,
  tone,
}: {
  label: string;
  value: string | number;
  tone: 'brand' | 'green' | 'amber' | 'orange' | 'blue' | 'red' | 'slate';
}) {
  const tones: Record<string, string> = {
    brand: 'text-[#4F46E5]',
    green: 'text-green-400',
    amber: 'text-amber-400',
    orange: 'text-orange-400',
    blue: 'text-blue-400',
    red: 'text-red-400',
    slate: 'text-gray-300',
  };

  return (
    <div className="rounded-xl border border-[#2A2A3E] bg-[#131324] p-4">
      <div className="mb-2 text-xs uppercase tracking-[0.16em] text-gray-500">{label}</div>
      <div className={`text-2xl font-semibold ${tones[tone]}`}>{value}</div>
    </div>
  );
}

function ActionLink({
  to,
  icon,
  title,
  description,
}: {
  to: string;
  icon: ReactNode;
  title: string;
  description: string;
}) {
  return (
    <Link
      to={to}
      className="group flex items-start gap-3 rounded-xl border border-[#2A2A3E] bg-[#0F0F1A] px-4 py-4 transition-colors hover:border-[#4F46E5]/30 hover:bg-[#141428]"
    >
      <div className="mt-0.5 text-[#4F46E5]">{icon}</div>
      <div className="min-w-0 flex-1">
        <div className="text-sm font-medium text-white">{title}</div>
        <div className="mt-1 text-xs leading-5 text-gray-400">{description}</div>
      </div>
      <ArrowRight className="mt-1 h-4 w-4 shrink-0 text-gray-500 transition-transform group-hover:translate-x-0.5" />
    </Link>
  );
}

function MetricGridSkeleton({ compact = false }: { compact?: boolean }) {
  const count = compact ? 3 : 4;
  return (
    <div className="grid grid-cols-2 gap-4">
      {Array.from({ length: count }).map((_, index) => (
        <div key={index} className="h-24 animate-pulse rounded-lg bg-[#1A1A2E]" />
      ))}
    </div>
  );
}

function ActivitySkeleton() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 4 }).map((_, index) => (
        <div key={index} className="h-24 animate-pulse rounded-lg bg-[#1A1A2E]" />
      ))}
    </div>
  );
}

function InlineError({
  message,
  onAction,
  compact = false,
}: {
  message: string;
  onAction: () => void;
  compact?: boolean;
}) {
  return (
    <div className={`rounded-xl border border-[#2A2A3E] bg-[#0F0F1A] text-center ${compact ? 'px-4 py-6' : 'px-6 py-10'}`}>
      <div className="flex flex-col items-center gap-3 text-gray-500">
        <XCircle className="h-10 w-10 opacity-30" />
        <p className="text-sm">{message}</p>
        <button onClick={onAction} className="btn-secondary text-sm">
          Retry
        </button>
      </div>
    </div>
  );
}

function EmptyHint({
  icon,
  message,
  actionLabel,
  actionTo,
}: {
  icon: ReactNode;
  message: string;
  actionLabel: string;
  actionTo: string;
}) {
  return (
    <div className="rounded-xl border border-[#2A2A3E] bg-[#0F0F1A] px-6 py-12 text-center">
      <div className="flex flex-col items-center gap-3 text-gray-500">
        {icon}
        <p className="text-sm">{message}</p>
        <Link to={actionTo} className="btn-primary text-sm">
          {actionLabel}
        </Link>
      </div>
    </div>
  );
}

function capitalize(value: string): string {
  if (!value) {
    return value;
  }
  return value.charAt(0).toUpperCase() + value.slice(1);
}
