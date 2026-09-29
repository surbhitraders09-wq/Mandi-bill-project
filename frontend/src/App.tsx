import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { AppShell } from '@/components/layout/app-shell'
import { PagePlaceholder } from '@/components/layout/page-placeholder'
import { Permission } from '@/components/layout/permission'
import { ProtectedRoute } from '@/components/layout/protected-route'
import { ThemeProvider } from '@/components/layout/theme-provider'
import { Toaster } from '@/components/ui/toaster'
import { AuditPage } from '@/pages/audit'
import { AutomationPage } from '@/pages/automation'
import { BillsPage } from '@/pages/bills'
import { DashboardPage } from '@/pages/dashboard'
import { FarmerDetailPage } from '@/pages/farmer-detail'
import { FarmersPage } from '@/pages/farmers'
import { LoginPage } from '@/pages/login'
import { MobileBillDetailPage } from '@/pages/mobile/mobile-bill-detail'
import { MobileBillsPage } from '@/pages/mobile/mobile-bills'
import { MobileHomePage } from '@/pages/mobile/mobile-home'
import { MobileSummaryPage } from '@/pages/mobile/mobile-summary'
import { MobileReportsPage } from '@/pages/mobile/mobile-reports'
import { MobileSettingsPage } from '@/pages/mobile/mobile-settings'
import { NotificationsPage } from '@/pages/notifications'
import { ReportsPage } from '@/pages/reports'
import { SettingsPage } from '@/pages/settings'
import { StockPage } from '@/pages/stock'
import { TraderDetailPage } from '@/pages/trader-detail'
import { TradersPage } from '@/pages/traders'

export default function App() {
  return (
    <BrowserRouter>
      <ThemeProvider />
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/mobile" element={<MobileHomePage />} />
        <Route path="/mobile/bills" element={<MobileBillsPage />} />
        <Route path="/mobile/bills/:auctionId" element={<MobileBillDetailPage />} />
        <Route path="/mobile/summary" element={<MobileSummaryPage />} />
        <Route path="/mobile/reports" element={<MobileReportsPage />} />
        <Route path="/mobile/settings" element={<MobileSettingsPage />} />
        <Route
          element={
            <ProtectedRoute>
              <AppShell />
            </ProtectedRoute>
          }
        >
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />

          <Route
            path="/farmers"
            element={
              <Permission permission="farmers:read">
                <FarmersPage />
              </Permission>
            }
          />
          <Route
            path="/farmers/:id"
            element={
              <Permission permission="farmers:read">
                <FarmerDetailPage />
              </Permission>
            }
          />
          <Route
            path="/farmers/payments"
            element={
              <Permission permission="payments:read">
                <PagePlaceholder title="Farmer Payments" description="Track payment records for farmers." phase="Phase 2" />
              </Permission>
            }
          />
          <Route
            path="/traders"
            element={
              <Permission permission="traders:read">
                <TradersPage />
              </Permission>
            }
          />
          <Route
            path="/traders/:id"
            element={
              <Permission permission="traders:read">
                <TraderDetailPage />
              </Permission>
            }
          />
          <Route
            path="/traders/stock"
            element={
              <Permission permission="stock:read">
                <StockPage defaultSegment="trader" title="Trader Stock" />
              </Permission>
            }
          />
          <Route
            path="/stock"
            element={
              <Permission permission="stock:read">
                <StockPage />
              </Permission>
            }
          />
          <Route
            path="/payments"
            element={
              <Permission permission="payments:read">
                <PagePlaceholder title="Payments" description="Cash and online payment records." phase="Phase 3" />
              </Permission>
            }
          />
          <Route
            path="/bills"
            element={
              <Permission permission="bills:read">
                <BillsPage />
              </Permission>
            }
          />
          <Route
            path="/reports"
            element={
              <Permission permission="reports:read">
                <ReportsPage />
              </Permission>
            }
          />
          <Route
            path="/documents"
            element={
              <Permission permission="documents:read">
                <PagePlaceholder title="Document Center" description="Aadhaar, mandate, and proof documents." phase="Phase 2" />
              </Permission>
            }
          />
          <Route
            path="/automation"
            element={
              <Permission permission="automation:read">
                <AutomationPage />
              </Permission>
            }
          />
          <Route
            path="/notifications"
            element={
              <Permission permission="notifications:read">
                <NotificationsPage />
              </Permission>
            }
          />
          <Route path="/audit" element={<AuditPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Route>
      </Routes>
      <Toaster />
    </BrowserRouter>
  )
}
