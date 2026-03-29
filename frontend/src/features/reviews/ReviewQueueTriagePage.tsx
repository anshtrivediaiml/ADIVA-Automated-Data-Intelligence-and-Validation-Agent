import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  AlertTriangle,
  ArrowRight,
  ClipboardList,
  Filter,
  RefreshCw,
  Search,
  ShieldAlert,
  Sparkles,
} from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { StatePanel } from '@/components/ui/StatePanel';
import { Pagination } from '@/components/ui/Pagination';
import { reviewsApi } from '@/lib/api/reviewsApi';
import { clampPage, formatDate, paginateItems } from '@/lib/utils';
import type { ReviewCase } from '@/types/models';

const PAGE_SIZE = 15;

export default function ReviewQueueTriagePage() {
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<'all' | 'open' | 'in_progress' | 'resolved'>('all');
  const [searchTerm, setSearchTerm] = useState('');

  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ['reviews'],
    queryFn: () => reviewsApi.list({ limit: 100 }),
    staleTime: 20_000,
    refetchOnWindowFocus: false,
  });

  const reviews = data?.reviews ?? [];
  const sortedAndFilteredReviews = useMemo(() => {
    const needle = searchTerm.trim().toLowerCase();
    return [...reviews]
      .filter((review) => {
        const matchesStatus = statusFilter === 'all' ? true : review.status === statusFilter;
        const haystack = [
          review.file_name ?? '',
          review.doc_type ?? '',
          review.id,
          review.job_id,
          ...(review.reason_codes ?? []),
        ]
          .join(' ')
          .toLowerCase();
        return matchesStatus && (!needle || haystack.includes(needle));
      })
      .sort((left, right) => reviewRank(right) - reviewRank(left));
  }, [reviews, searchTerm, statusFilter]);

  useEffect(() => {
    setPage((currentPage) => clampPage(currentPage, sortedAndFilteredReviews.length, PAGE_SIZE));
  }, [sortedAndFilteredReviews.length]);

  const paginatedReviews = paginateItems(sortedAndFilteredReviews, page, PAGE_SIZE);
  const openCount = reviews.filter((review) => review.status === 'open').length;
  const inProgressCount = reviews.filter((review) => review.status === 'in_progress').length;
  const resolvedCount = reviews.filter((review) => review.status === 'resolved').length;
  const criticalCount = reviews.reduce(
    (sum, review) => sum + (review.critical_open_field_count ?? 0),
    0,
  );
  const nextReview = sortedAndFilteredReviews.find((review) => review.status !== 'resolved');

  return (
    <div className="page-shell">
      <div className="page-container">
        <PageHeader
          eyebrow="Human Review"
          title="Review Queue"
          subtitle="Prioritize the cases that matter first. This page is for triage, urgency, and getting the right case open quickly."
          actions={
            <button type="button" onClick={() => refetch()} className="btn-secondary flex items-center gap-2">
              <RefreshCw className={`h-4 w-4 ${isFetching ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          }
          badges={
            <>
              <span className="soft-badge">
                <ClipboardList className="h-3.5 w-3.5 text-amber-300" />
                {openCount} open
              </span>
              <span className="soft-badge">
                <ShieldAlert className="h-3.5 w-3.5 text-red-300" />
                {criticalCount} critical fields
              </span>
              <span className="soft-badge">
                <Sparkles className="h-3.5 w-3.5 text-[#A5B4FC]" />
                {reviews.length} visible cases
              </span>
            </>
          }
        />

        <div className="space-y-6">
          <section className="section-frame">
            <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
              <div className="rounded-2xl border border-amber-500/15 bg-[radial-gradient(circle_at_top_left,rgba(245,158,11,0.16),transparent_32%),linear-gradient(180deg,rgba(34,24,14,0.96),rgba(17,17,28,0.94))] p-6">
                <div className="mb-2 text-xs font-medium uppercase tracking-[0.2em] text-amber-300">
                  Review first
                </div>
                {nextReview ? (
                  <>
                    <div className="text-xl font-semibold text-white">
                      {nextReview.file_name ?? nextReview.id}
                    </div>
                    <p className="mt-2 text-sm leading-6 text-gray-300">
                      {nextReview.doc_type ?? 'Unknown document'} with {nextReview.open_field_count ?? 0} open
                      field decisions and {nextReview.critical_open_field_count ?? 0} critical flags.
                    </p>
                    <div className="mt-4 flex flex-wrap gap-2 text-xs">
                      <span className="soft-badge border-amber-500/15 bg-[#1A1320] text-amber-200">
                        Priority {capitalize(nextReview.priority ?? 'normal')}
                      </span>
                      {nextReview.next_recommended_field ? (
                        <span className="soft-badge border-white/10 bg-[#141427] text-gray-300">
                          Next field: {humanize(nextReview.next_recommended_field)}
                        </span>
                      ) : null}
                    </div>
                    <div className="mt-5">
                      <Link to={`/reviews/${nextReview.id}`} className="btn-primary inline-flex items-center gap-2">
                        Open case
                        <ArrowRight className="h-4 w-4" />
                      </Link>
                    </div>
                  </>
                ) : (
                  <StatePanel
                    title="Queue is clear"
                    message="There are no unresolved review cases right now."
                    tone="success"
                    compact
                    className="border-0 bg-transparent px-0 py-0 text-left"
                  />
                )}
              </div>

              <div className="grid gap-4 sm:grid-cols-3 lg:grid-cols-1 xl:grid-cols-3">
                <TriageMetric title="Open" value={String(openCount)} note="Waiting for a reviewer." tone="amber" />
                <TriageMetric title="In progress" value={String(inProgressCount)} note="Partially reviewed." tone="brand" />
                <TriageMetric title="Resolved" value={String(resolvedCount)} note="Closed out and completed." tone="green" />
              </div>
            </div>
          </section>

          <section className="section-frame">
            <div className="section-frame-header">
              <div>
                <h2 className="section-title">Triage list</h2>
                <p className="section-subtitle">
                  Sorted so high-pressure, unresolved cases rise above older resolved items.
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {[
                  { label: 'All', value: 'all' },
                  { label: 'Open', value: 'open' },
                  { label: 'In Progress', value: 'in_progress' },
                  { label: 'Resolved', value: 'resolved' },
                ].map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => setStatusFilter(option.value as typeof statusFilter)}
                    className={statusFilter === option.value ? 'btn-primary py-2' : 'btn-secondary py-2'}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="mb-5 grid gap-3 lg:grid-cols-[1fr_auto]">
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-500" />
                <input
                  value={searchTerm}
                  onChange={(event) => setSearchTerm(event.target.value)}
                  className="input-base pl-10"
                  placeholder="Search by file name, job id, case id, document type, or reason code..."
                />
              </div>
              <div className="soft-badge justify-center">
                <Filter className="h-3.5 w-3.5 text-[#A5B4FC]" />
                {sortedAndFilteredReviews.length} matching cases
              </div>
            </div>

            {isLoading ? (
              <div className="space-y-3">
                {Array.from({ length: 5 }).map((_, index) => (
                  <div key={index} className="h-36 animate-pulse rounded-2xl bg-white/[0.04]" />
                ))}
              </div>
            ) : isError ? (
              <StatePanel
                title="Review queue unavailable"
                message="The queue could not be loaded. Retry after the API responds again."
                actionLabel="Retry"
                onAction={() => refetch()}
                tone="error"
              />
            ) : sortedAndFilteredReviews.length === 0 ? (
              <StatePanel
                title="No cases match the current filters"
                message="Adjust the status filter or search term to bring cases back into view."
                icon={<AlertTriangle className="h-8 w-8" />}
                compact
              />
            ) : (
              <>
                <div className="space-y-3">
                  {paginatedReviews.map((review) => (
                    <ReviewCard key={review.id} review={review} />
                  ))}
                </div>
                <Pagination
                  page={page}
                  pageSize={PAGE_SIZE}
                  totalItems={sortedAndFilteredReviews.length}
                  onPageChange={setPage}
                />
              </>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}

function TriageMetric({
  title,
  value,
  note,
  tone,
}: {
  title: string;
  value: string;
  note: string;
  tone: 'brand' | 'green' | 'amber';
}) {
  const tones = {
    brand: 'border-[#4F46E5]/18 bg-[#12152C]',
    green: 'border-green-500/15 bg-[#111D1B]',
    amber: 'border-amber-500/15 bg-[#1D1711]',
  };
  const values = {
    brand: 'text-[#A5B4FC]',
    green: 'text-green-300',
    amber: 'text-amber-300',
  };

  return (
    <div className={`rounded-2xl border p-5 ${tones[tone]}`}>
      <div className="text-xs font-medium uppercase tracking-[0.18em] text-gray-500">{title}</div>
      <div className={`mt-3 text-3xl font-semibold ${values[tone]}`}>{value}</div>
      <div className="mt-2 text-sm leading-6 text-gray-400">{note}</div>
    </div>
  );
}

function ReviewCard({ review }: { review: ReviewCase }) {
  const statusTone =
    review.status === 'resolved'
      ? 'bg-green-900/30 text-green-300'
      : review.status === 'in_progress'
        ? 'bg-blue-900/30 text-blue-300'
        : 'bg-amber-900/30 text-amber-300';

  return (
    <div className="rounded-2xl border border-[#2A2A3E] bg-[#121224]/70 p-5 transition-colors hover:border-[#4F46E5]/30">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <div className="truncate text-base font-semibold text-white">
              {review.file_name ?? review.id}
            </div>
            <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${statusTone}`}>
              {review.status === 'in_progress' ? 'In Progress' : capitalize(review.status)}
            </span>
            {review.priority ? (
              <span className="soft-badge border-white/10 bg-[#141427] text-gray-300">
                Priority {capitalize(review.priority)}
              </span>
            ) : null}
          </div>

          <div className="mt-2 flex flex-wrap items-center gap-3 text-sm text-gray-400">
            <span>{review.doc_type ?? 'Unknown document'}</span>
            <span>Case {review.id.slice(0, 8)}</span>
            <span>Updated {formatDate(review.updated_at ?? review.created_at)}</span>
          </div>

          {(review.reason_codes ?? []).length > 0 ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {(review.reason_codes ?? []).slice(0, 4).map((reason) => (
                <span
                  key={reason}
                  className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs text-gray-300"
                >
                  {humanize(reason)}
                </span>
              ))}
            </div>
          ) : null}

          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <MiniStat label="Open fields" value={String(review.open_field_count ?? 0)} tone={(review.open_field_count ?? 0) > 0 ? 'amber' : 'slate'} />
            <MiniStat label="Critical" value={String(review.critical_open_field_count ?? 0)} tone={(review.critical_open_field_count ?? 0) > 0 ? 'red' : 'slate'} />
            <MiniStat label="Next field" value={review.next_recommended_field ? humanize(review.next_recommended_field) : 'None'} tone="brand" />
          </div>
        </div>

        <div className="flex shrink-0 flex-col items-stretch gap-3 xl:min-w-[220px]">
          <Link to={`/reviews/${review.id}`} className="btn-primary inline-flex items-center justify-center gap-2">
            Review case
            <ArrowRight className="h-4 w-4" />
          </Link>
          <Link to={`/jobs/${review.job_id}`} className="btn-secondary text-center">
            Open job
          </Link>
        </div>
      </div>
    </div>
  );
}

function MiniStat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: 'amber' | 'red' | 'brand' | 'slate';
}) {
  const valueTone = {
    amber: 'text-amber-300',
    red: 'text-red-300',
    brand: 'text-[#A5B4FC]',
    slate: 'text-gray-300',
  };

  return (
    <div className="rounded-xl border border-[#2A2A3E] bg-[#11111F] p-3">
      <div className="text-[11px] uppercase tracking-[0.16em] text-gray-500">{label}</div>
      <div className={`mt-2 text-sm font-medium ${valueTone[tone]}`}>{value}</div>
    </div>
  );
}

function reviewRank(review: ReviewCase) {
  const statusWeight = review.status === 'open' ? 400 : review.status === 'in_progress' ? 250 : 0;
  const priorityWeight =
    review.priority === 'critical' ? 300 : review.priority === 'high' ? 220 : review.priority === 'medium' ? 120 : 40;
  return (
    statusWeight +
    priorityWeight +
    (review.critical_open_field_count ?? 0) * 35 +
    (review.open_field_count ?? 0) * 10 +
    (review.priority_score ?? 0)
  );
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
