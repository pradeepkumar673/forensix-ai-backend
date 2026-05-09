import '@xyflow/react/dist/style.css'
import { useCallback, useMemo } from 'react'
import {
  Background,
  Controls,
  Edge,
  MarkerType,
  MiniMap,
  Node,
  Panel,
  ReactFlow,
  useEdgesState,
  useNodesState,
} from '@xyflow/react'

type GraphEntity = {
  entity_id: string
  entity_type: string
  label: string
  risk_score?: number | null
}

type GraphRelationship = {
  source_id: string
  target_id: string
  relation_type: string
  strength?: number
}

/** Maps backend EntityGraphResponse shards into an interactive React Flow canvas. */
export function KnowledgeGraphBoard({
  entities,
  relationships,
}: {
  entities: GraphEntity[]
  relationships: GraphRelationship[]
}) {
  const initialNodes: Node[] = useMemo(() => {
    const cols = Math.ceil(Math.sqrt(Math.max(entities.length, 1)))
    return entities.map((e, i) => {
      const col = i % cols
      const row = Math.floor(i / cols)
      const risk = e.risk_score ?? 0
      const accent =
        risk > 75 ? '#ef4444' : risk > 45 ? '#f59e0b' : risk > 20 ? '#38bdf8' : '#22c55e'
      return {
        id: e.entity_id,
        position: { x: col * 240 + 40, y: row * 140 + 40 },
        data: {
          label: e.label,
          type: e.entity_type,
        },
        style: {
          background: 'rgba(10,20,40,0.92)',
          border: `1px solid ${accent}`,
          color: '#e8eef7',
          fontFamily: 'JetBrains Mono, monospace',
          fontSize: 11,
          padding: 12,
          borderRadius: 12,
          minWidth: 160,
          boxShadow: `0 0 28px ${accent}33`,
        },
      }
    })
  }, [entities])

  const initialEdges: Edge[] = useMemo(
    () =>
      relationships.map((r, i) => ({
        id: `${r.source_id}-${r.target_id}-${i}`,
        source: r.source_id,
        target: r.target_id,
        label: r.relation_type,
        animated: true,
        style: { stroke: 'rgba(0,245,255,0.45)', strokeWidth: 1 + (r.strength ?? 0.5) },
        markerEnd: { type: MarkerType.ArrowClosed, color: 'rgba(0,245,255,0.55)' },
      })),
    [relationships],
  )

  const [nodes, , onNodesChange] = useNodesState(initialNodes)
  const [edges, , onEdgesChange] = useEdgesState(initialEdges)

  const onNodeClick = useCallback(() => {
    /* reserved — inspector hooks */
  }, [])

  return (
    <div className="h-[520px] w-full overflow-hidden rounded-2xl border border-primary/20 bg-[#050a18]/80 holo-ring">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        fitView
        proOptions={{ hideAttribution: true }}
        className="bg-transparent"
      >
        <MiniMap
          className="!bg-card/90 !border !border-primary/20"
          maskColor="rgba(5,10,24,0.65)"
        />
        <Controls className="!border-primary/25 !bg-card/90 [&_button]:!fill-primary" />
        <Background gap={22} size={1} color="rgba(0,245,255,0.07)" />
        <Panel position="top-left" className="rounded-lg border border-primary/20 bg-background/80 px-3 py-1 font-mono text-[10px] uppercase tracking-[0.24em] text-primary">
          Entity lattice · classified
        </Panel>
      </ReactFlow>
    </div>
  )
}
