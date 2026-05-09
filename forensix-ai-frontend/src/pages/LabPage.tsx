import { DigitalAutopsyLab } from '@/components/lab/DigitalAutopsyLab'
import { useCaseStore } from '@/stores/case-store'

export default function LabPage() {
  const activeId = useCaseStore((s) => s.activeCaseId)

  return (
    <div className="space-y-8">
      <header>
        <p className="font-mono text-[11px] uppercase tracking-[0.34em] text-primary">Digital autopsy</p>
        <h1 className="font-display text-4xl font-semibold text-card-foreground">Spectral trauma lattice</h1>
        <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
          Showcase twin — Konva tensor plane fused with MedSAM-style segmentation, ViTPose kinematics, ELA tamper optics,
          and investigative overlays.
        </p>
      </header>

      <DigitalAutopsyLab caseId={activeId} />
    </div>
  )
}
