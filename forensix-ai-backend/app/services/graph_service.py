"""
app/services/graph_service.py
------------------------------
Forensic knowledge graph (entity-relationship) service.

Responsibilities:
  • Extract named entities (persons, locations, organisations, weapons,
    vehicles, substances, phones, documents) from case evidence text
  • Build a directed relationship graph between those entities
  • Compute graph-theoretic metrics (degree centrality, betweenness centrality,
    PageRank) to surface key actors and locations
  • Detect communities / cliques (suspect groups, alibi networks)
  • Serialise the graph to pyvis-compatible HTML for frontend visualisation
  • Export to NetworkX DiGraph for further analysis

Public functions:
  extract_entities(text, model)                         → list[dict]
  build_entity_graph(entities_raw, relationships_raw,
                     case_id, context, model)           → EntityGraphResponse
  compute_graph_metrics(graph_response)                 → dict
  render_graph_html(graph_response)                     → str  (pyvis HTML)
  merge_graphs(graph_a, graph_b)                        → EntityGraphResponse
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid as uuid_lib
from typing import Any
from uuid import UUID, uuid4

import httpx
import networkx as nx

from app.core.config import get_settings
from app.schemas.analysis import (
    AIModelMeta,
    ConfidenceScore,
    EntityGraphResponse,
    EntityType,
    GraphEntity,
    GraphRelationship,
)

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Constants                                                                     #
# --------------------------------------------------------------------------- #

# Risk score colour bands for pyvis visualisation
_RISK_COLORS: list[tuple[float, str]] = [
    (80.0, "#e74c3c"),   # critical  — red
    (60.0, "#e67e22"),   # high      — orange
    (40.0, "#f1c40f"),   # moderate  — yellow
    (20.0, "#2ecc71"),   # low       — green
    (0.0,  "#3498db"),   # minimal   — blue
]

# Entity-type → node shape for pyvis
_ENTITY_SHAPES: dict[str, str] = {
    "person":       "dot",
    "location":     "square",
    "organisation": "triangle",
    "weapon":       "star",
    "vehicle":      "diamond",
    "substance":    "triangleDown",
    "phone":        "dot",
    "document":     "box",
    "other":        "ellipse",
}

# --------------------------------------------------------------------------- #
# Internal helpers                                                              #
# --------------------------------------------------------------------------- #

def _settings():
    return get_settings()


def _ollama_url() -> str:
    return f"{_settings().OLLAMA_BASE_URL}/api/generate"


def _make_confidence(score: float) -> ConfidenceScore:
    return ConfidenceScore.from_float(max(0.0, min(1.0, score)))


def _extract_json_block(text: str) -> Any:
    tag_match = re.search(r"<json>(.*?)</json>", text, re.DOTALL | re.IGNORECASE)
    if tag_match:
        return json.loads(tag_match.group(1).strip())

    fence_match = re.search(r"```(?:json)?\s*([\[\{].*?[\]\}])\s*```", text, re.DOTALL)
    if fence_match:
        return json.loads(fence_match.group(1).strip())

    bare_match = re.search(r"([\[\{].*[\]\}])", text, re.DOTALL)
    if bare_match:
        return json.loads(bare_match.group(1).strip())

    raise ValueError(f"No valid JSON found in model response:\n{text[:400]}")


async def _call_ollama(
    prompt: str,
    model: str | None = None,
    system: str | None = None,
    temperature: float = 0.1,
    max_tokens: int = 4096,
    timeout: float = 180.0,
) -> tuple[str, int]:
    """Async POST to Ollama. Returns (response_text, inference_ms)."""
    mdl = model or _settings().OLLAMA_MODEL
    payload: dict[str, Any] = {
        "model":   mdl,
        "prompt":  prompt,
        "stream":  False,
        "options": {
            "temperature":    temperature,
            "num_predict":    max_tokens,
            "top_p":          0.9,
            "repeat_penalty": 1.1,
        },
    }
    if system:
        payload["system"] = system

    t0 = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(_ollama_url(), json=payload)
            resp.raise_for_status()
    except httpx.ConnectError as exc:
        raise RuntimeError(
            f"Cannot reach Ollama at {_settings().OLLAMA_BASE_URL}"
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            f"Ollama HTTP {exc.response.status_code}: {exc.response.text[:200]}"
        ) from exc

    inference_ms = round((time.perf_counter() - t0) * 1000)
    return resp.json().get("response", ""), inference_ms


# --------------------------------------------------------------------------- #
# System & prompt templates                                                     #
# --------------------------------------------------------------------------- #

_GRAPH_SYSTEM_PROMPT = """
You are ARIA, a forensic intelligence analyst specialised in entity-relationship
extraction and link analysis.

