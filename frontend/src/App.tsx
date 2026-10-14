import { MotionConfig } from 'motion/react'
import { useEffect } from 'react'
import { Route, Routes, useLocation } from 'react-router-dom'
import { AuthProvider } from './context/AuthProvider'
import { RequireAuth } from './context/RequireAuth'
import { OnboardingProvider } from './components/onboarding/OnboardingGuide'
import AppLayout from './components/layout/AppLayout'
import AboutPage from './pages/AboutPage'
import AnnouncementsPage from './pages/AnnouncementsPage'
import TechArchivePage from './pages/TechArchivePage'
import AuthPage from './pages/AuthPage'
import CareerGuidePage from './pages/CareerGuidePage'
import DashboardPage from './pages/DashboardPage'
import HomePage from './pages/HomePage'
import InterviewNewPage from './pages/InterviewNewPage'
import InterviewPreviewPage from './pages/InterviewPreviewPage'
import InterviewSessionPage from './pages/InterviewSessionPage'
import { KnowledgePage } from './pages/KnowledgePage'
import { ExpressionPage } from './pages/ExpressionPage'
import { MatchingPage } from './pages/MatchingPage'
import JobsPage from './pages/JobsPage'
import JobLibraryPage from './pages/JobLibraryPage'
import ResumePage from './pages/ResumePage'
import MistakesPage from './pages/MistakesPage'
import ChallengesPage from './pages/ChallengesPage'
import ConcertoPage from './pages/ConcertoPage'
import MePage from './pages/MePage'
import NotFoundPage from './pages/NotFoundPage'
import ReportDetailPage from './pages/ReportDetailPage'
import ReportsPage from './pages/ReportsPage'
import { SkillsPage } from './pages/SkillsPage'

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
          <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </OnboardingProvider>
      </AuthProvider>
    </MotionConfig>
  )
}
