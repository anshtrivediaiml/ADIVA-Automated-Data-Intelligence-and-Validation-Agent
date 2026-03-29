import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { ClipboardList, ArrowRight, Filter, Search, Clock3, Sparkles, CheckCircle2 } from 'lucide-react';
import { reviewsApi } from '@/lib/api/reviewsApi';
import { Pagination } from '@/components/ui/Pagination';
import { clampPage, formatDate, paginateItems } from '@/lib/utils';

const PAGE_SIZE = 15;

export default function ReviewQueuePage() {
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<'all' | 'open' | 'in_progress' | 'resolved'>('all');
  const [searchTerm, setSearchTerm] = useState('');
  const apiStatusFilter = statusFilter === 'all' ? undefined : statusFilter;
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['reviews', 'queue', apiStatusFilter ?? 'all'],
    queryFn: () => reviewsApi.list({ limit: 100, status: apiStatusFilter }),
    staleTime: 15_000,
    refetchOnWindowFocus: false,
  });

  const reviews = data?.reviews ?? [];
  const filteredReviews = useMemo(() => {
    return reviews.filter((review) => {
      const matchesStatus = statusFilter === 'all' ? true : review.status === statusFilter;
      const needle = searchTerm.trim().toLowerCase();
      const haystack = [review.file_name ?? '', review.doc_type ?? '', review.id, review.job_id]
        .join(' ')
        .toLowerCase();
      const matchesSearch = !needle || haystack.includes(needle);
      return matchesStatus && matchesSearch;
    });
  }, [reviews, searchTerm, statusFilter]);
  const paginatedReviews = paginateItems(filteredReviews, page, PAGE_SIZE);
  const openCount = reviews.filter((review) => review.status === 'open').length;
  const inProgressCount = reviews.filter((review) => review.status === 'in_progress').length;
  const resolvedCount = reviews.filter((review) => review.status === 'resolved').length;
  const totalOpenFields = reviews.reduce((sum, review) => sum + (review.open_field_count ?? 0), 0);

  useEffect(() => {
    setPage((currentPage) => clampPage(currentPage, filteredReviews.length, PAGE_SIZE));
  }, [filteredReviews.length]);

  return (
    <div className="p-8">
      <div className="mb-8">
        <h2 className="text-2xl font-semibold text-white mb-1">Review Queue</h2>
        <p className="text-gray-400 text-sm">Documents requiring human field correction</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <SummaryCard
          icon={<ClipboardList className="w-4 h-4" />}
          title="Open Cases"
          value={`${openCount}`}
          hint="Cases waiting for a reviewer decision."
          tone="amber"
          active={statusFilter === 'open'}
          onClick={() => setStatusFilter((current) => (current === 'open' ? 'all' : 'open'))}
        />
        <SummaryCard
          icon={<Clock3 className="w-4 h-4" />}
          title="In Progress"
          value={`${inProgressCount}`}
          hint="Cases partially reviewed but not resolved."
          tone="brand"
          active={statusFilter === 'in_progress'}
          onClick={() => setStatusFilter((current) => (current === 'in_progress' ? 'all' : 'in_progress'))}
        />
        <SummaryCard
          icon={<CheckCircle2 className="w-4 h-4" />}
          title="Resolved"
          value={`${resolvedCount}`}
          hint="Completed review cases."
          tone="green"
          active={statusFilter === 'resolved'}
          onClick={() => setStatusFilter((current) => (current === 'resolved' ? 'all' : 'resolved'))}
        />
        <SummaryCard
          icon={<Sparkles className="w-4 h-4" />}
          title="Open Fields"
          value={`${totalOpenFields}`}
          hint="Outstanding field decisions across the queue."
          tone="slate"
        />
      </div>

      <div className="card">
        {isLoading ? (
          <div className="p-6 space-y-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="h-14 bg-[#0F0F1A] rounded-lg animate-pulse" />
            ))}
          </div>
        ) : isError ? (
          <div className="py-16 text-center text-gray-500 text-sm">
            <p className="mb-3">Failed to load review queue.</p>
            <button onClick={() => refetch()} className="btn-secondary text-sm">
              Retry
            </button>
          </div>
        ) : reviews.length === 0 ? (
          <div className="py-16 text-center flex flex-col items-center gap-3 text-gray-500">
            <ClipboardList className="w-12 h-12 opacity-30" />
            <p className="text-sm font-medium">No pending reviews</p>
            <p className="text-xs">All documents have been reviewed or are processing.</p>
          </div>
        ) : (
          <>
            <div className="p-6 border-b border-[#2A2A3E] bg-[#0F0F1A]/35">
              <div className="flex flex-col lg:flex-row gap-3 lg:items-center lg:justify-between">
                <div className="relative flex-1 max-w-2xl">
                  <Search className="w-4 h-4 text-gray-500 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    value={searchTerm}
                    onChange={(event) => setSearchTerm(event.target.value)}
                    placeholder="Search by file name, case id, job id, or document type..."
                    className="input-base pl-10"
                  />
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <div className="inline-flex items-center gap-2 text-xs uppercase tracking-wider text-gray-500 mr-2">
                    <Filter className="w-3.5 h-3.5" />
                    Queue filter
                  </div>
                  {[
                    { value: 'all', label: 'All' },
                    { value: 'open', label: 'Open' },
                    { value: 'in_progress', label: 'In Progress' },
                    { value: 'resolved', label: 'Resolved' },
                  ].map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => setStatusFilter(option.value as typeof statusFilter)}
                      className={`px-3 py-2 rounded-lg text-sm transition-all ${
                        statusFilter === option.value
                          ? 'bg-[#4F46E5] text-white'
                          : 'bg-[#0F0F1A] text-gray-400 hover:text-white hover:bg-[#1A1A2E]'
                      }`}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-[#2A2A3E] bg-[#0F0F1A]/50">
                    {['Case ID', 'File Name', 'Doc Type', 'Open Fields', 'Status', 'Created', 'Action'].map((h) => (
                      <th key={h} className="text-left px-6 py-4 text-xs font-medium text-gray-400 uppercase tracking-wider">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#2A2A3E]">
                  {paginatedReviews.map((r) => {
                    const openCount = r.open_field_count ?? r.fields?.filter((f) => f.status === 'open').length ?? 0;
                    return (
                      <tr key={r.id} className="hover:bg-[#1F1F2E]/50 transition-colors">
                        <td className="px-6 py-4 text-sm font-mono text-gray-500">{r.id.slice(0, 8)}...</td>
                        <td className="px-6 py-4">
                          <div className="text-sm text-white font-medium max-w-[220px] truncate">{r.file_name ?? '-'}</div>
                          <div className="text-xs text-gray-500 mt-1">Job {r.job_id.slice(0, 8)}...</div>
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-400">{r.doc_type ?? '-'}</td>
                        <td className="px-6 py-4 text-sm">
                          <span className={`font-medium ${openCount > 0 ? 'text-amber-400' : 'text-green-400'}`}>
                            {openCount} open
                          </span>
                        </td>
                        <td className="px-6 py-4 text-sm">
                          <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${
                            r.status === 'resolved'    ? 'bg-green-900/30 text-green-300' :
                            r.status === 'in_progress' ? 'bg-blue-900/30 text-blue-300'  :
                                                         'bg-amber-900/30 text-amber-300'
                          }`}>
                            {r.status === 'in_progress' ? 'In Progress' : r.status.charAt(0).toUpperCase() + r.status.slice(1)}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-400">{formatDate(r.created_at)}</td>
                        <td className="px-6 py-4 text-sm">
                          <Link
                            to={`/reviews/${r.id}`}
                            className="flex items-center gap-1.5 text-[#4F46E5] hover:text-[#4338CA] font-medium text-sm transition-colors"
                          >
                            Review <ArrowRight className="w-3.5 h-3.5" />
                          </Link>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {filteredReviews.length === 0 && (
              <div className="px-6 py-10 text-center text-gray-500 text-sm border-t border-[#2A2A3E]">
                No review cases match the current filters.
              </div>
            )}

            <Pagination page={page} pageSize={PAGE_SIZE} totalItems={filteredReviews.length} onPageChange={setPage} />
          </>
        )}
      </div>
    </div>
  );
}

function SummaryCard({
  icon,
  title,
  value,
  hint,
  tone,
  active = false,
  onClick,
}: {
  icon: ReactNode;
  title: string;
  value: string;
  hint: string;
  tone: 'brand' | 'green' | 'amber' | 'slate';
  active?: boolean;
  onClick?: () => void;
}) {
  const toneClasses: Record<string, string> = {
    brand: 'text-[#A5B4FC]',
    green: 'text-green-300',
    amber: 'text-amber-300',
    slate: 'text-gray-300',
  };

  const Component = onClick ? 'button' : 'div';

  return (
    <Component
      type={onClick ? 'button' : undefined}
      onClick={onClick}
      className={`card p-4 text-left ${onClick ? 'cursor-pointer hover:border-[#4F46E5]/40' : ''} ${
        active ? 'border-[#4F46E5] shadow-[0_0_0_1px_rgba(79,70,229,0.28)]' : ''
      }`}
    >
      <div className="flex items-center gap-2 text-xs uppercase tracking-wider text-gray-500 mb-2">
        <span className={toneClasses[tone]}>{icon}</span>
        {title}
      </div>
      <div className={`text-lg font-semibold mb-1 ${toneClasses[tone]}`}>{value}</div>
      <div className="text-xs text-gray-500 leading-relaxed">{hint}</div>
    </Component>
  );
}
