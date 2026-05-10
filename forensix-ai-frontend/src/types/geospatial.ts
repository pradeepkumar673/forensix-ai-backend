/**
 * src/types/geospatial.ts
 * Shared type definitions for the Forensic Geolocation Lattice module.
 * Import these wherever you need to pass map-related data between components.
 */

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
  /** Unique identifier — use crypto.randomUUID() for manual pins */
  id: string
  lat: number
  lng: number
  /** Short display name */
  name: string
  /** Longer investigative description */
  description: string
  type: LocationType
  /**
   * Confidence score 0–100:
   *  90–100 = explicitly stated in document
   *  60–89  = strongly implied
   *  30–59  = inferred / contextual
   *  <30    = speculative / generated
   */
  confidence: number
  /** The raw text or reasoning that produced this pin */
  extractedFrom?: string
  /** ISO-8601 timestamp if known */
  timestamp?: string
  /** true when added by the investigator via the UI, not by LLM */
  manual?: boolean
}

export interface MapState {
  pins: ForensicPin[]
  center: [number, number]
  zoom: number
}

export type TileProvider = 'carto-dark' | 'osm' | 'esri-satellite'

export const TILE_URLS: Record<TileProvider, { url: string; attribution: string }> = {
  'carto-dark': {
    url: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    attribution: '&copy; <a href="https://carto.com/">CARTO</a> &copy; OpenStreetMap contributors',
  },
  osm: {
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; <a href="https://openstreetmap.org">OpenStreetMap</a> contributors',
  },
  'esri-satellite': {
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: '&copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics',
  },
}
