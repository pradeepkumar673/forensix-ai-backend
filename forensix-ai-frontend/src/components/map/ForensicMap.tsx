/**
 * ForensicMap.tsx
 * Forensic Geolocation Lattice — Crime Scene Mapping Module
 *
 * Dependencies (add to package.json):
 *   leaflet, react-leaflet, leaflet.markercluster, @types/leaflet
 *
 * npm install leaflet react-leaflet @types/leaflet
 *
 * Also add to your global CSS (index.css):
 *   @import 'leaflet/dist/leaflet.css';
 */

import { useEffect, useRef, useState, useCallback } from 'react'
import { analyzeGeospatial } from '@/lib/api'
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  LayerGroup,
  LayersControl,
  useMap,
  Circle,
  Polyline,
  ZoomControl,
} from 'react-leaflet'
import L, { LatLngExpression } from 'leaflet'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  AlertTriangle,
  Crosshair,
  Eye,
  Layers,
  Loader2,
  MapPin,
  Navigation,
  Plus,
  Radio,
  Save,
  Trash2,
  User,
  Zap,
} from 'lucide-react'
import { toast } from 'sonner'

// ─── Types ────────────────────────────────────────────────────────────────────

export type LocationType =
  | 'crime_scene'
  | 'body_discovery'
  | 'witness'
  | 'suspect'
  | 'vehicle'
  | 'cctv'
  | 'hospital'
  | 'escape_route'
  | 'custom'

export interface ForensicPin {
  id: string
  lat: number
  lng: number
  name: string
  description: string
  type: LocationType
  confidence: number // 0–100
  extractedFrom?: string
  timestamp?: string
  manual?: boolean
}

export interface ForensicMapProps {
  caseId: string
  reportText?: string
  combinedAnalysis?: string
}

// ─── Constants ────────────────────────────────────────────────────────────────

const TYPE_META: Record<
  LocationType,
  { label: string; color: string; icon: string; hex: string }
> = {
  crime_scene:    { label: 'Crime Scene',      color: '#dc2626', icon: '🔴', hex: '#dc2626' },
  body_discovery: { label: 'Body Discovery',   color: '#7c3aed', icon: '🟣', hex: '#7c3aed' },
  witness:        { label: 'Witness Location', color: '#2563eb', icon: '🔵', hex: '#2563eb' },
  suspect:        { label: 'Suspect Linked',   color: '#d97706', icon: '🟠', hex: '#d97706' },
  vehicle:        { label: 'Vehicle / Parking',color: '#ca8a04', icon: '🟡', hex: '#ca8a04' },
  cctv:           { label: 'CCTV / Surveillance', color: '#0891b2', icon: '🩵', hex: '#0891b2' },
  hospital:       { label: 'Hospital / Morgue',color: '#16a34a', icon: '🟢', hex: '#16a34a' },
  escape_route:   { label: 'Escape Route',     color: '#e11d48', icon: '❗', hex: '#e11d48' },
  custom:         { label: 'Custom Pin',       color: '#00f5ff', icon: '📍', hex: '#00f5ff' },
}

// ─── Marker Icon Factory ──────────────────────────────────────────────────────

