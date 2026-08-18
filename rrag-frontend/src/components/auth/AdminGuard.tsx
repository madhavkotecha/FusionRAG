import { useAuthStore } from '../../stores/auth.store';

export function AdminGuard({ children }: { children: React.ReactNode }) {
  const user = useAuthStore((s) => s.user);

  if (!user) return null;

  if (user.orgRole !== 'org_admin' && !user.isPlatformAdmin) {
    return (
      <div className="flex flex-col items-center justify-center py-24 animate-fade-in">
        <div className="w-16 h-16 rounded-2xl bg-red-500/10 flex items-center justify-center mb-4">
          <svg className="w-8 h-8 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m0 0v2m0-2h2m-2 0H10m4-6V7a4 4 0 00-8 0v4h8z" />
          </svg>
        </div>
        <h2 className="text-lg font-semibold text-text-primary mb-1">Access Denied</h2>
        <p className="text-sm text-text-muted mb-4">You need organization admin privileges to access this page.</p>
        <a href="/" className="text-sm text-accent-400 hover:text-accent-300">Return to Dashboard</a>
      </div>
    );
  }

  return <>{children}</>;
}
