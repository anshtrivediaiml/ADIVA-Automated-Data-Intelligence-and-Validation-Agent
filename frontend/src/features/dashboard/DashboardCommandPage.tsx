import { useMemo, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  Activity,
  ArrowRight,
  CheckCircle2,
  ClipboardList,
  Clock3,
  Layers3,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Upload,
  XCircle,
} from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { StatePanel } from '@/components/ui/StatePanel';
import { StatusPill } from '@/components/ui/StatusPill';
import { healthApi } from '@/lib/api/healthApi';
import { jobsApi } from '@/lib/api/jobsApi';
import { reviewsApi } from '@/lib/api/reviewsApi';
import { formatDate } from '@/lib/utils';
import type { Job } from '@/types/models';

export default function DashboardCommandPage() {
  const {
    data: jobs = [],
    isLoading: jobsLoading,
    isError: jobsError,
    refetch: refetchJobs,
    isFetching: jobsFetching,
  } = useQuery<Job[]>({
    queryKey: ['jobs'],
    queryFn: () => jobsApi.list({ limit: 200 }),
    staleTime: 15_000,
    refetchOnWindowFocus: false,
  });

  const {
    data: reviewsData,
    isLoading: reviewsLoading,
    isError: reviewsError,
    refetch: refetchReviews,
    isFetching: reviewsFetching,
  } = useQuery({
    queryKey: ['reviews'],
    queryFn: () => reviewsApi.list({ limit: 100 }),
    staleTime: 20_000,
    refetchOnWindowFocus: false,
  });

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: () => healthApi.health(),
    staleTime: 30_000,
  });

  const reviews = reviewsData?.reviews ?? [];
  const today = new Date().toISOString().slice(0, 10);
  const queued = jobs.filter((job) => job.status === 'queued').length;
  const processing = jobs.filter((job) => job.status === 'processing').length;
  const completed = jobs.filter((job) => job.status === 'completed').length;
  const failed = jobs.filter((job) => job.status === 'failed').length;
  const needsReview = jobs.filter((job) => job.status === 'needs_review').length;
  const lowConfidence = jobs.filter((job) => job.status === 'low_confidence').length;
  const active = queued + processing;
  const jobsToday = jobs.filter((job) => (job.submitted_at ?? '').startsWith(today)).length;
  const completedToday = jobs.filter(
    (job) => job.status === 'completed' && (job.finished_at ?? '').startsWith(today),
  ).length;
  const successRate = jobs.length > 0 ? Math.round((completed / jobs.length) * 100) : 0;
  const openReviews = reviews.filter((review) => review.status !== 'resolved');
  const criticalOpenFields = openReviews.reduce(
    (sum, review) => sum + (review.critical_open_field_count ?? 0),
    0,
  );
  const openFieldCount = openReviews.reduce((sum, review) => sum + (review.open_field_count ?? 0), 0);
  const recentJobs = jobs.slice(0, 6);

  const nextPriorityReview = useMemo(() => {
    return [...openReviews].sort((left, right) => {
      const leftScore =
        (left.priority_score ?? 0) + (left.critical_open_field_count ?? 0) * 10 + (left.open_field_count ?? 0);
      const rightScore =
        (right.priority_score ?? 0) + (right.critical_open_field_count ?? 0) * 10 + (right.open_field_count ?? 0);
      return rightScore - leftScore;
    })[0];
  }, [openReviews]);

  const refreshAll = () => {
    refetchJobs();
    refetchReviews();
  };

  return (
    <div className="page-shell">
      <div className="page-container">
        <PageHeader
          eyebrow="Command Center"
          title="Dashboard"
          subtitle="Track workload, quality pressure, and operator attention from one place. Detailed row-level actions stay in the jobs and review workspaces."
          actions={
            <button type="button" onClick={refreshAll} className="btn-secondary flex items-center gap-2">
              <RefreshCw className={`h-4 w-4 ${jobsFetching || reviewsFetching ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          }
          badges={
            <>
              <span className="soft-badge">
                <Activity className="h-3.5 w-3.5 text-[#A5B4FC]" />
                {active} active jobs
              </span>
              <span className="soft-badge">
                <ClipboardList className="h-3.5 w-3.5 text-amber-300" />
                {openReviews.length} review cases
              </span>
              <span className="soft-badge">
                <ShieldCheck className="h-3.5 w-3.5 text-green-300" />
                System {capitalize(health?.status ?? 'unknown')}
              </span>
            </>
          }
        />

        {jobsError && reviewsError ? (
          <StatePanel
            title="Dashboard signal is unavailable"
            message="The overview could not load jobs or reviews. Refresh after the backend stabilizes."
            actionLabel="Retry"
            onAction={refreshAll}
            tone="error"
          />
        ) : (
          <div className="space-y-6">
            <section className="section-frame overflow-hidden p-0">
              <div className="border-b border-[#2A2A3E] bg-[radial-gradient(circle_at_top_left,rgba(79,70,229,0.22),transparent_36%),linear-gradient(180deg,rgba(25,25,44,0.96),rgba(18,18,32,0.94))] px-7 py-7">
                <div className="grid gap-6 lg:grid-cols-[1.5fr_1fr]">
                  <div>
                    <div className="mb-3 flex items-center gap-2 text-sm font-medium text-[#A5B4FC]">
                      <Sparkles className="h-4 w-4" />
                      Live operating picture
                    </div>
                    <h2 className="text-2xl font-semibold text-white">
                      {jobsLoading ? 'Loading workload...' : `${active} jobs are currently in motion`}
                    </h2>
                    <p className="mt-3 max-w-3xl text-sm leading-6 text-gray-300/85">
                      Use this page to decide what needs attention next: active pipeline load, review pressure,
                      failure risk, and the fastest route into the correct workspace.
                    </p>

                    <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                      <MetricCard title="Jobs today" value={String(jobsToday)} note={`${completedToday} completed today`} tone="brand" icon={<Clock3 className="h-4 w-4" />} />
                      <MetricCard title="Needs review" value={String(needsReview)} note={`${openFieldCount} open field decisions`} tone="amber" icon={<ClipboardList className="h-4 w-4" />} />
                      <MetricCard title="Success rate" value={`${successRate}%`} note={`${completed} completed from ${jobs.length} visible jobs`} tone="green" icon={<CheckCircle2 className="h-4 w-4" />} />
                      <MetricCard title="Failures" value={String(failed)} note={`${lowConfidence} low-confidence jobs also need checking`} tone="red" icon={<XCircle className="h-4 w-4" />} />
                    </div>
                  </div>

                  <div className="rounded-2xl border border-[#312F54] bg-[#121224]/75 p-5">
                    <div className="mb-4 flex items-center justify-between">
                      <div>
                        <h3 className="text-base font-semibold text-white">Immediate focus</h3>
                        <p className="mt-1 text-sm text-gray-400">Where operators should look first</p>
                      </div>
                      <Link to="/reviews" className="text-sm text-[#A5B4FC] transition-colors hover:text-white">
                        Open queue
                      </Link>
                    </div>

                    {reviewsLoading ? (
                      <div className="space-y-3">
                        {Array.from({ length: 3 }).map((_, index) => (
                          <div key={index} className="h-16 animate-pulse rounded-xl bg-white/[0.04]" />
                        ))}
                      </div>
                    ) : nextPriorityReview ? (
                      <div className="space-y-4">
                        <div className="rounded-xl border border-amber-500/20 bg-[linear-gradient(180deg,rgba(82,52,13,0.28),rgba(18,18,36,0.96))] p-4">
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <div className="text-xs font-medium uppercase tracking-[0.18em] text-amber-300">
                                Highest review pressure
                              </div>
                              <div className="mt-2 truncate text-sm font-semibold text-white">
                                {nextPriorityReview.file_name ?? nextPriorityReview.id}
                              </div>
                              <div className="mt-1 text-sm text-gray-400">
                                {nextPriorityReview.doc_type ?? 'Unknown document'} · {nextPriorityReview.open_field_count ?? 0} open fields
                              </div>
                            </div>
                            <span className="rounded-full border border-amber-400/20 bg-amber-400/10 px-3 py-1 text-xs font-medium text-amber-200">
                              {capitalize(nextPriorityReview.priority ?? 'normal')}
                            </span>
                          </div>
                          <div className="mt-4 flex flex-wrap items-center gap-2 text-xs text-gray-300">
                            <span className="soft-badge border-amber-500/15 bg-[#1A1320] text-amber-200">
                              {nextPriorityReview.critical_open_field_count ?? 0} critical
                            </span>
                            {nextPriorityReview.next_recommended_field ? (
                              <span className="soft-badge border-white/10 bg-[#141427] text-gray-300">
                                Next: {humanize(nextPriorityReview.next_recommended_field)}
                              </span>
                            ) : null}
                          </div>
                        </div>

                        <div className="grid gap-3 sm:grid-cols-2">
                          <QuickAction to="/upload" title="Upload document" description="Start a single extraction job." icon={<Upload className="h-4 w-4" />} />
                          <QuickAction to="/batch" title="Run batch" description="Queue a group of files together." icon={<Layers3 className="h-4 w-4" />} />
                          <QuickAction to="/jobs" title="Track jobs" description="Open the main operations workspace." icon={<Activity className="h-4 w-4" />} />
                          <QuickAction to="/reviews" title="Resolve reviews" description="Work through flagged fields." icon={<ClipboardList className="h-4 w-4" />} />
                        </div>
                      </div>
                    ) : (
                      <StatePanel
                        title="No open review pressure"
                        message="There are no unresolved review cases in the visible window."
                        tone="success"
                        compact
                      />
                    )}
                  </div>
                </div>
              </div>
            </section>

            <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
              <section className="section-frame">
                <div className="section-frame-header">
                  <div>
                    <h2 className="section-title">Pipeline lanes</h2>
                    <p className="section-subtitle">A quick snapshot of where the visible workload is sitting right now.</p>
                  </div>
                  <Link to="/jobs" className="btn-ghost">
                    Open jobs workspace
                  </Link>
                </div>

                {jobsLoading ? (
                  <DashboardSkeleton rows={4} />
                ) : jobsError ? (
                  <StatePanel
                    title="Jobs overview unavailable"
                    message="The pipeline snapshot could not load. Retry when the jobs API responds again."
                    actionLabel="Retry"
                    onAction={() => refetchJobs()}
                    tone="error"
                    compact
                  />
                ) : (
                  <div className="grid gap-4 md:grid-cols-2">
                    <LaneCard title="Queued" count={queued} description="Jobs waiting to be picked up." tone="slate" />
                    <LaneCard title="Processing" count={processing} description="Jobs actively moving through the pipeline." tone="blue" />
                    <LaneCard title="Completed" count={completed} description="Finished successfully and ready to inspect." tone="green" />
                    <LaneCard title="Attention needed" count={needsReview + lowConfidence + failed} description="Review-required, low-confidence, or failed jobs." tone="amber" />
                  </div>
                )}
              </section>

              <section className="section-frame">
                <div className="section-frame-header">
                  <div>
                    <h2 className="section-title">Review pressure</h2>
                    <p className="section-subtitle">Human-in-the-loop load and the quality friction it creates.</p>
                  </div>
                  <Link to="/reviews" className="btn-ghost">
                    Open reviews
                  </Link>
                </div>

                {reviewsLoading ? (
                  <DashboardSkeleton rows={3} />
                ) : reviewsError ? (
                  <StatePanel
                    title="Review signal unavailable"
                    message="The review queue summary could not load. Retry when the queue API responds again."
                    actionLabel="Retry"
                    onAction={() => refetchReviews()}
                    tone="error"
                    compact
                  />
                ) : (
                  <div className="space-y-4">
                    <SignalRow label="Open cases" value={`${openReviews.length}`} note={openReviews.length > 0 ? 'These cases still need human action.' : 'No pending review cases.'} tone={openReviews.length > 0 ? 'amber' : 'green'} />
                    <SignalRow label="Critical open fields" value={`${criticalOpenFields}`} note="Critical items should be reviewed before lower-priority fields." tone={criticalOpenFields > 0 ? 'red' : 'slate'} />
                    <SignalRow
                      label="Queue health"
                      value={openReviews.length === 0 ? 'Clear' : criticalOpenFields > 0 ? 'Escalated' : 'Manageable'}
                      note="A quick qualitative read of the current manual-review burden."
                      tone={openReviews.length === 0 ? 'green' : criticalOpenFields > 0 ? 'red' : 'amber'}
                    />
                  </div>
                )}
              </section>
            </div>

            <section className="section-frame">
              <div className="section-frame-header">
                <div>
                  <h2 className="section-title">Recent activity</h2>
                  <p className="section-subtitle">The latest jobs, surfaced as activity rather than a second jobs table.</p>
                </div>
                <Link to="/jobs" className="btn-ghost">
                  View all jobs
                </Link>
              </div>

              {jobsLoading ? (
                <DashboardSkeleton rows={5} />
              ) : recentJobs.length === 0 ? (
                <StatePanel title="No jobs yet" message="Upload a document to start building your processing activity." actionLabel="Upload document" actionTo="/upload" compact />
              ) : (
                <div className="space-y-3">
                  {recentJobs.map((job) => (
                    <div key={job.job_id} className="flex flex-col gap-4 rounded-2xl border border-[#2A2A3E] bg-[#121224]/70 p-4 md:flex-row md:items-center md:justify-between">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <div className="truncate text-sm font-semibold text-white">
                            {job.file_name ?? `Job ${job.job_id.slice(0, 8)}`}
                          </div>
                          <StatusPill status={job.status} />
                        </div>
                        <div className="mt-2 flex flex-wrap items-center gap-3 text-sm text-gray-400">
                          <span>{job.doc_type ?? 'Unknown document'}</span>
                          <span>{formatDate(job.submitted_at)}</span>
                          {job.review_open_field_count ? (
                            <span className="text-amber-300">
                              {job.review_open_field_count} flagged field{job.review_open_field_count === 1 ? '' : 's'}
                            </span>
                          ) : null}
                        </div>
                      </div>

                      <div className="flex flex-wrap items-center gap-3">
                        <Link to={`/jobs/${job.job_id}`} className="btn-secondary">
                          Track job
                        </Link>
                        {(job.status === 'completed' || job.status === 'needs_review' || job.status === 'low_confidence') && (
                          <Link to={`/jobs/${job.job_id}/result`} className="btn-primary">
                            View result
                          </Link>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>
        )}
      </div>
    </div>
  );
}

function MetricCard({
  title,
  value,
  note,
  tone,
  icon,
}: {
  title: string;
  value: string;
  note: string;
  tone: 'brand' | 'green' | 'amber' | 'red';
  icon: ReactNode;
}) {
  const tones = {
    brand: 'text-[#A5B4FC] border-[#4F46E5]/20 bg-[#111428]',
    green: 'text-green-300 border-green-500/15 bg-[#111D1B]',
    amber: 'text-amber-300 border-amber-500/15 bg-[#1D1711]',
    red: 'text-red-300 border-red-500/15 bg-[#1E1318]',
  };

  return (
    <div className={`rounded-2xl border p-4 ${tones[tone]}`}>
      <div className="mb-3 flex items-center gap-2 text-xs font-medium uppercase tracking-[0.16em] text-gray-400">
        {icon}
        {title}
      </div>
      <div className="text-2xl font-semibold text-white">{value}</div>
      <div className="mt-2 text-sm leading-6 text-gray-400">{note}</div>
    </div>
  );
}

function QuickAction({
  to,
  title,
  description,
  icon,
}: {
  to: string;
  title: string;
  description: string;
  icon: ReactNode;
}) {
  return (
    <Link
      to={to}
      className="group rounded-2xl border border-[#2A2A3E] bg-[#141427]/70 p-4 transition-colors hover:border-[#4F46E5]/35 hover:bg-[#18182D]"
    >
      <div className="mb-3 flex items-center gap-2 text-sm font-medium text-[#A5B4FC]">
        {icon}
        {title}
      </div>
      <div className="text-sm leading-6 text-gray-400">{description}</div>
      <div className="mt-4 flex items-center gap-2 text-sm font-medium text-white">
        Open
        <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
      </div>
    </Link>
  );
}

function LaneCard({
  title,
  count,
  description,
  tone,
}: {
  title: string;
  count: number;
  description: string;
  tone: 'slate' | 'blue' | 'green' | 'amber';
}) {
  const toneClasses = {
    slate: 'border-[#2A2A3E] bg-[#121224] text-gray-300',
    blue: 'border-blue-500/15 bg-[#111A2E] text-blue-300',
    green: 'border-green-500/15 bg-[#111D1B] text-green-300',
    amber: 'border-amber-500/15 bg-[#1D1711] text-amber-300',
  };

  return (
    <div className={`rounded-2xl border p-5 ${toneClasses[tone]}`}>
      <div className="text-xs font-medium uppercase tracking-[0.18em] text-gray-500">{title}</div>
      <div className="mt-3 text-3xl font-semibold text-white">{count}</div>
      <div className="mt-2 text-sm leading-6 text-gray-400">{description}</div>
    </div>
  );
}

function SignalRow({
  label,
  value,
  note,
  tone,
}: {
  label: string;
  value: string;
  note: string;
  tone: 'green' | 'amber' | 'red' | 'slate';
}) {
  const toneClasses = {
    green: 'text-green-300',
    amber: 'text-amber-300',
    red: 'text-red-300',
    slate: 'text-gray-300',
  };

  return (
    <div className="rounded-2xl border border-[#2A2A3E] bg-[#121224]/65 p-4">
      <div className="flex items-center justify-between gap-4">
        <div className="text-sm font-medium text-white">{label}</div>
        <div className={`text-sm font-semibold ${toneClasses[tone]}`}>{value}</div>
      </div>
      <div className="mt-2 text-sm leading-6 text-gray-400">{note}</div>
    </div>
  );
}

function DashboardSkeleton({ rows }: { rows: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="h-20 animate-pulse rounded-2xl bg-white/[0.04]" />
      ))}
    </div>
  );
}

function capitalize(value: string) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function humanize(value: string) {
  return value
    .replace(/_/g, ' ')
    .replace(/\./g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}