Your task: extract entities and relationships from forensic evidence and build
a structured knowledge graph suitable for criminal intelligence analysis.

Extraction rules:
  1. Extract EVERY named entity — persons (suspects, victims, witnesses, officers),
     locations, organisations, weapons, vehicles, substances, phone numbers,
     documents, and digital accounts.
  2. For each entity, estimate a risk_score (0–100) indicating its centrality
     to the crime (0 = peripheral, 100 = primary suspect / crime scene).
  3. Infer relationships from context — explicit and implicit.  Label with
     standard criminal-intelligence relation types (KNOWS, LIVES_AT, OWNS,
     CALLED, WITNESSED, PRESENT_AT, SUSPECT_OF, VICTIM_OF, EMPLOYED_BY,
     ASSOCIATE_OF, FLED_TO, etc.).
  4. Assign confidence scores (0.0–1.0) to every entity and relationship.
  5. ALWAYS respond with valid JSON wrapped in <json>…</json> tags only.
""".strip()


_EXTRACT_ENTITIES_PROMPT = """
## FORENSIC ENTITY EXTRACTION

Extract all forensic entities and their relationships from the following text.

### Evidence Text
{text}

Return ONLY this JSON inside <json>…</json> tags:

<json>
{{
  "entities": [
    {{
      "entity_id":    "<uuid-v4>",
      "entity_type":  "<person|location|organisation|weapon|vehicle|substance|phone|document|other>",
      "label":        "<display name>",
      "attributes":   {{
        "aliases":          ["<string>"],
        "description":      "<string>",
        "role":             "<victim|suspect|witness|officer|expert|unknown>",
        "known_addresses":  ["<string>"],
        "phone_numbers":    ["<string>"],
        "date_of_birth":    "<string or null>",
        "physical_desc":    "<string or null>"
      }},
      "risk_score":   <0-100>,
      "confidence":   <0.0-1.0>
    }}
  ],
  "relationships": [
    {{
      "relationship_id": "<uuid-v4>",
      "source_id":       "<entity_id>",
      "target_id":       "<entity_id>",
      "relation_type":   "<KNOWS|LIVES_AT|OWNS|CALLED|WITNESSED|PRESENT_AT|SUSPECT_OF|VICTIM_OF|EMPLOYED_BY|ASSOCIATE_OF|FLED_TO|PURCHASED|USED|OTHER>",
      "strength":        <0.0-1.0>,
      "temporal_context":"<string or null>",
      "evidence_refs":   ["<string>"],
      "confidence":      <0.0-1.0>
    }}
  ],
  "extraction_notes": "<caveats or ambiguities>",
  "overall_confidence": <0.0-1.0>
}}
</json>
"""


_BUILD_GRAPH_PROMPT = """
## FORENSIC KNOWLEDGE GRAPH CONSTRUCTION

You are synthesising a knowledge graph from multiple entity sets extracted from
different evidence sources.  Your task is to:
  1. Deduplicate entities that refer to the same real-world person / place / thing
     (merge by label similarity and attribute overlap).
  2. Merge duplicate or conflicting relationships.
  3. Infer any additional relationships implied by the combined entity set.
  4. Identify the most central entities (suspects, primary locations).
  5. Identify likely suspect entities (highest risk_score + most relationships
     of type SUSPECT_OF / PRESENT_AT / OWNS).
  6. Write a narrative summary of the relationship network.

