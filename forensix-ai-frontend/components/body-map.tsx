'use client'

import { useState, useRef, useEffect } from 'react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Trash2, Copy, Download } from 'lucide-react'

interface Wound {
  id: string
  x: number
  y: number
  type: 'wound' | 'spatter' | 'pose'
  description?: string
  severity?: 'minor' | 'moderate' | 'severe'
}

interface BodyMapProps {
  caseId?: string
  readOnly?: boolean
  onWoundsChange?: (wounds: Wound[]) => void
}

export function BodyMap({ caseId, readOnly = false, onWoundsChange }: BodyMapProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [wounds, setWounds] = useState<Wound[]>([
    { id: '1', x: 200, y: 150, type: 'wound', description: 'Head laceration', severity: 'severe' },
    { id: '2', x: 150, y: 250, type: 'wound', description: 'Shoulder wound', severity: 'moderate' },
    { id: '3', x: 180, y: 350, type: 'spatter', description: 'Blood spatter pattern' },
  ])
  const [selectedWound, setSelectedWound] = useState<string | null>(null)
  const [mode, setMode] = useState<'view' | 'add-wound' | 'add-spatter' | 'add-pose'>('view')

  useEffect(() => {
    drawBodyMap()
  }, [wounds, selectedWound, mode])

  useEffect(() => {
    onWoundsChange?.(wounds)
  }, [wounds, onWoundsChange])

  const drawBodyMap = () => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    // Clear canvas
    ctx.fillStyle = '#141f30'
    ctx.fillRect(0, 0, canvas.width, canvas.height)

    // Draw body outline (simplified human figure)
    ctx.strokeStyle = '#3a5570'
    ctx.lineWidth = 2
    ctx.fillStyle = '#1a2a3a'

    // Head
    ctx.beginPath()
    ctx.arc(canvas.width / 2, 80, 40, 0, Math.PI * 2)
    ctx.fill()
    ctx.stroke()

    // Torso
    ctx.fillRect(canvas.width / 2 - 35, 130, 70, 120)
    ctx.strokeRect(canvas.width / 2 - 35, 130, 70, 120)

    // Arms
    ctx.fillRect(canvas.width / 2 - 100, 150, 65, 20)
    ctx.strokeRect(canvas.width / 2 - 100, 150, 65, 20)
    ctx.fillRect(canvas.width / 2 + 35, 150, 65, 20)
    ctx.strokeRect(canvas.width / 2 + 35, 150, 65, 20)

    // Legs
    ctx.fillRect(canvas.width / 2 - 25, 260, 20, 90)
    ctx.strokeRect(canvas.width / 2 - 25, 260, 20, 90)
    ctx.fillRect(canvas.width / 2 + 5, 260, 20, 90)
    ctx.strokeRect(canvas.width / 2 + 5, 260, 20, 90)

    // Draw wounds
    wounds.forEach((wound) => {
      const isSelected = wound.id === selectedWound

      if (wound.type === 'wound') {
        ctx.fillStyle = isSelected ? '#ff1744' : '#c2185b'
        ctx.beginPath()
        ctx.arc(wound.x, wound.y, 12, 0, Math.PI * 2)
        ctx.fill()

        // Highlight ring if selected
        if (isSelected) {
          ctx.strokeStyle = '#ff1744'
          ctx.lineWidth = 3
          ctx.beginPath()
          ctx.arc(wound.x, wound.y, 18, 0, Math.PI * 2)
          ctx.stroke()
        }
      } else if (wound.type === 'spatter') {
        // Blood spatter pattern
        ctx.fillStyle = isSelected ? '#ff6b6b' : '#d32f2f'
        for (let i = 0; i < 5; i++) {
          const angle = (i / 5) * Math.PI * 2
          const distance = 15
          const x = wound.x + Math.cos(angle) * distance
          const y = wound.y + Math.sin(angle) * distance
          ctx.beginPath()
          ctx.arc(x, y, 4, 0, Math.PI * 2)
          ctx.fill()
        }
      } else if (wound.type === 'pose') {
        ctx.strokeStyle = '#00d9ff'
        ctx.lineWidth = 3
        ctx.beginPath()
        ctx.arc(wound.x, wound.y, 10, 0, Math.PI * 2)
        ctx.stroke()
      }

      // Draw label
      ctx.fillStyle = '#e6f0fa'
      ctx.font = '12px Arial'
      ctx.fillText(wound.description || 'Wound', wound.x + 20, wound.y - 10)
    })

    // Draw grid when in edit mode
    if (!readOnly && mode !== 'view') {
      ctx.strokeStyle = '#3a5570'
      ctx.lineWidth = 0.5
      for (let i = 0; i < canvas.width; i += 20) {
        ctx.beginPath()
        ctx.moveTo(i, 0)
        ctx.lineTo(i, canvas.height)
        ctx.stroke()
      }
      for (let i = 0; i < canvas.height; i += 20) {
        ctx.beginPath()
        ctx.moveTo(0, i)
        ctx.lineTo(canvas.width, i)
        ctx.stroke()
      }
    }
  }

  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (readOnly) return

    const canvas = canvasRef.current
    if (!canvas) return

    const rect = canvas.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top

    // Check if clicking on existing wound
    for (const wound of wounds) {
      const distance = Math.hypot(wound.x - x, wound.y - y)
      if (distance < 20) {
        setSelectedWound(wound.id)
        return
      }
    }

    // Add new wound
    if (mode !== 'view') {
      const newWound: Wound = {
        id: Date.now().toString(),
        x,
        y,
        type: mode === 'add-wound' ? 'wound' : mode === 'add-spatter' ? 'spatter' : 'pose',
        description: `${mode.replace('add-', '').toUpperCase()} at (${Math.round(x)}, ${Math.round(y)})`,
      }
      setWounds([...wounds, newWound])
      setSelectedWound(newWound.id)
    }
  }

  const deleteWound = (woundId: string) => {
    setWounds(wounds.filter((w) => w.id !== woundId))
    setSelectedWound(null)
  }

  return (
    <div className="space-y-6">
      {/* Controls */}
      <Card className="p-4 bg-card border-border">
        <div className="flex flex-wrap gap-2">
          <Button
            variant={mode === 'view' ? 'default' : 'outline'}
            onClick={() => setMode('view')}
            className="gap-2"
          >
            View
          </Button>
          <Button
            variant={mode === 'add-wound' ? 'default' : 'outline'}
            onClick={() => setMode('add-wound')}
            disabled={readOnly}
            className="gap-2"
          >
            Add Wound
          </Button>
          <Button
            variant={mode === 'add-spatter' ? 'default' : 'outline'}
            onClick={() => setMode('add-spatter')}
            disabled={readOnly}
            className="gap-2"
          >
            Add Spatter
          </Button>
          <Button
            variant={mode === 'add-pose' ? 'default' : 'outline'}
            onClick={() => setMode('add-pose')}
            disabled={readOnly}
            className="gap-2"
          >
            Mark Pose
          </Button>

          <div className="flex-1" />

          <Button variant="outline" className="gap-2">
            <Copy className="w-4 h-4" />
            Copy
          </Button>
          <Button variant="outline" className="gap-2">
            <Download className="w-4 h-4" />
            Export
          </Button>
        </div>
      </Card>

      {/* Canvas */}
      <Card className="bg-card border-border p-4 overflow-auto">
        <canvas
          ref={canvasRef}
          width={400}
          height={450}
          onClick={handleCanvasClick}
          className={`mx-auto border-2 border-border rounded ${!readOnly && mode !== 'view' ? 'cursor-crosshair' : 'cursor-pointer'}`}
        />
      </Card>

      {/* Wound List */}
      <Card className="p-4 bg-card border-border">
        <h3 className="font-semibold text-foreground mb-4">Wounds & Markings ({wounds.length})</h3>
        <div className="space-y-2 max-h-48 overflow-y-auto">
          {wounds.map((wound) => (
            <div
              key={wound.id}
              className={`flex items-center justify-between p-3 rounded-lg cursor-pointer transition-colors ${
                selectedWound === wound.id
                  ? 'bg-accent/20 border border-accent'
                  : 'bg-background border border-border hover:border-accent/50'
              }`}
              onClick={() => setSelectedWound(wound.id)}
            >
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <div
                    className={`w-3 h-3 rounded-full ${
                      wound.type === 'wound'
                        ? 'bg-red-500'
                        : wound.type === 'spatter'
                          ? 'bg-orange-500'
                          : 'bg-cyan-500'
                    }`}
                  />
                  <span className="text-sm font-medium text-foreground">{wound.description}</span>
                  {wound.severity && <span className="text-xs text-muted-foreground">({wound.severity})</span>}
                </div>
                <p className="text-xs text-muted-foreground mt-1">Position: ({wound.x}, {wound.y})</p>
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={(e) => {
                  e.stopPropagation()
                  deleteWound(wound.id)
                }}
                disabled={readOnly}
                className="h-8 w-8 text-destructive hover:text-destructive"
              >
                <Trash2 className="w-4 h-4" />
              </Button>
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}
