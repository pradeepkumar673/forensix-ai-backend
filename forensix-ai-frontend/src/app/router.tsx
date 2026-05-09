import { createBrowserRouter } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { RequireAuth } from '@/app/RequireAuth'
import { ShortcutsRoot } from '@/app/ShortcutsRoot'
import DashboardPage from '@/pages/DashboardPage'
import LoginPage from '@/pages/LoginPage'
import CasesPage from '@/pages/CasesPage'
import NewCasePage from '@/pages/NewCasePage'
import VaultPage from '@/pages/VaultPage'
import LabPage from '@/pages/LabPage'
import WorkspacePage from '@/pages/WorkspacePage'
import ReportForgePage from '@/pages/ReportForgePage'

export const router = createBrowserRouter([
  {
    element: <ShortcutsRoot />,
    children: [
      { path: '/login', element: <LoginPage /> },
      {
        element: <RequireAuth />,
        children: [
          {
            path: '/',
            element: <AppShell />,
            children: [
              { index: true, element: <DashboardPage /> },
              { path: 'cases', element: <CasesPage /> },
              { path: 'cases/new', element: <NewCasePage /> },
              { path: 'vault', element: <VaultPage /> },
              { path: 'lab', element: <LabPage /> },
              { path: 'workspace', element: <WorkspacePage /> },
              { path: 'report', element: <ReportForgePage /> },
            ],
          },
        ],
      },
    ],
  },
])
