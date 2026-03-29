import { Link, useLocation, useNavigate } from 'react-router-dom';
import { LayoutDashboard, Upload, Layers, Briefcase, ClipboardList, LogOut } from 'lucide-react';
import { useAuth } from '@/lib/auth/AuthContext';

const navItems = [
  { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/upload',    label: 'Upload',    icon: Upload },
  { path: '/batch',     label: 'Batch',     icon: Layers },
  { path: '/jobs',      label: 'Jobs',      icon: Briefcase },
  { path: '/reviews',   label: 'Reviews',   icon: ClipboardList },
];

export function Sidebar() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  function handleLogout() {
    logout();
    navigate('/login', { replace: true });
  }

  return (
    <div className="w-64 bg-[rgba(15,15,26,0.92)] border-r border-[rgba(62,62,92,0.72)] backdrop-blur-md h-screen flex flex-col flex-shrink-0">
      {/* Logo */}
      <div className="relative p-6 border-b border-[#2A2A3E] overflow-hidden">
        {/* Brand accent line */}
        <div className="absolute inset-y-0 left-0 w-0.5 bg-gradient-to-b from-[#4F46E5] via-[#818CF8]/50 to-transparent" />
        <h1 className="text-2xl font-semibold text-white tracking-tight">ADIVA</h1>
        <p className="text-xs text-gray-500 mt-0.5">Document Intelligence Platform</p>
      </div>

      {/* Nav */}
      <nav className="flex-1 p-4 overflow-y-auto">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive =
            location.pathname === item.path ||
            (item.path !== '/dashboard' && location.pathname.startsWith(item.path));

          return (
            <Link
              key={item.path}
              to={item.path}
              className={`relative flex items-center gap-3 pl-[14px] pr-4 py-3 rounded-lg mb-1 border-l-2 transition-all duration-200 ${
                isActive
                  ? 'border-[#4F46E5] bg-[#4F46E5]/12 text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]'
                  : 'border-transparent text-gray-400 hover:text-white hover:bg-white/[0.04]'
              }`}
            >
              <Icon className={`w-5 h-5 flex-shrink-0 transition-colors ${isActive ? 'text-[#A5B4FC]' : ''}`} />
              <span className="font-medium text-sm">{item.label}</span>
            </Link>
          );
        })}
      </nav>

      {/* User section */}
      {user && (
        <div className="p-4 border-t border-[#2A2A3E]">
          <div className="flex items-center gap-3 mb-3 px-2">
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[#4F46E5]/40 to-[#4F46E5]/10 border border-[#4F46E5]/30 flex items-center justify-center flex-shrink-0">
              <span className="text-xs font-semibold text-[#A5B4FC]">
                {user.name?.charAt(0)?.toUpperCase() ?? 'U'}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-white truncate">{user.name}</p>
              <p className="text-xs text-gray-500 truncate capitalize">{user.role}</p>
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="flex items-center gap-2 w-full px-3 py-2 rounded-lg text-gray-400 hover:bg-[#1A1A2E] hover:text-white transition-all duration-200 text-sm group"
          >
            <LogOut className="w-4 h-4 group-hover:translate-x-0.5 transition-transform duration-200" />
            <span>Sign out</span>
          </button>
        </div>
      )}
    </div>
  );
}
