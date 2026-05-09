import { Outlet, Navigate, Route, Routes } from 'react-router-dom'
import { useMemo, useState } from 'react'

import CasesPage from '@/pages/CasesPage'
import DashboardPage from '@/pages/DashboardPage'
import EvidenceVaultPage from '@/pages/EvidenceVaultPage'
import LabPage from '@/pages/LabPage'
import LoginPage from '@/pages/LoginPage'
import ReportForgePage from '@/pages/ReportForgePage'
import WorkspacePage from '@/pages/WorkspacePage'

import { GlobalPaletteWrapper } from '@/components/command/GlobalPalette'
import { AppShell } from '@/components/layout/AppShell'
import { OracleOrbButton, OraclePanel } from '@/components/oracle/OraclePanel'
import { useGlobalShortcuts } from '@/hooks/useGlobalShortcuts'
import { useCaseStore } from '@/stores/case-store'
import { useSessionStore } from '@/stores/session-store'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<OperationalShell />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/cases" element={<CasesPage />} />
          <Route path="/evidence" element={<EvidenceVaultPage />} />
          <Route path="/lab" element={<LabPage />} />
          <Route path="/workspace" element={<WorkspacePage />} />
          <Route path="/reports" element={<ReportForgePage />} />
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

function ProtectedRoute() {
  const biometric = useSessionStore((s) => s.biometricVerified)
  if (!biometric) return <Navigate to="/login" replace />
  return <Outlet />
}

/** Wraps routed pages with tactile shell + Oracle + ⌘ K shortcuts. */

function OperationalShell() {
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [oracleOpen, setOracleOpen] = useState(false)

  const cases = useCaseStore((s) => s.cases)
  const activeId = useCaseStore((s) => s.activeCaseId)

  const activeCase = useMemo(() => cases.find((c) => c.id === activeId) ?? null, [cases, activeId])

  useGlobalShortcuts({
    onCommandPalette: () => setPaletteOpen(true),
    onOracleToggle: () => setOracleOpen((o) => !o),
  })

  return (
    <GlobalPaletteWrapper open={paletteOpen} setOpen={setPaletteOpen}>
      <AppShell>
        <Outlet />
      </AppShell>

      <OraclePanel open={oracleOpen} onOpenChange={setOracleOpen} activeCase={activeCase} />
      {!oracleOpen && (
        <OracleOrbButton floating onToggle={() => setOracleOpen(true)}>Open forensic oracle</OracleOrbButton>
      )}
    </GlobalPaletteWrapper>
  )
}