function makeIcon(type: LocationType, pulse = false) {
  const { hex } = TYPE_META[type]
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="32" height="40" viewBox="0 0 32 40">
      ${pulse ? `<circle cx="16" cy="16" r="18" fill="${hex}" opacity="0.18">
        <animate attributeName="r" values="14;22;14" dur="2s" repeatCount="indefinite"/>
        <animate attributeName="opacity" values="0.3;0;0.3" dur="2s" repeatCount="indefinite"/>
      </circle>` : ''}
      <circle cx="16" cy="16" r="12" fill="${hex}" opacity="0.25"/>
      <circle cx="16" cy="16" r="8" fill="${hex}"/>
      <circle cx="16" cy="16" r="4" fill="#ffffff" opacity="0.9"/>
      <line x1="16" y1="24" x2="16" y2="40" stroke="${hex}" stroke-width="2.5" opacity="0.7"/>
    </svg>
  `
  return L.divIcon({
    html: svg,
    className: '',
    iconSize: [32, 40],
    iconAnchor: [16, 40],
    popupAnchor: [0, -40],
  })
}

// REMOVED direct Anthropic fetch to avoid CORS blockers. 
// Logic moved to Backend via analyzeGeospatial().

// ─── Map Centre Fly ───────────────────────────────────────────────────────────

function FlyToCenter({ center }: { center: LatLngExpression }) {
  const map = useMap()
  useEffect(() => {
    map.flyTo(center, 14, { duration: 1.4 })
  }, [center, map])
  return null
}

// ─── Confidence Badge ─────────────────────────────────────────────────────────

function ConfidenceBar({ value }: { value: number }) {
  const color = value >= 75 ? '#00f5ff' : value >= 45 ? '#d97706' : '#dc2626'
  return (
    <div className="mt-1 flex items-center gap-2">
      <div className="h-1.5 flex-1 rounded-full bg-white/10">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${value}%`, background: color }}
        />
      </div>
      <span className="font-mono text-[10px]" style={{ color }}>
        {value}%
      </span>
    </div>
  )
}

// ─── Main Component ───────────────────────────────────────────────────────────

