# Forensix AI - Implementation Guide

## Overview
Forensix AI is a professional cyber forensic investigation platform with a dark forensic aesthetic (navy/red/cyan). Built with Next.js 16, React 19, and TypeScript.

## Architecture

### Core Components
- **Sidebar Navigation**: Collapsible navigation with 13 forensic investigation modules
- **Header**: Search functionality, notifications, and user profile
- **Layout System**: Fixed sidebar + header with scrollable main content area

### State Management
- **Zustand**: Global state for cases, evidence, timeline, body map data, chat messages
- **TanStack Query**: Server-side state and API data caching (ready for implementation)
- **React Context**: Theme management

### API Integration
- **Axios**: HTTP client with auto-discovery and error handling
- **Location**: `/lib/api-client.ts`
- **Features**: Typed endpoints for all forensic modules, FormData support for file uploads

## Project Structure

```
app/
├── page.tsx              # Dashboard
├── cases/
│   ├── page.tsx         # Cases list
│   └── [id]/page.tsx    # Case details
├── evidence/            # Evidence upload/storage
├── autopsy/             # Autopsy analysis
├── body-map/            # 2D interactive body map
├── body-map-full/       # Full-screen body map
├── timeline/            # Timeline with contradiction detection
├── knowledge-graph/     # Entity relationship graph
├── audio/               # Voice/audio analysis
├── risk/                # Risk assessment dashboard
├── chat/                # AI forensic chat
├── reports/             # Report generation
└── settings/            # Configuration

components/
├── sidebar.tsx          # Main navigation
├── header.tsx           # Top bar
├── layout-wrapper.tsx   # Page wrapper
├── body-map.tsx         # Interactive body visualization
└── dashboard-overview.tsx # Charts and statistics

lib/
├── api-client.ts        # API communication layer
├── store.ts             # Zustand state management
└── utils.ts             # Utility functions
```

## Design System

### Color Palette
- **Background**: Navy blue (#0f1419)
- **Primary**: Blood red (#c2185b) - Action buttons, alerts
- **Accent**: Neon cyan (#00d9ff) - Highlights, accents
- **Foreground**: Light cyan-tinted white (#e6f0fa)
- **Muted**: Gray tones (#505a74, #a8acb8)

### Typography
- **Font Family**: Geist (sans-serif)
- **Heading**: Bold, sizing based on hierarchy
- **Body**: Regular weight, 14px minimum
- **Mono**: Geist Mono for code/technical data

### Spacing & Layout
- **Grid**: 4px/8px base unit system
- **Gaps**: Flexbox with consistent gap classes
- **Borders**: 1-2px subtle borders with accent on hover
- **Shadows**: Minimal elevation through border colors

## Key Features Implemented

### 1. Dashboard
- Case statistics cards
- Evidence type distribution
- Recent cases list
- Quick action buttons
- Chart visualizations with Recharts

### 2. Case Management
- Case list with search/filter
- Case detail view with tabs
- Status tracking
- Evidence/Timeline/Analysis integration

### 3. Evidence Management
- Drag-and-drop upload interface
- Evidence list with status tracking
- File type icons and metadata
- Analysis status indicators
- Hash verification support

### 4. Autopsy Analysis
- Cause of death assessment (confidence-based)
- Time of death estimation
- Critical findings highlighting
- Toxicology tracking
- Charts for confidence intervals

### 5. 2D Body Map (Interactive)
- Canvas-based body visualization
- Multiple marking types: wounds, spatter, pose
- Click to add/select markings
- Wound description and severity levels
- Export/copy functionality
- Full editing capabilities

### 6. Timeline Analysis
- Chronological event display
- Contradiction detection (red highlighting)
- Evidence linking to events
- Confidence scoring
- Visual timeline indicator

### 7. Knowledge Graph
- Entity relationship mapping
- Connection strength indicators
- Relationship type classification
- Expandable node structure

### 8. Audio Analysis
- Voice stress level analysis
- Emotional state detection
- Keyword extraction
- Waveform visualization
- Multiple file support

### 9. Risk Assessment
- Risk factor scoring
- Overall threat level calculation
- Distribution pie chart
- Safety recommendations
- Factor-based bar chart

### 10. AI Chat Assistant
- Real-time conversation interface
- Message history
- Quick action prompts
- Async response handling
- Context awareness

### 11. Report Generation
- Multiple report types
- Generation status tracking
- File download/preview
- Report management

### 12. Settings
- User configuration
- API setup
- Security settings (2FA ready)
- Display preferences
- Advanced options

## API Endpoints (Expected)

```
Cases:
GET    /cases
GET    /cases/{id}
POST   /cases
PUT    /cases/{id}
DELETE /cases/{id}

Evidence:
GET    /evidence
POST   /evidence/upload
POST   /evidence/{id}/analyze

Autopsy:
GET    /autopsy/{caseId}
POST   /autopsy/{caseId}

Timeline:
GET    /timeline/{caseId}
POST   /timeline/{caseId}/contradictions

Knowledge Graph:
GET    /knowledge-graph/{caseId}
PUT    /knowledge-graph/{caseId}

Audio:
POST   /audio/{fileId}/analyze
GET    /audio/{fileId}/analysis

Risk:
GET    /risk/{caseId}
POST   /risk/{caseId}/calculate

Chat:
POST   /chat/{caseId}
GET    /chat/{caseId}/history

Reports:
POST   /reports/{caseId}/generate
GET    /reports/{reportId}

Body Map:
GET    /body-map/{caseId}
PUT    /body-map/{caseId}
```

## Getting Started

### Prerequisites
- Node.js 18+
- pnpm (or npm/yarn)

### Installation
```bash
pnpm install
```

### Development
```bash
pnpm dev
```

App runs at `http://localhost:3000`

### Build
```bash
pnpm build
pnpm start
```

## Component Usage

### Using the Body Map
```tsx
import { BodyMap } from '@/components/body-map'

<BodyMap 
  caseId="1"
  readOnly={false}
  onWoundsChange={(wounds) => console.log(wounds)}
/>
```

### Using the Store
```tsx
import { useForensixStore } from '@/lib/store'

const { cases, addCase, setError } = useForensixStore()
```

### Using the API Client
```tsx
import { apiClient } from '@/lib/api-client'

const cases = await apiClient.getCases()
const analysis = await apiClient.analyzeEvidence(evidenceId)
```

## Next Steps for Backend Integration

1. **Connect FastAPI Backend**:
   - Update `NEXT_PUBLIC_API_URL` environment variable
   - Implement actual API calls in components
   - Add error handling and loading states

2. **Implement Missing Features**:
   - React Flow integration for knowledge graph
   - PDF generation for reports
   - WebSocket for real-time chat
   - File upload with progress tracking

3. **Add Authentication**:
   - User login/logout
   - Session management
   - Role-based access control
   - API key management

4. **Performance Optimization**:
   - Image lazy loading
   - Code splitting by route
   - Caching strategy implementation
   - Bundle analysis

5. **Testing**:
   - Unit tests with Jest
   - Integration tests
   - E2E tests with Cypress
   - Visual regression testing

## Troubleshooting

### Dev Server Issues
- Clear `.next` folder: `rm -rf .next`
- Restart dev server: `pnpm dev`
- Check for port conflicts: `lsof -i :3000`

### Build Errors
- Ensure all imports are correct
- Check TypeScript errors: `pnpm tsc --noEmit`
- Verify environment variables are set

### Styling Issues
- Verify dark class is applied to `<html>`
- Check CSS variable names in globals.css
- Clear browser cache if colors don't update

## Support & Documentation
For detailed requirements, see: `/v0_plans/deep-design.md`