### Case Context
{context}

### Combined Entity & Relationship Data
{data_json}

Return ONLY this JSON inside <json>…</json> tags:

<json>
{{
  "entities": [
    {{
      "entity_id":    "<uuid-v4>",
      "entity_type":  "<type>",
      "label":        "<string>",
      "attributes":   {{}},
      "risk_score":   <0-100>,
      "confidence":   <0.0-1.0>
    }}
  ],
  "relationships": [
    {{
      "relationship_id": "<uuid-v4>",
      "source_id":       "<entity_id>",
      "target_id":       "<entity_id>",
      "relation_type":   "<string>",
      "strength":        <0.0-1.0>,
      "temporal_context":"<string or null>",
      "evidence_refs":   ["<string>"],
      "confidence":      <0.0-1.0>
    }}
  ],
  "central_entity_ids":  ["<entity_id>"],
  "suspect_entity_ids":  ["<entity_id>"],
  "narrative_summary":   "<300-word plain-language summary of the relationship network>",
  "overall_confidence":  <0.0-1.0>
}}
</json>
"""

# --------------------------------------------------------------------------- #
# Internal parsers                                                              #
# --------------------------------------------------------------------------- #

def _parse_entity_type(raw: str) -> EntityType:
    try:
        return EntityType(raw.lower())
    except ValueError:
        return EntityType.OTHER


def _dict_to_entity(raw: dict[str, Any]) -> GraphEntity:
    try:
        eid = UUID(raw.get("entity_id", ""))
    except (ValueError, AttributeError):
        eid = uuid4()

    return GraphEntity(
        entity_id   = eid,
        entity_type = _parse_entity_type(raw.get("entity_type", "other")),
        label       = raw.get("label", "Unknown"),
        attributes  = raw.get("attributes", {}),
        risk_score  = raw.get("risk_score"),
        confidence  = _make_confidence(raw.get("confidence", 0.5)),
    )


def _dict_to_relationship(raw: dict[str, Any]) -> GraphRelationship | None:
    """Return None if source_id / target_id cannot be parsed as valid UUIDs."""
    try:
        rid = UUID(raw.get("relationship_id", ""))
    except (ValueError, AttributeError):
        rid = uuid4()

    try:
        source_id = UUID(raw["source_id"])
        target_id = UUID(raw["target_id"])
    except (KeyError, ValueError, AttributeError):
        return None   # cannot build edge without valid node references

    return GraphRelationship(
        relationship_id  = rid,
        source_id        = source_id,
        target_id        = target_id,
        relation_type    = raw.get("relation_type", "OTHER"),
        strength         = float(raw.get("strength", 0.5)),
        evidence_refs    = raw.get("evidence_refs", []),
        temporal_context = raw.get("temporal_context"),
        confidence       = _make_confidence(raw.get("confidence", 0.5)),
    )


def _parse_uuid_list(raw_list: list) -> list[UUID]:
    result: list[UUID] = []
    for item in raw_list:
        try:
            result.append(UUID(item))
        except (ValueError, AttributeError):
            pass
    return result


# --------------------------------------------------------------------------- #
# Public API                                                                    #
# --------------------------------------------------------------------------- #

async def _llm_extract_entities_chunk(
    source_text: str,
    model: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    prompt = _EXTRACT_ENTITIES_PROMPT.format(text=source_text)
    response_text, inference_ms = await _call_ollama(
        prompt=prompt,
        model=model,
        system=_GRAPH_SYSTEM_PROMPT,
        temperature=0.05,
        max_tokens=5000,
    )
    try:
        parsed = _extract_json_block(response_text)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.error("Entity extraction JSON parse failure: %s", exc)
        raise ValueError(
            f"LLM did not return valid JSON for entity extraction.\n"
            f"Raw response (first 400 chars):\n{response_text[:400]}"
        ) from exc
    entities = parsed.get("entities", [])
    relationships = parsed.get("relationships", [])
    return entities, relationships, inference_ms


async def extract_entities(
    text:  str,
    model: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Extract entities and relationships from any forensic evidence text.

    Parameters
    ----------
    text  : Raw or cleaned text (autopsy report, statement, police report, etc.)
    model : Ollama model tag.

    Returns
    -------
    (entities_raw, relationships_raw) — two lists of plain dicts as returned
    by the LLM.  Pass these directly to build_entity_graph().

    Raises
    ------
    RuntimeError : If the Ollama server is unreachable.
    ValueError   : If the LLM output cannot be parsed.
    """
    if not text or not text.strip():
        raise ValueError("text must be a non-empty string")

    max_chars = 10_000
    truncated = len(text) > max_chars
    source_text = text[:max_chars] + ("\n\n[TRUNCATED]" if truncated else "")

    primary = model or _settings().OLLAMA_MODEL
    fallback = (_settings().OLLAMA_FALLBACK_MODEL or "").strip()

    try:
        entities, relationships, inference_ms = await _llm_extract_entities_chunk(source_text, primary)
    except (RuntimeError, ValueError) as exc:
        logger.warning("Entity extract failed model=%s: %s", primary, exc)
        if not fallback or fallback == primary:
            raise
        entities, relationships, inference_ms = await _llm_extract_entities_chunk(source_text, fallback)

    logger.info(
        "Extracted %d entities, %d relationships from text (%d chars) in %d ms",
        len(entities), len(relationships), len(text), inference_ms,
    )
    return entities, relationships


