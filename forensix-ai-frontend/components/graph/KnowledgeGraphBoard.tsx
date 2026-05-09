/**
 * Interactive entity graph — binds FastAPI correlate/graph payloads to xyflow DAG.
 */

import '@xyflow/react/dist/style.css'

import {
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  type Node,
  type Edge,
  type NodeProps,
  type NodeTypes,
  MiniMap,
  Position,
  ReactFlow,
  ReactFlowProvider,
  MarkerType,
} from '@xyflow/react'
import { memo, useCallback, useMemo } from 'react'

type GraphEntityRaw = {
  entity_id?: string
  label?: string
  entity_type?: string
  risk_score?: number | null
  attributes?: Record<string, unknown>
}

type GraphRelRaw = {
  source_id?: string
  target_id?: string
  relation_type?: string
  strength?: number
}

export type ParsedGraphPayload = {
  entities: GraphEntityRaw[]
  relationships: GraphRelRaw[]
}

type EntityPayload = {
  label: string
  kind: string
  risk?: number | null
}

const EntityGlassNode = memo((props: NodeProps) => {
  const data = props.data as EntityPayload
  const hot = typeof data.risk === 'number' && data.risk > 62
  return (
    <div
      className={`relative max-w-[200px] rounded-lg border px-4 py-2 text-[11px] shadow-lg backdrop-blur-md ${
        hot
          ? 'border-accent/85 bg-accent/15 text-accent-foreground'
          : 'border-primary/35 bg-popover/90 text-popover-foreground'
      }`}
    >
      <Handle type="target" position={Position.Left} id="tl" />
      <Handle type="target" position={Position.Top} id="tt" />
      <Handle type="source" position={Position.Right} id="sr" />
      <Handle type="source" position={Position.Bottom} id="sb" />
      <p className="font-display text-[10px] uppercase tracking-[0.2em] text-primary/85">
        {data.kind ?? 'UNKNOWN'}
      </p>
      <p className="mt-1 line-clamp-2 font-medium leading-tight">{data.label}</p>
      {typeof data.risk === 'number' && (
        <p className="mt-2 font-mono text-[10px] text-muted-foreground">
          RISK {data.risk.toFixed(1)}
        </p>
      )}
    </div>
  )
})

function hashColor(label: string) {
  let h = 0
  for (let i = 0; i < label.length; i++) {
    h = (h << 5) - h + label.charCodeAt(i)
    h |= 0
  }
  const hues = ['#22d3ee', '#38bdf8', '#a855f7', '#f97316']
  return hues[Math.abs(h) % hues.length]
}

function layoutCircular(n: number, i: number) {
  const r = Math.min(220, 140 + Math.max(n, 1) * 6)
  const ang = (i / Math.max(n, 1)) * Math.PI * 2 - Math.PI / 2
  return { x: 320 + Math.cos(ang) * r, y: 320 + Math.sin(ang) * r }
}

type Props = {
  payload: ParsedGraphPayload | null
}

export function KnowledgeGraphBoard({ payload }: Props) {
  const demo: ParsedGraphPayload = useMemo(
    () => ({
      entities: [
        { entity_id: '1', entity_type: 'person', label: 'Victim Proxy', risk_score: 12 },
        { entity_id: '2', entity_type: 'weapon', label: 'Bladed instrument', risk_score: 88 },
        {
          entity_id: '3',
          entity_type: 'location',
          label: 'Harbor Industrial Unit 04',
          risk_score: 44,
        },
        { entity_id: '4', entity_type: 'person', label: 'Primary Suspect Ω', risk_score: 79 },
      ],
      relationships: [
        { source_id: '4', target_id: '3', relation_type: 'LAST_SEEN', strength: 0.9 },
        { source_id: '4', target_id: '2', relation_type: 'POSSESSED', strength: 0.73 },
        { source_id: '1', target_id: '2', relation_type: 'INJURED_BY', strength: 0.95 },
      ],
    }),
    []
  )

  const source = payload && payload.entities.length > 0 ? payload : demo

  const nodes: Node[] = useMemo(
    () =>
      source.entities.map((e, idx) => {
        const pos = layoutCircular(source.entities.length, idx)
        const id = e.entity_id ?? `e-${idx}`
        return {
          id,
          type: 'glass',
          position: pos,
          data: {
            label: e.label ?? 'Unlabelled signal',
            kind: e.entity_type ?? 'OTHER',
            risk: e.risk_score,
          },
        }
      }),
    [source.entities]
  )

  const edges: Edge[] = useMemo(() => {
    return source.relationships.flatMap((r, i): Edge[] => {
      const stroke = hashColor(`${r.source_id}:${r.target_id}:${i}`)
      const w = Math.max((r.strength ?? 0.55) * 4, 1.2)

      const srcRaw = String(r.source_id ?? '')
      const tgtRaw = String(r.target_id ?? '')
      const sidOk = nodes.some((n) => n.id === srcRaw)
      const tidOk = nodes.some((n) => n.id === tgtRaw)
      if (!sidOk || !tidOk) return []

      const edgeOut: Edge = {
        id: `${srcRaw}->${tgtRaw}-${i}`,
        source: srcRaw,
        target: tgtRaw,
        label: r.relation_type ?? 'REL',
        animated: (r.strength ?? 0) > 0.75,
        style: {
          stroke,
          strokeWidth: w,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: stroke,
        },
        labelStyle: { fill: '#e8eef7', fontSize: 9, fontFamily: 'JetBrains Mono, monospace' },
      }
      return [edgeOut]
    })
  }, [source.relationships, nodes])

  const nodeTypes = useMemo(
    (): NodeTypes => ({
      glass: EntityGlassNode,
    }),
    []
  )

  const onEdgeClick = useCallback((_evt: unknown, edge: Edge) => {
    void _evt
    void edge
  }, [])

  return (
    <ReactFlowProvider>
      <div style={{ height: 520, width: '100%', minHeight: 400 }} className="rounded-xl border border-border/70">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          proOptions={{ hideAttribution: true }}
          defaultEdgeOptions={{ type: 'default' }}
          onEdgeClick={onEdgeClick}
        >
          <Background variant={BackgroundVariant.Dots} color="rgba(34,211,238,0.12)" gap={18} />
          <MiniMap maskColor="#020617aa" />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
    </ReactFlowProvider>
  )
}
