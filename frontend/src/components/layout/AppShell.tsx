import { Outlet, useLocation } from 'react-router-dom';
import { Sidebar } from '@/components/layout/Sidebar';

export function AppShell() {
  const location = useLocation();

  return (
    <div className="flex h-screen bg-[#0F0F1A] overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <div key={location.pathname} className="page-transition">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