async def build_entity_graph(
    entities_raw:      list[dict[str, Any]],
    relationships_raw: list[dict[str, Any]],
    case_id:           UUID | None = None,
    context:           str = "",
    model:             str | None = None,
) -> EntityGraphResponse:
    """
    Build and synthesise a full EntityGraphResponse from raw entity/relationship dicts.

    The LLM is used to deduplicate entities, infer missing relationships, and
    identify central / suspect entities.

    Parameters
    ----------
    entities_raw      : List of entity dicts from extract_entities().
    relationships_raw : List of relationship dicts from extract_entities().
    case_id           : UUID of the parent case.
    context           : Brief case context for the LLM.
    model             : Ollama model tag.

    Returns
    -------
    EntityGraphResponse — fully populated schema object.

    Raises
    ------
    RuntimeError : If the Ollama server is unreachable.
    ValueError   : If the LLM output cannot be parsed.
    """
    if not entities_raw:
        raise ValueError("entities_raw must be a non-empty list")

    if case_id is None:
        case_id = uuid4()

    combined_data = {
        "entities":      entities_raw[:80],     # cap to avoid token overflow
        "relationships": relationships_raw[:150],
    }

    prompt = _BUILD_GRAPH_PROMPT.format(
        context  = context or "No additional context provided.",
        data_json= json.dumps(combined_data, indent=2, default=str)[:14_000],
    )

    primary = model or _settings().OLLAMA_MODEL
    fallback = (_settings().OLLAMA_FALLBACK_MODEL or "").strip()

    async def _llm_graph_merge(m: str) -> tuple[dict[str, Any], int]:
        response_text, inference_ms = await _call_ollama(
            prompt=prompt,
            model=m,
            system=_GRAPH_SYSTEM_PROMPT,
            temperature=0.05,
            max_tokens=6000,
        )
        try:
            parsed = _extract_json_block(response_text)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.error("Graph build JSON parse failure: %s", exc)
            raise ValueError(
                f"LLM did not return valid JSON for graph construction.\n"
                f"Raw response (first 400 chars):\n{response_text[:400]}"
            ) from exc
        return parsed, inference_ms

    try:
        parsed, inference_ms = await _llm_graph_merge(primary)
        used_model = primary
    except (RuntimeError, ValueError) as exc:
        logger.warning("Graph build failed model=%s: %s", primary, exc)
        if not fallback or fallback == primary:
            raise
        parsed, inference_ms = await _llm_graph_merge(fallback)
        used_model = fallback

    # ── Convert dicts → schema objects ─────────────────────────────────────── #
    entities: list[GraphEntity] = []
    for raw in parsed.get("entities", []):
        try:
            entities.append(_dict_to_entity(raw))
        except Exception as e:
            logger.warning("Skipping malformed entity: %s — %s", raw, e)

    relationships: list[GraphRelationship] = []
    for raw in parsed.get("relationships", []):
        rel = _dict_to_relationship(raw)
        if rel:
            relationships.append(rel)
        else:
            logger.warning("Skipping relationship with invalid node refs: %s", raw)

    central_ids = _parse_uuid_list(parsed.get("central_entity_ids", []))
    suspect_ids = _parse_uuid_list(parsed.get("suspect_entity_ids", []))

    logger.info(
        "Built graph: %d entities, %d relationships, %d central, %d suspects in %d ms",
        len(entities), len(relationships),
        len(central_ids), len(suspect_ids), inference_ms,
    )

    return EntityGraphResponse(
        case_id            = case_id,
        entities           = entities,
        relationships      = relationships,
        central_entities   = central_ids,
        suspect_entities   = suspect_ids,
        narrative_summary  = parsed.get(
            "narrative_summary",
            "Entity relationship graph constructed from available evidence.",
        ),
        model_meta = AIModelMeta(
            model_name   = used_model,
            inference_ms = inference_ms,
        ),
    )


