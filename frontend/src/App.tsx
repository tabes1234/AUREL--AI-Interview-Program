import { MotionConfig } from 'motion/react'
import { lazy, Suspense, useEffect } from 'react'
import { Route, Routes, useLocation } from 'react-router-dom'
import { AuthProvider } from './context/AuthProvider'
import { RequireAuth } from './context/RequireAuth'
import { RequireAdmin } from './components/admin/RequireAdmin'
import { OnboardingProvider } from './components/onboarding/OnboardingGuide'
import AppLayout from './components/layout/AppLayout'
import { Loader2 } from 'lucide-react'

// 路由级代码分割：每个页面独立分块，首屏只加载当前路由（命名导出的页面在 then 中适配为默认导出）
const AboutPage = lazy(() => import('./pages/AboutPage'))
const AnnouncementsPage = lazy(() => import('./pages/AnnouncementsPage'))
const TechArchivePage = lazy(() => import('./pages/TechArchivePage'))
const AuthPage = lazy(() => import('./pages/AuthPage'))
const CareerGuidePage = lazy(() => import('./pages/CareerGuidePage'))
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const HomePage = lazy(() => import('./pages/HomePage'))
const InterviewNewPage = lazy(() => import('./pages/InterviewNewPage'))
const InterviewPreviewPage = lazy(() => import('./pages/InterviewPreviewPage'))
const InterviewSessionPage = lazy(() => import('./pages/InterviewSessionPage'))
const KnowledgePage = lazy(() => import('./pages/KnowledgePage').then((m) => ({ default: m.KnowledgePage })))
const ExpressionPage = lazy(() => import('./pages/ExpressionPage').then((m) => ({ default: m.ExpressionPage })))
const MatchingPage = lazy(() => import('./pages/MatchingPage').then((m) => ({ default: m.MatchingPage })))
const JobsPage = lazy(() => import('./pages/JobsPage'))
const JobLibraryPage = lazy(() => import('./pages/JobLibraryPage'))
const ResumePage = lazy(() => import('./pages/ResumePage'))
const ResumeGalleryPage = lazy(() => import('./pages/ResumeGalleryPage'))
const MistakesPage = lazy(() => import('./pages/MistakesPage'))
const ChallengesPage = lazy(() => import('./pages/ChallengesPage'))
const ConcertoPage = lazy(() => import('./pages/ConcertoPage'))
const MePage = lazy(() => import('./pages/MePage'))
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'))
const ReportDetailPage = lazy(() => import('./pages/ReportDetailPage'))
const ReportsPage = lazy(() => import('./pages/ReportsPage'))
const SkillsPage = lazy(() => import('./pages/SkillsPage').then((m) => ({ default: m.SkillsPage })))

// 观澜管理中心（独立布局，不进入普通用户导航；服务端校验管理员角色）
const AdminLayout = lazy(() => import('./pages/admin/AdminLayout'))
const AdminOverviewPage = lazy(() => import('./pages/admin/AdminOverviewPage'))
const AdminUsersPage = lazy(() => import('./pages/admin/AdminUsersPage'))
const AdminUserDetailPage = lazy(() => import('./pages/admin/AdminUserDetailPage'))
const AdminModulesPage = lazy(() => import('./pages/admin/AdminModulesPage'))
const AdminAiPage = lazy(() => import('./pages/admin/AdminAiPage'))
const AdminAuditPage = lazy(() => import('./pages/admin/AdminAuditPage'))

/** 分块加载瞬间的品牌化占位：居中轻量旋转，不闪整页白屏 */
function RouteFallback() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center" role="status" aria-label="页面加载中">
      <Loader2 className="h-6 w-6 animate-spin text-brand-500/80" aria-hidden="true" />
    </div>
  )
}

function ScrollToTop() {
  const { pathname } = useLocation()
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pathname])
  return null
}

export default function App() {
  return (
    <MotionConfig reducedMotion="user">
      <AuthProvider>
        <OnboardingProvider>
          <ScrollToTop />
          <Suspense fallback={<RouteFallback />}>
            <Routes>
            {/* 公开页面：首页、观澜之意、澜讯、认证 */}
            <Route path="/" element={<HomePage />} />
            <Route path="/about" element={<AboutPage />} />
            <Route path="/announcements" element={<AnnouncementsPage />} />
            <Route path="/announcements/tech-archive" element={<TechArchivePage />} />
            <Route path="/auth" element={<AuthPage />} />
            {/* 工作台：全部需要登录（未登录访问时跳转 /auth 并记录来路） */}
            <Route
              element={
                <RequireAuth>
                  <AppLayout />
                </RequireAuth>
              }
            >
              <Route path="/app" element={<DashboardPage />} />
              <Route path="/career-guide" element={<CareerGuidePage />} />
              <Route path="/interview/new" element={<InterviewNewPage />} />
              <Route path="/reports" element={<ReportsPage />} />
              <Route path="/reports/:id" element={<ReportDetailPage />} />
              <Route path="/knowledge" element={<KnowledgePage />} />
              <Route path="/skills" element={<SkillsPage />} />
              <Route path="/matching" element={<MatchingPage />} />
              <Route path="/expression" element={<ExpressionPage />} />
              <Route path="/jobs" element={<JobsPage />} />
              <Route path="/job-library" element={<JobLibraryPage />} />
              <Route path="/resume" element={<ResumePage />} />
              <Route path="/resume-gallery" element={<ResumeGalleryPage />} />
              <Route path="/mistakes" element={<MistakesPage />} />
              <Route path="/challenges" element={<ChallengesPage />} />
              <Route path="/concerto" element={<ConcertoPage />} />
              <Route path="/me" element={<MePage />} />
            </Route>
            <Route
              path="/interview/preview"
              element={
                <RequireAuth>
                  <InterviewPreviewPage />
                </RequireAuth>
              }
            />
            <Route
              path="/interview/:id"
              element={
                <RequireAuth>
                  <InterviewSessionPage />
                </RequireAuth>
              }
            />
            {/* 观澜管理中心：仅管理员（前端守卫为展示层，接口在服务端二次校验） */}
            <Route
              path="/admin"
              element={
                <RequireAdmin>
                  <AdminLayout />
                </RequireAdmin>
              }
            >
              <Route index element={<AdminOverviewPage />} />
              <Route path="users" element={<AdminUsersPage />} />
              <Route path="users/:userId" element={<AdminUserDetailPage />} />
              <Route path="modules" element={<AdminModulesPage />} />
              <Route path="ai" element={<AdminAiPage />} />
              <Route path="audit" element={<AdminAuditPage />} />
            </Route>
            <Route path="*" element={<NotFoundPage />} />
            </Routes>
          </Suspense>
        </OnboardingProvider>
      </AuthProvider>
    </MotionConfig>
  )
}