export function ForensicMap({ caseId, reportText = '', combinedAnalysis = '' }: ForensicMapProps) {
  const [pins, setPins] = useState<ForensicPin[]>([])
  const [isExtracting, setIsExtracting] = useState(false)
  const [selectedPin, setSelectedPin] = useState<ForensicPin | null>(null)
  const [center, setCenter] = useState<[number, number]>([20.5937, 78.9629]) // Default: India center
  const [manualName, setManualName] = useState('')
  const [manualLat, setManualLat] = useState('')
  const [manualLng, setManualLng] = useState('')
  const [manualType, setManualType] = useState<LocationType>('custom')
  const [showAddPanel, setShowAddPanel] = useState(false)
  const [mapReady, setMapReady] = useState(false)
  const storageKey = `forensix-map-${caseId}`

  // ── Load saved state ──
  useEffect(() => {
    if (!caseId) return
    try {
      const saved = localStorage.getItem(storageKey)
      if (saved) {
        const data = JSON.parse(saved) as { pins: ForensicPin[]; center: [number, number] }
        setPins(data.pins ?? [])
        setCenter(data.center ?? [20.5937, 78.9629])
      }
    } catch {
      /* ignore */
    }
    setMapReady(true)
  }, [caseId, storageKey])

  // ── Save state ──
  const saveState = useCallback(
    (nextPins: ForensicPin[], nextCenter: [number, number]) => {
      try {
        localStorage.setItem(storageKey, JSON.stringify({ pins: nextPins, center: nextCenter }))
        toast.success('Map lattice saved to local vault')
      } catch {
        toast.error('Save failed — storage quota exceeded')
      }
    },
    [storageKey],
  )

  // ── Extract locations ──
  const handleExtract = async () => {
    const text = reportText || combinedAnalysis
    if (!text.trim()) {
      toast.error('No report text available — paste text or run analysis first')
      return
    }
    setIsExtracting(true)
    try {
      const data = await analyzeGeospatial(caseId, text)
      const extracted: ForensicPin[] = data.points.map((p: any) => ({
        id: p.point_id,
        name: p.label,
        description: p.description,
        lat: p.latitude,
        lng: p.longitude,
        type: p.point_type,
        confidence: p.confidence?.score ? Math.round(p.confidence.score * 100) : 85,
        timestamp: p.timestamp
      }))
      
      setPins(extracted)
      const primary = extracted.find((p) => p.type === 'crime_scene') ?? extracted[0]
      if (primary) {
        const newCenter: [number, number] = [primary.lat, primary.lng]
        setCenter(newCenter)
      }
      toast.success(`${extracted.length} geospatial nodes crystallized`)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Unknown error'
      toast.error(`Neural geocoding failed: ${msg}`)
    } finally {
      setIsExtracting(false)
    }
  }

  // ── Add manual pin ──
  const handleAddPin = () => {
    const lat = parseFloat(manualLat)
    const lng = parseFloat(manualLng)
    if (!manualName || isNaN(lat) || isNaN(lng)) {
      toast.error('Enter name, latitude, and longitude')
      return
    }
    const pin: ForensicPin = {
      id: crypto.randomUUID(),
      name: manualName,
      description: 'Manually added by investigator',
      lat,
      lng,
      type: manualType,
      confidence: 100,
      manual: true,
      timestamp: new Date().toISOString(),
    }
    setPins((prev) => [...prev, pin])
    setManualName('')
    setManualLat('')
    setManualLng('')
    setShowAddPanel(false)
    toast.success('Pin anchored to lattice')
  }

  // ── Remove pin ──
  const removePin = (id: string) => {
    setPins((prev) => prev.filter((p) => p.id !== id))
    if (selectedPin?.id === id) setSelectedPin(null)
  }

  // ── Escape route polyline ──
  const escapeRoutes = pins
    .filter((p) => p.type === 'escape_route')
    .map((p) => [p.lat, p.lng] as [number, number])
  const crimeScene = pins.find((p) => p.type === 'crime_scene')
  const escapeLine: [number, number][] = crimeScene
    ? [[crimeScene.lat, crimeScene.lng], ...escapeRoutes]
    : escapeRoutes

  return (
    <div className="grid h-full gap-4 lg:grid-cols-[1fr_340px]">
      {/* ── Map Canvas ── */}
      <div className="relative overflow-hidden rounded-2xl border border-primary/20" style={{ minHeight: 520 }}>
        {/* Header overlay */}
        <div
          className="absolute left-0 right-0 top-0 z-[500] flex items-center justify-between gap-3 px-4 py-2"
          style={{
            background: 'linear-gradient(180deg, rgba(3,8,20,0.96) 0%, rgba(3,8,20,0) 100%)',
          }}
        >
          <div className="flex items-center gap-2">
            <Crosshair className="h-4 w-4 text-primary animate-pulse" />
            <span className="font-mono text-[11px] uppercase tracking-[0.28em] text-primary">
              Geospatial Lattice
            </span>
            <Badge
              variant="outline"
              className="border-primary/30 font-mono text-[9px] uppercase text-cyan-400"
            >
              {pins.length} nodes
            </Badge>
          </div>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              className="h-7 border-primary/25 bg-background/80 font-mono text-[10px] uppercase"
              onClick={() => setShowAddPanel((v) => !v)}
            >
              <Plus className="mr-1 h-3 w-3" />
              Add Pin
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="h-7 border-primary/25 bg-background/80 font-mono text-[10px] uppercase"
              onClick={() => saveState(pins, center)}
              disabled={pins.length === 0}
            >
              <Save className="mr-1 h-3 w-3" />
              Save
            </Button>
          </div>
        </div>

        {/* Manual add panel */}
        {showAddPanel && (
          <div
            className="absolute left-4 top-14 z-[500] w-72 rounded-xl border border-primary/30 p-4 shadow-2xl"
            style={{ background: 'rgba(3,8,20,0.97)' }}
          >
            <p className="mb-3 font-mono text-[10px] uppercase tracking-[0.22em] text-primary">
              Manual Pin Entry
            </p>
            <div className="space-y-2">
              <Input
                placeholder="Location name"
                value={manualName}
                onChange={(e) => setManualName(e.target.value)}
                className="h-8 border-primary/20 bg-background/60 font-mono text-xs"
              />
              <div className="grid grid-cols-2 gap-2">
                <Input
                  placeholder="Latitude"
                  value={manualLat}
                  onChange={(e) => setManualLat(e.target.value)}
                  className="h-8 border-primary/20 bg-background/60 font-mono text-xs"
                />
                <Input
                  placeholder="Longitude"
                  value={manualLng}
                  onChange={(e) => setManualLng(e.target.value)}
                  className="h-8 border-primary/20 bg-background/60 font-mono text-xs"
                />
              </div>
              <select
                value={manualType}
                onChange={(e) => setManualType(e.target.value as LocationType)}
                className="h-8 w-full rounded-md border border-primary/20 bg-background/60 px-2 font-mono text-xs text-foreground"
              >
                {(Object.keys(TYPE_META) as LocationType[]).map((t) => (
                  <option key={t} value={t}>
                    {TYPE_META[t].icon} {TYPE_META[t].label}
                  </option>
                ))}
              </select>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  className="h-7 flex-1 bg-primary font-mono text-[10px] uppercase text-primary-foreground"
                  onClick={handleAddPin}
                >
                  Anchor
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-7 font-mono text-[10px] uppercase"
                  onClick={() => setShowAddPanel(false)}
                >
                  Cancel
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* Leaflet map */}
        {mapReady && (
          <MapContainer
            center={center}
            zoom={12}
            style={{ height: '100%', width: '100%', background: '#040d1f' }}
            zoomControl={false}
          >
            <ZoomControl position="bottomright" />
            <TileLayer
              url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
              attribution='&copy; <a href="https://carto.com/">CARTO</a> &copy; OpenStreetMap contributors'
              maxZoom={19}
            />

            <FlyToCenter center={center} />

            {/* Escape route lines */}
            {escapeLine.length > 1 && (
              <Polyline
                positions={escapeLine}
                pathOptions={{
                  color: '#dc2626',
                  weight: 2,
                  dashArray: '6 4',
                  opacity: 0.7,
                }}
              />
            )}

            <LayersControl position="topright">
              {(Object.keys(TYPE_META) as LocationType[]).map((type) => {
                const typePins = pins.filter((p) => p.type === type)
                if (!typePins.length) return null
                return (
                  <LayersControl.Overlay
                    key={type}
                    name={`${TYPE_META[type].icon} ${TYPE_META[type].label}`}
                    checked
                  >
                    <LayerGroup>
                      {typePins.map((pin) => (
                        <Marker
                          key={pin.id}
                          position={[pin.lat, pin.lng]}
                          icon={makeIcon(pin.type, pin.type === 'crime_scene')}
                          eventHandlers={{ click: () => setSelectedPin(pin) }}
                        >
                          <Popup
                            className="forensic-popup"
                            maxWidth={300}
                          >
                            <div
                              style={{
                                background: '#040d1f',
                                border: `1px solid ${TYPE_META[pin.type].hex}44`,
                                borderRadius: 10,
                                padding: '12px 14px',
                                fontFamily: 'monospace',
                                minWidth: 220,
                              }}
                            >
                              <div
                                style={{
                                  fontSize: 9,
                                  textTransform: 'uppercase',
                                  letterSpacing: '0.22em',
                                  color: TYPE_META[pin.type].hex,
                                  marginBottom: 6,
                                }}
                              >
                                {TYPE_META[pin.type].label}
                                {pin.manual && (
                                  <span style={{ color: '#00f5ff', marginLeft: 8 }}>
                                    · Manual
                                  </span>
                                )}
                              </div>
                              <div
                                style={{
                                  fontSize: 13,
                                  fontWeight: 600,
                                  color: '#e2e8f0',
                                  marginBottom: 4,
                                }}
                              >
                                {pin.name}
                              </div>
                              <div style={{ fontSize: 11, color: '#8ba4c7', marginBottom: 8 }}>
                                {pin.description}
                              </div>
                              {pin.extractedFrom && (
                                <div
                                  style={{
                                    fontSize: 10,
                                    color: '#5f7394',
                                    borderLeft: `2px solid ${TYPE_META[pin.type].hex}`,
                                    paddingLeft: 8,
                                    marginBottom: 8,
                                    fontStyle: 'italic',
                                  }}
                                >
                                  {pin.extractedFrom}
                                </div>
                              )}
                              <div style={{ fontSize: 10, color: '#5f7394' }}>
                                {pin.lat.toFixed(5)}, {pin.lng.toFixed(5)}
                              </div>
                              <div style={{ marginTop: 6 }}>
                                <div
                                  style={{
                                    height: 3,
                                    background: '#ffffff10',
                                    borderRadius: 2,
                                    overflow: 'hidden',
                                  }}
                                >
                                  <div
                                    style={{
                                      height: '100%',
                                      width: `${pin.confidence}%`,
                                      background: TYPE_META[pin.type].hex,
                                      borderRadius: 2,
                                    }}
                                  />
                                </div>
                                <div
                                  style={{ fontSize: 9, color: '#5f7394', marginTop: 2 }}
                                >
                                  Confidence: {pin.confidence}%
                                </div>
                              </div>
                            </div>
                          </Popup>

                          {/* CCTV radius ring */}
                          {pin.type === 'cctv' && (
                            <Circle
                              center={[pin.lat, pin.lng]}
                              radius={150}
                              pathOptions={{
                                color: '#0891b2',
                                fillColor: '#0891b2',
                                fillOpacity: 0.08,
                                weight: 1,
                                dashArray: '4 3',
                              }}
                            />
                          )}

                          {/* Crime scene radius */}
                          {pin.type === 'crime_scene' && (
                            <Circle
                              center={[pin.lat, pin.lng]}
                              radius={80}
                              pathOptions={{
                                color: '#dc2626',
                                fillColor: '#dc2626',
                                fillOpacity: 0.06,
                                weight: 1,
                                dashArray: '6 3',
                              }}
                            />
                          )}
                        </Marker>
                      ))}
                    </LayerGroup>
                  </LayersControl.Overlay>
                )
              })}
            </LayersControl>
          </MapContainer>
        )}

        {/* Bottom overlay — legend */}
        <div
          className="absolute bottom-0 left-0 right-0 z-[500] flex items-center gap-3 overflow-x-auto px-4 py-2"
          style={{
            background: 'linear-gradient(0deg, rgba(3,8,20,0.92) 0%, rgba(3,8,20,0) 100%)',
          }}
        >
          {(Object.keys(TYPE_META) as LocationType[])
            .filter((t) => pins.some((p) => p.type === t))
            .map((t) => (
              <div key={t} className="flex shrink-0 items-center gap-1.5">
                <div
                  className="h-2 w-2 rounded-full"
                  style={{ background: TYPE_META[t].hex }}
                />
                <span className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground">
                  {TYPE_META[t].label}
                </span>
              </div>
            ))}
        </div>
      </div>

      {/* ── Side Panel ── */}
      <div className="flex flex-col gap-4">
        {/* Control card */}
        <Card className="glass-panel border-primary/20">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 font-display text-base">
              <Radio className="h-4 w-4 text-primary" />
              Neural Geocoding
            </CardTitle>
            <CardDescription className="font-mono text-[10px] uppercase tracking-[0.22em]">
              LLM-powered location extraction
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="font-mono text-[11px] leading-relaxed text-muted-foreground">
              Parses autopsy / case text → extracts real locations + generates investigative
              intelligence points.
            </p>
            <Button
              className="w-full bg-primary font-mono text-xs uppercase tracking-wider text-primary-foreground hover:bg-primary/90"
              onClick={handleExtract}
              disabled={isExtracting || (!reportText && !combinedAnalysis)}
            >
              {isExtracting ? (
                <>
                  <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
                  Neural geocoding in progress...
                </>
              ) : (
                <>
                  <Zap className="mr-2 h-3.5 w-3.5" />
                  Extract & Map Locations
                </>
              )}
            </Button>
            {!reportText && !combinedAnalysis && (
              <p className="font-mono text-[10px] text-amber-400/80">
                ⚠ No report text — run report analysis or paste text
              </p>
            )}
          </CardContent>
        </Card>

        {/* Stats */}
        {pins.length > 0 && (
          <div className="grid grid-cols-3 gap-2">
            {(['crime_scene', 'witness', 'suspect'] as LocationType[]).map((t) => {
              const count = pins.filter((p) => p.type === t).length
              return (
                <div
                  key={t}
                  className="rounded-lg border border-primary/15 bg-card/50 p-2 text-center"
                >
                  <div
                    className="font-display text-xl font-bold"
                    style={{ color: TYPE_META[t].hex }}
                  >
                    {count}
                  </div>
                  <div className="font-mono text-[8px] uppercase tracking-wider text-muted-foreground">
                    {TYPE_META[t].label.split(' ')[0]}
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {/* Pin list */}
        <Card className="glass-panel flex-1 border-primary/20">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 font-display text-sm">
              <Layers className="h-3.5 w-3.5 text-primary" />
              Intelligence Nodes
              <Badge
                variant="outline"
                className="ml-auto border-primary/25 font-mono text-[9px]"
              >
                {pins.length}
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <ScrollArea className="h-[320px]">
              {pins.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <MapPin className="mb-3 h-8 w-8 text-primary/20" />
                  <p className="font-mono text-[11px] text-muted-foreground/60">
                    No nodes mapped yet
                  </p>
                  <p className="mt-1 font-mono text-[10px] text-muted-foreground/40">
                    Extract from report or add manually
                  </p>
                </div>
              ) : (
                <div className="space-y-1 p-3">
                  {pins.map((pin) => (
                    <button
                      key={pin.id}
                      className="group w-full rounded-lg border border-primary/10 bg-background/40 px-3 py-2.5 text-left transition-all hover:border-primary/30 hover:bg-card/60"
                      style={{
                        borderLeftColor:
                          selectedPin?.id === pin.id
                            ? TYPE_META[pin.type].hex
                            : undefined,
                        borderLeftWidth: selectedPin?.id === pin.id ? 3 : undefined,
                      }}
                      onClick={() => {
                        setSelectedPin(pin)
                        setCenter([pin.lat, pin.lng])
                      }}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-1.5">
                            <div
                              className="h-1.5 w-1.5 shrink-0 rounded-full"
                              style={{ background: TYPE_META[pin.type].hex }}
                            />
                            <span className="truncate font-mono text-[11px] font-medium text-card-foreground">
                              {pin.name}
                            </span>
                            {pin.manual && (
                              <Badge
                                variant="outline"
                                className="h-4 border-cyan-500/30 px-1 font-mono text-[8px] text-cyan-400"
                              >
                                manual
                              </Badge>
                            )}
                          </div>
                          <div className="mt-0.5 font-mono text-[9px] text-muted-foreground/60 uppercase tracking-wider">
                            {TYPE_META[pin.type].label}
                          </div>
                          <ConfidenceBar value={pin.confidence} />
                        </div>
                        <button
                          className="shrink-0 opacity-0 transition-opacity group-hover:opacity-100"
                          onClick={(e) => {
                            e.stopPropagation()
                            removePin(pin.id)
                          }}
                        >
                          <Trash2 className="h-3.5 w-3.5 text-red-400/60 hover:text-red-400" />
                        </button>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </ScrollArea>
          </CardContent>
        </Card>

        {/* Selected pin detail */}
        {selectedPin && (
          <Card
            className="glass-panel border-primary/20"
            style={{ borderColor: `${TYPE_META[selectedPin.type].hex}33` }}
          >
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="font-display text-sm" style={{ color: TYPE_META[selectedPin.type].hex }}>
                  <span className="mr-2">{TYPE_META[selectedPin.type].icon}</span>
                  {TYPE_META[selectedPin.type].label}
                </CardTitle>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-6 w-6 p-0"
                  onClick={() => setSelectedPin(null)}
                >
                  ×
                </Button>
              </div>
              <p className="font-mono text-[13px] font-medium text-card-foreground">
                {selectedPin.name}
              </p>
            </CardHeader>
            <CardContent className="space-y-2 pt-0">
              <p className="font-mono text-[11px] leading-relaxed text-muted-foreground">
                {selectedPin.description}
              </p>
              {selectedPin.extractedFrom && (
                <div className="rounded border-l-2 border-primary/40 bg-background/40 px-2 py-1.5">
                  <p className="font-mono text-[10px] italic text-muted-foreground/70">
                    "{selectedPin.extractedFrom}"
                  </p>
                </div>
              )}
              <div className="flex items-center gap-4 font-mono text-[10px] text-muted-foreground/60">
                <span>
                  <Navigation className="mr-1 inline h-3 w-3" />
                  {selectedPin.lat.toFixed(5)}, {selectedPin.lng.toFixed(5)}
                </span>
              </div>
              <ConfidenceBar value={selectedPin.confidence} />
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}

export default ForensicMap
