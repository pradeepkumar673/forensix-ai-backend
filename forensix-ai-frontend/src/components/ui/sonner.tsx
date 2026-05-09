import * as React from 'react'

import type { ToasterProps } from 'sonner'

import { Toaster as Sonner } from 'sonner'

/** Dark forensic shell only — aligns with mandated premium lab UI. */
const Toaster = ({ ...props }: ToasterProps) => {
  return (
    <Sonner
      theme="dark"
      className="toaster group"
      style={
        {
          '--normal-bg': 'var(--popover)',
          '--normal-text': 'var(--popover-foreground)',
          '--normal-border': 'var(--border)',
        } as React.CSSProperties
      }
      {...props}
    />
  )
}

export { Toaster }
