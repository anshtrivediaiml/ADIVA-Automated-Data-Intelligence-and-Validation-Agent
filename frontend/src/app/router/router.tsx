import { lazy, Suspense } from 'react';
import { createBrowserRouter } from 'react-router-dom';
import { ProtectedRoute } from '@/app/router/ProtectedRoute';
import { RouteErrorPage } from '@/app/router/RouteErrorPage';
import { AppShell } from '@/components/layout/AppShell';
import LoginPage from '@/features/auth/LoginPage';

// Route-level code splitting — each page gets its own JS chunk
const DashboardLandingPage = lazy(() => import('@/features/dashboard/DashboardLandingPage'));
const JobsPage = lazy(() => import('@/features/jobs/JobsPage'));
const JobDetailPage = lazy(() => import('@/features/jobs/JobDetailPage'));
const ResultPage = lazy(() => import('@/features/results/ResultPage'));
const SingleUploadPage = lazy(() => import('@/features/upload/SingleUploadPage'));
const BatchUploadPage = lazy(() => import('@/features/upload/BatchUploadPage'));
const ReviewQueuePage = lazy(() => import('@/features/reviews/ReviewQueuePage'));
const ReviewCasePage = lazy(() => import('@/features/reviews/ReviewCasePage'));

/** Minimal loading shell shown while a lazy route chunk downloads */
function PageLoader() {
  return (
    <div className="flex h-screen items-center justify-center bg-[#0F0F1A]">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-[#4F46E5] border-t-transparent" />
    </div>
  );
}

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage />, errorElement: <RouteErrorPage /> },

  {
    element: <ProtectedRoute />,
    errorElement: <RouteErrorPage />,
    children: [
      {
        element: <AppShell />,
        errorElement: <RouteErrorPage />,
        children: [
          {
            element: <Suspense fallback={<PageLoader />}><DashboardLandingPage /></Suspense>,
            path: '/',
          },
          {
            element: <Suspense fallback={<PageLoader />}><DashboardLandingPage /></Suspense>,
            path: '/dashboard',
          },
          {
            element: <Suspense fallback={<PageLoader />}><JobsPage /></Suspense>,
            path: '/jobs',
          },
          {
            element: <Suspense fallback={<PageLoader />}><JobDetailPage /></Suspense>,
            path: '/jobs/:id',
          },
          {
            element: <Suspense fallback={<PageLoader />}><ResultPage /></Suspense>,
            path: '/jobs/:id/result',
          },
          {
            element: <Suspense fallback={<PageLoader />}><SingleUploadPage /></Suspense>,
            path: '/upload',
          },
          {
            element: <Suspense fallback={<PageLoader />}><BatchUploadPage /></Suspense>,
            path: '/batch',
          },
          {
            element: <Suspense fallback={<PageLoader />}><ReviewQueuePage /></Suspense>,
            path: '/reviews',
          },
          {
            element: <Suspense fallback={<PageLoader />}><ReviewCasePage /></Suspense>,
            path: '/reviews/:id',
          },
        ],
      },
    ],
  },
]);
