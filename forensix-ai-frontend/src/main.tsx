import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { RouterProvider } from 'react-router-dom'
import { AppProviders } from '@/app/providers'
import { router } from '@/app/router'
import './index.css'
import 'leaflet/dist/leaflet.css'
import L from 'leaflet'
import iconUrl from 'leaflet/dist/images/marker-icon.png'
import iconRetinaUrl from 'leaflet/dist/images/marker-icon-2x.png'
import shadowUrl from 'leaflet/dist/images/marker-shadow.png'

// Overwrite the default icon so Vite can resolve the asset paths
delete (L.Icon.Default.prototype as any)._getIconUrl
L.Icon.Default.mergeOptions({ iconUrl, iconRetinaUrl, shadowUrl })

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AppProviders>
      <RouterProvider
        router={router}
        future={{ v7_startTransition: true }}
      />
    </AppProviders>
  </StrictMode>,
)