def compute_graph_metrics(
    graph_response: EntityGraphResponse,
) -> dict[str, Any]:
    """
    Compute graph-theoretic metrics on an EntityGraphResponse using NetworkX.

    Metrics computed:
      • degree_centrality         — normalised node degree
      • betweenness_centrality    — importance as a bridge between clusters
      • pagerank                  — recursive importance / influence score
      • in_degree / out_degree    — directional edge counts per node
      • density                   — ratio of actual to possible edges
      • strongly_connected_components — groups of mutually reachable nodes
      • top_5_by_betweenness      — highest-betweenness entity labels

    Parameters
    ----------
    graph_response : EntityGraphResponse to analyse.

    Returns
    -------
    dict with metric keys described above, keyed by entity_id (str).
    """
    # ── Build NetworkX DiGraph ─────────────────────────────────────────────── #
    G = nx.DiGraph()

    entity_map: dict[str, str] = {}   # entity_id → label
    for entity in graph_response.entities:
        eid = str(entity.entity_id)
        G.add_node(eid, label=entity.label, entity_type=entity.entity_type.value)
        entity_map[eid] = entity.label

    for rel in graph_response.relationships:
        src = str(rel.source_id)
        tgt = str(rel.target_id)
        if src in G and tgt in G:
            G.add_edge(
                src, tgt,
                relation_type=rel.relation_type,
                strength=rel.strength,
                weight=rel.strength,
            )

    if G.number_of_nodes() == 0:
        return {"error": "Graph has no nodes."}

    # ── Compute metrics ────────────────────────────────────────────────────── #
    degree_centrality      = nx.degree_centrality(G)
    betweenness_centrality = nx.betweenness_centrality(G, weight="weight", normalized=True)
    pagerank               = nx.pagerank(G, weight="weight") if G.number_of_edges() > 0 else {}

    in_degree  = dict(G.in_degree())
    out_degree = dict(G.out_degree())
    density    = nx.density(G)

    # Strongly connected components (groups of mutually reachable nodes)
    scc = [
        sorted(component, key=lambda n: entity_map.get(n, n))
        for component in nx.strongly_connected_components(G)
        if len(component) > 1   # only non-trivial SCCs
    ]

    # Top 5 entities by betweenness (sorted descending)
    top_5 = sorted(
        betweenness_centrality.items(),
        key=lambda x: x[1],
        reverse=True,
    )[:5]
    top_5_labelled = [
        {"entity_id": eid, "label": entity_map.get(eid, eid), "betweenness": round(score, 4)}
        for eid, score in top_5
    ]

    return {
        "node_count":                G.number_of_nodes(),
        "edge_count":                G.number_of_edges(),
        "density":                   round(density, 4),
        "degree_centrality":         {k: round(v, 4) for k, v in degree_centrality.items()},
        "betweenness_centrality":    {k: round(v, 4) for k, v in betweenness_centrality.items()},
        "pagerank":                  {k: round(v, 6) for k, v in pagerank.items()},
        "in_degree":                 in_degree,
        "out_degree":                out_degree,
        "strongly_connected_components": scc,
        "top_5_by_betweenness":      top_5_labelled,
    }


