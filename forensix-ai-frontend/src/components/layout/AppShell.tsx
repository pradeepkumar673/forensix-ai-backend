import { Outlet } from 'react-router-dom'
import { Sidebar } from '@/components/layout/Sidebar'
import { TopBar } from '@/components/layout/TopBar'
import { CyberBackdrop } from '@/components/effects/CyberBackdrop'
import { ScanningOverlay } from '@/components/effects/ScanningOverlay'
import { NeuralCommandPalette } from '@/components/command/NeuralCommandPalette'
import { ForensicOracle } from '@/components/oracle/ForensicOracle'
export function AppShell() {
  return (
    <div className="scanlines flex min-h-dvh text-foreground">
      <CyberBackdrop />
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <main className="relative flex-1 overflow-y-auto px-4 py-6 md:px-8">
          <Outlet />
        </main>
      </div>
      <ScanningOverlay />
      <NeuralCommandPalette />
      <ForensicOracle />
    </div>
  )
}
