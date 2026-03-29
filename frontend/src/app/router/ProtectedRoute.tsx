import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '@/lib/auth/AuthContext';

export function ProtectedRoute() {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-[#0F0F1A]">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 rounded-full border-2 border-[#4F46E5] border-t-transparent animate-spin" />
          <span className="text-sm text-gray-400">Loading ADIVA...</span>
        </div>
      </div>
    );
  }

  return isAuthenticated ? <Outlet /> : <Navigate to="/login" replace />;
}
