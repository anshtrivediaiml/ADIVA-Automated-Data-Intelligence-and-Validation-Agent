import { useParams, Link, useNavigate, useLocation } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { AlertTriangle, CheckCircle, Loader2, ClipboardCheck, FileWarning, Sparkles } from 'lucide-react';
import { reviewsApi } from '@/lib/api/reviewsApi';
import { DataPreview } from '@/components/ui/DataPreview';
import { DocumentPreviewPane } from '@/features/reviews/DocumentPreviewPane';
import { formatDate } from '@/lib/utils';
import { useToast } from '@/lib/hooks/useToast';
import type { ReviewField } from '@/types/models';

export default function ReviewCasePage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const returnTo = (location.state as { returnTo?: string } | null)?.returnTo ?? '/reviews';
  const qc = useQueryClient();
  const { toast } = useToast();
  const [selectedFieldId, setSelectedFieldId] = useState<string | null>(null);

  const { data: review, isLoading, isError } = useQuery({
    queryKey: ['review', 'detail', id],
    queryFn: () => reviewsApi.get(id!),
    enabled: !!id,
  });

  const {
    data: previewSource,
    isLoading: isPreviewLoading,
    isError: isPreviewError,
    refetch: refetchPreview,
  } = useQuery({
    queryKey: ['review-source', id],
    queryFn: () => reviewsApi.getSource(id!),
    enabled: !!id,
    staleTime: 60_000,
  });

  const correctMutation = useMutation({
    mutationFn: ({ fieldId, value }: { fieldId: string; value: string }) =>
      reviewsApi.correctField(id!, fieldId, value),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['review'] });
      qc.invalidateQueries({ queryKey: ['reviews'] });
      qc.invalidateQueries({ queryKey: ['result'] });
      qc.invalidateQueries({ queryKey: ['jobs'] });
      toast('Field correction saved', 'success');
    },
    onError: () => toast('Failed to save correction', 'error'),
  });

  const acceptAiMutation = useMutation({
    mutationFn: (fieldId: string) => reviewsApi.acceptAiProposal(id!, fieldId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['review'] });
      qc.invalidateQueries({ queryKey: ['reviews'] });
      qc.invalidateQueries({ queryKey: ['result'] });
      qc.invalidateQueries({ queryKey: ['jobs'] });
      toast('AI proposal accepted', 'success');
    },
    onError: () => toast('Failed to accept AI proposal', 'error'),
  });

  const acceptOriginalMutation = useMutation({
    mutationFn: (fieldId: string) => reviewsApi.acceptOriginal(id!, fieldId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['review'] });
      qc.invalidateQueries({ queryKey: ['reviews'] });
      qc.invalidateQueries({ queryKey: ['result'] });
      qc.invalidateQueries({ queryKey: ['jobs'] });
      toast('Original value accepted', 'success');
    },
    onError: () => toast('Failed to accept original value', 'error'),
  });

  const resolveMutation = useMutation({
    mutationFn: () => reviewsApi.resolve(id!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['review'] });
      qc.invalidateQueries({ queryKey: ['reviews'] });
      qc.invalidateQueries({ queryKey: ['result'] });
      qc.invalidateQueries({ queryKey: ['jobs'] });
      toast('Review case resolved', 'success');
      navigate(returnTo, { replace: true });
    },
    onError: () => toast('Failed to resolve case', 'error'),
  });

  const fields = review?.fields ?? [];
  const openFields = fields.filter((f) => f.status === 'open');
  const addressedCount = fields.length - openFields.length;
  const canResolve = review ? review.status !== 'resolved' && openFields.length === 0 : false;
  const aiSuggestionCount = fields.filter((field) => field.proposed_value != null).length;
  const resolvedTone = canResolve ? 'green' : openFields.length > 0 ? 'amber' : 'slate';
  const selectedField = useMemo(
    () => fields.find((field) => field.id === selectedFieldId) ?? null,
    [fields, selectedFieldId],
  );

  useEffect(() => {
    const preferredField = openFields[0] ?? fields[0] ?? null;
    if (!preferredField) {
      if (selectedFieldId !== null) {
        setSelectedFieldId(null);
      }
      return;
    }

    const currentField = fields.find((field) => field.id === selectedFieldId) ?? null;
    const shouldReplaceSelection =
      !currentField || (currentField.status !== 'open' && openFields.length > 0);

    if (shouldReplaceSelection && preferredField.id !== selectedFieldId) {
      setSelectedFieldId(preferredField.id);
    }
  }, [fields, openFields, selectedFieldId]);

  if (isLoading) {
    return (
      <div className="p-8 max-w-7xl mx-auto">
        <div className="card p-8 space-y-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-16 bg-[#0F0F1A] rounded-lg animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (isError || !review) {
    return (
      <div className="p-8 max-w-7xl mx-auto">
        <div className="card p-8 text-center">
          <AlertTriangle className="w-12 h-12 text-red-400 mx-auto mb-3" />
          <p className="text-gray-400 text-sm">Could not load review case.</p>
          <Link to={returnTo} className="btn-primary mt-4 inline-block">Back to Queue</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-7xl mx-auto">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-gray-400 mb-6">
        <Link to={returnTo} className="hover:text-white">Reviews</Link>
        <span>/</span>
        <span className="font-mono text-xs">{id?.slice(0, 8)}...</span>
      </div>

      {/* Header */}
      <div className="card p-6 mb-6">
        <div className="flex items-start justify-between mb-3">
          <div>
            <h2 className="text-xl font-semibold text-white mb-1">{review.file_name ?? 'Review Case'}</h2>
            <div className="flex gap-4 text-sm text-gray-400">
              <span>Doc Type: <span className="text-white">{review.doc_type ?? '-'}</span></span>
              <span>Created: <span className="text-white">{formatDate(review.created_at)}</span></span>
            </div>
          </div>
          <button
            onClick={() => resolveMutation.mutate()}
            disabled={!canResolve || resolveMutation.isPending}
            className={`btn-primary flex items-center gap-2 ${!canResolve ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            {resolveMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />}
            Resolve Case
          </button>
        </div>

        <div className="mt-3">
          <div className="flex items-center justify-between text-xs text-gray-400 mb-1.5">
            <span>{addressedCount} of {review.fields.length} fields addressed</span>
            <span className={openFields.length === 0 ? 'text-green-400' : 'text-amber-400'}>
              {openFields.length} remaining
            </span>
          </div>
          <div className="w-full h-1.5 bg-[#2A2A3E] rounded-full overflow-hidden">
            <div
              className="h-full bg-[#4F46E5] rounded-full transition-all"
              style={{ width: review.fields.length > 0 ? `${(addressedCount / review.fields.length) * 100}%` : '0%' }}
            />
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-5">
          <SummaryCard
            icon={<FileWarning className="w-4 h-4" />}
            title="Open Fields"
            value={`${openFields.length}`}
            hint={openFields.length === 0 ? 'All flagged fields are addressed.' : 'These fields still need a decision before resolution.'}
            tone={resolvedTone}
          />
          <SummaryCard
            icon={<ClipboardCheck className="w-4 h-4" />}
            title="Progress"
            value={`${addressedCount}/${review.fields.length}`}
            hint="Resolved, corrected, or accepted fields count toward completion."
            tone={canResolve ? 'green' : 'brand'}
          />
          <SummaryCard
            icon={<Sparkles className="w-4 h-4" />}
            title="AI Suggestions"
            value={`${aiSuggestionCount}`}
            hint={aiSuggestionCount > 0 ? 'Some fields include an AI proposal you can accept directly.' : 'No AI proposals were returned for these fields.'}
            tone={aiSuggestionCount > 0 ? 'brand' : 'slate'}
          />
        </div>
      </div>

      {/* Fields */}
      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)] gap-6 items-start">
        <DocumentPreviewPane
          source={previewSource}
          isLoading={isPreviewLoading}
          isError={isPreviewError}
          onRetry={() => {
            void refetchPreview();
          }}
        />

        {review.fields.length === 0 ? (
          <div className="card p-8 text-center text-gray-500 text-sm">No fields to review.</div>
        ) : (
          <div className="space-y-4">
            <div className="card p-4 border-[#4F46E5]/30">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="text-xs uppercase tracking-wider text-gray-500 mb-1">Currently reviewing</div>
                  <div className="text-base font-semibold text-white">
                    {selectedField?.field_path ?? 'Select a flagged field'}
                  </div>
                  <div className="text-sm text-gray-400 mt-1">
                    {selectedField
                      ? selectedField.validation_message
                      : 'Choose a field on the right to inspect its extracted value and decide the correction.'}
                  </div>
                </div>
                <div className="text-right text-sm text-gray-400">
                  <div>{openFields.length} open</div>
                  <div>{addressedCount} addressed</div>
                </div>
              </div>
            </div>

            {review.fields.map((field) => (
              <FieldCard
                key={field.id}
                field={field}
                selected={field.id === selectedFieldId}
                onSelect={() => setSelectedFieldId(field.id)}
                onCorrect={(value) => correctMutation.mutate({ fieldId: field.id, value })}
                onAcceptAi={() => acceptAiMutation.mutate(field.id)}
                onAcceptOriginal={() => acceptOriginalMutation.mutate(field.id)}
                isPending={correctMutation.isPending || acceptAiMutation.isPending || acceptOriginalMutation.isPending}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── FieldCard ────────────────────────────────────────────────────────────────

function FieldCard({
  field,
  selected,
  onSelect,
  onCorrect,
  onAcceptAi,
  onAcceptOriginal,
  isPending,
}: {
  field: ReviewField;
  selected: boolean;
  onSelect: () => void;
  onCorrect: (value: string) => void;
  onAcceptAi: () => void;
  onAcceptOriginal: () => void;
  isPending: boolean;
}) {
  const [correction, setCorrection] = useState('');
  const isAddressed = field.status !== 'open';
  const cardRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (!selected) {
      return;
    }

    cardRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

    if (!isAddressed) {
      const focusTimer = window.setTimeout(() => {
        inputRef.current?.focus();
      }, 120);

      return () => window.clearTimeout(focusTimer);
    }
  }, [selected, isAddressed]);

  return (
    <div
      ref={cardRef}
      onClick={onSelect}
      className={`card p-5 transition-all cursor-pointer ${
        selected
          ? 'border-[#4F46E5] shadow-[0_0_0_1px_rgba(79,70,229,0.35),0_20px_40px_rgba(10,10,20,0.28)]'
          : ''
      } ${isAddressed ? 'opacity-60' : ''}`}
    >
      <div className="flex items-center gap-3 mb-3">
        <span className="font-mono text-sm text-[#4F46E5] font-medium">{field.field_path}</span>
        <span className="px-2 py-0.5 rounded text-xs bg-amber-900/30 text-amber-300">{field.reason_code}</span>
        {selected && !isAddressed && (
          <span className="px-2 py-0.5 rounded text-xs bg-[#4F46E5]/20 text-[#C7D2FE]">
            Currently reviewing
          </span>
        )}
        {isAddressed && (
          <span className="px-2 py-0.5 rounded text-xs bg-green-900/30 text-green-300 ml-auto">
            {field.status.charAt(0).toUpperCase() + field.status.slice(1)}
          </span>
        )}
      </div>

      <p className="text-xs text-gray-400 mb-4">{field.validation_message}</p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        <div className="bg-[#0F0F1A] rounded-lg p-3">
          <p className="text-xs text-gray-500 mb-1">Extracted Value</p>
          <DataPreview value={field.original_value} compact emptyLabel="No extracted value" />
        </div>
        <div className="bg-[#0F0F1A] rounded-lg p-3">
          <p className="text-xs text-gray-500 mb-1">AI Proposed Value</p>
          <DataPreview value={field.proposed_value} compact emptyLabel="No AI proposal" />
        </div>
      </div>

      {field.corrected_value != null && (
        <div className="mb-4 rounded-lg border border-[#2A2A3E] bg-[#0F0F1A] p-3">
          <p className="text-xs text-gray-500 mb-1">Final / Corrected Value</p>
          <DataPreview value={field.corrected_value} compact emptyLabel="No final value" />
        </div>
      )}

      {!isAddressed && (
        <div className="space-y-3">
          <input
            ref={inputRef}
            type="text"
            value={correction}
            onChange={(e) => setCorrection(e.target.value)}
            placeholder="Enter corrected value..."
            className="input-base w-full"
            onClick={(event) => event.stopPropagation()}
          />
          <div className="flex flex-wrap gap-2">
            <button
              onClick={(event) => {
                event.stopPropagation();
                if (correction.trim()) onCorrect(correction.trim());
              }}
              disabled={!correction.trim() || isPending}
              className="btn-primary px-4 flex items-center gap-1.5"
            >
              {isPending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null}
              Correct
            </button>
            {field.proposed_value != null && (
              <button
                onClick={(event) => {
                  event.stopPropagation();
                  onAcceptAi();
                }}
                disabled={isPending}
                className="btn-secondary px-4 text-sm"
              >
                Accept AI
              </button>
            )}
            <button
              onClick={(event) => {
                event.stopPropagation();
                onAcceptOriginal();
              }}
              disabled={isPending}
              className="btn-secondary px-4 text-sm"
            >
              Keep Original
            </button>
          </div>
        </div>
      )}
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
  tone: 'brand' | 'green' | 'amber' | 'slate';
}) {
  const toneClasses: Record<string, string> = {
    brand: 'text-[#A5B4FC]',
    green: 'text-green-300',
    amber: 'text-amber-300',
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