def render_graph_html(
    graph_response: EntityGraphResponse,
    height:         str = "750px",
    width:          str = "100%",
    bgcolor:        str = "#0d1117",
    font_color:     str = "#c9d1d9",
) -> str:
    """
    Render the entity-relationship graph as a standalone pyvis HTML string.

    The HTML string can be:
      • Written to a .html file and served statically
      • Returned directly in an API response (Base64-encoded or as HTML)
      • Embedded in a React frontend via an <iframe> or dangerouslySetInnerHTML

    Node styling:
      • Colour    → risk_score band (red = high risk, blue = low)
      • Shape     → entity_type  (person = dot, location = square, …)
      • Size      → degree (more connections = larger node)
      • Label     → entity label

    Parameters
    ----------
    graph_response : EntityGraphResponse to render.
    height         : CSS height of the network canvas.
    width          : CSS width of the network canvas.
    bgcolor        : Canvas background colour.
    font_color     : Default font colour for node labels.

    Returns
    -------
    Full standalone HTML as a string.

    Raises
    ------
    ImportError : If pyvis is not installed.
    """
    try:
        from pyvis.network import Network
    except ImportError as exc:
        raise ImportError(
            "pyvis is required for graph rendering. "
            "Install it with: pip install pyvis"
        ) from exc

    net = Network(
        height       = height,
        width        = width,
        bgcolor      = bgcolor,
        font_color   = font_color,
        directed     = True,
        notebook     = False,
    )
    net.barnes_hut(
        gravity=-8000,
        central_gravity=0.3,
        spring_length=200,
        spring_strength=0.04,
        damping=0.09,
    )

    # Build a quick degree map from relationships
    degree_map: dict[str, int] = {}
    for rel in graph_response.relationships:
        src = str(rel.source_id)
        tgt = str(rel.target_id)
        degree_map[src] = degree_map.get(src, 0) + 1
        degree_map[tgt] = degree_map.get(tgt, 0) + 1

    # ── Add nodes ─────────────────────────────────────────────────────────── #
    for entity in graph_response.entities:
        eid       = str(entity.entity_id)
        risk      = entity.risk_score or 0.0
        node_size = 15 + min(degree_map.get(eid, 0) * 4, 40)

        # Pick colour from risk band
        colour = "#3498db"
        for threshold, col in _RISK_COLORS:
            if risk >= threshold:
                colour = col
                break

        shape = _ENTITY_SHAPES.get(entity.entity_type.value, "ellipse")

        # Bold suspects and central entities
        is_suspect  = entity.entity_id in graph_response.suspect_entities
        is_central  = entity.entity_id in graph_response.central_entities
        font_weight = "bold" if (is_suspect or is_central) else "normal"
        border_width = 3 if is_suspect else 1

        # Build hover tooltip
        attrs = entity.attributes or {}
        tooltip_lines = [
            f"<b>{entity.label}</b>",
            f"Type: {entity.entity_type.value}",
            f"Risk: {int(risk)}/100",
            f"Confidence: {entity.confidence.score:.0%}",
        ]
        if attrs.get("role"):
            tooltip_lines.append(f"Role: {attrs['role']}")
        if attrs.get("description"):
            tooltip_lines.append(f"Desc: {attrs['description'][:120]}")
        if is_suspect:
            tooltip_lines.append("⚠️ SUSPECT ENTITY")
        if is_central:
            tooltip_lines.append("🎯 CENTRAL ENTITY")

        net.add_node(
            n_id        = eid,
            label       = entity.label,
            title       = "<br>".join(tooltip_lines),
            color       = colour,
            size        = node_size,
            shape       = shape,
            borderWidth = border_width,
            font        = {"color": font_color, "bold": is_suspect},
        )

    # ── Add edges ─────────────────────────────────────────────────────────── #
    for rel in graph_response.relationships:
        src = str(rel.source_id)
        tgt = str(rel.target_id)

        # Width proportional to strength
        edge_width = max(1, int(rel.strength * 5))

        edge_tooltip = (
            f"<b>{rel.relation_type}</b><br>"
            f"Strength: {rel.strength:.0%}<br>"
            f"Confidence: {rel.confidence.score:.0%}"
        )
        if rel.temporal_context:
            edge_tooltip += f"<br>When: {rel.temporal_context}"

        try:
            net.add_edge(
                source = src,
                to     = tgt,
                label  = rel.relation_type,
                title  = edge_tooltip,
                width  = edge_width,
                color  = {"color": "#555", "highlight": "#e74c3c"},
                arrows = "to",
            )
        except Exception as e:
            logger.warning("Skipping edge %s→%s: %s", src, tgt, e)

    return net.generate_html()


