const STATUS_STYLES: Record<string, string> = {
  draft: 'bg-gray-500/10 text-gray-400 ring-gray-500/20',
  published: 'bg-emerald-500/10 text-emerald-400 ring-emerald-500/20',
  archived: 'bg-amber-500/10 text-amber-400 ring-amber-500/20',
  pending: 'bg-gray-500/10 text-gray-400 ring-gray-500/20',
  queued: 'bg-gray-500/10 text-gray-400 ring-gray-500/20',
  running: 'bg-blue-500/10 text-blue-400 ring-blue-500/20',
  completed: 'bg-emerald-500/10 text-emerald-400 ring-emerald-500/20',
  failed: 'bg-red-500/10 text-red-400 ring-red-500/20',
  cancelled: 'bg-amber-500/10 text-amber-400 ring-amber-500/20',
};

export function StatusBadge({ status }: { status: string }) {
  const style = STATUS_STYLES[status] || STATUS_STYLES.draft;
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ring-1 ring-inset ${style}`}
    >
      {status}
    </span>
  );
}