def merge_graphs(
    graph_a: EntityGraphResponse,
    graph_b: EntityGraphResponse,
) -> EntityGraphResponse:
    """
    Merge two EntityGraphResponse objects into one.

    Entities with the same entity_id are deduplicated (graph_a takes precedence).
    Relationships are unioned; duplicates (same source+target+relation_type)
    are also deduplicated.

    Parameters
    ----------
    graph_a : Primary graph (takes precedence in deduplication).
    graph_b : Secondary graph to merge in.

    Returns
    -------
    New EntityGraphResponse containing the merged graph.

    Note: The merged graph inherits graph_a's case_id and narrative_summary.
    The caller is responsible for re-running build_entity_graph() or
    compute_graph_metrics() on the merged result if fresh analysis is needed.
    """
    # Merge entities
    entity_map: dict[UUID, GraphEntity] = {e.entity_id: e for e in graph_a.entities}
    for entity in graph_b.entities:
        if entity.entity_id not in entity_map:
            entity_map[entity.entity_id] = entity

    # Merge relationships (deduplicate on source+target+relation_type)
    rel_key = lambda r: (r.source_id, r.target_id, r.relation_type)
    rel_map: dict[tuple, GraphRelationship] = {rel_key(r): r for r in graph_a.relationships}
    for rel in graph_b.relationships:
        if rel_key(rel) not in rel_map:
            rel_map[rel_key(rel)] = rel

    # Merge central / suspect entity lists
    central = list(set(graph_a.central_entities + graph_b.central_entities))
    suspects= list(set(graph_a.suspect_entities + graph_b.suspect_entities))

    merged_entities      = list(entity_map.values())
    merged_relationships = list(rel_map.values())

    return EntityGraphResponse(
        case_id           = graph_a.case_id,
        entities          = merged_entities,
        relationships     = merged_relationships,
        central_entities  = central,
        suspect_entities  = suspects,
        narrative_summary = (
            f"[MERGED GRAPH]\n"
            f"Graph A: {graph_a.narrative_summary[:400]}\n\n"
            f"Graph B: {graph_b.narrative_summary[:400]}"
        ),
        model_meta = graph_a.model_meta,
    )
