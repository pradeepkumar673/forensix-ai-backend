import React from 'react'
import { cn } from '@/lib/utils'

interface ForensicPanelProps {
  children: React.ReactNode
  title?: string
  glow?: boolean
  className?: string
  style?: React.CSSProperties
}

export function ForensicPanel({ children, title, glow, className, style }: ForensicPanelProps) {
  return (
    <div 
      className={cn(
        "relative bg-card/85 backdrop-blur-xl border border-border rounded-[2px] p-5 shadow-2xl transition-all duration-300",
        glow && "border-primary/20 shadow-[0_0_30px_rgba(0,245,196,0.05),inset_0_1px_0_rgba(0,245,196,0.1)]",
        className
      )}
      style={style}
    >
      {/* Corner Decorations */}
      <div className="absolute top-0 left-0 w-3 h-3 border-t-2 border-l-2 border-primary" />
      <div className="absolute top-0 right-0 w-3 h-3 border-t-2 border-r-2 border-primary" />
      <div className="absolute bottom-0 left-0 w-3 h-3 border-b-2 border-l-2 border-primary" />
      <div className="absolute bottom-0 right-0 w-3 h-3 border-b-2 border-r-2 border-primary" />
      
      {title && (
        <div className="mb-4 flex items-center gap-2">
          <div className="w-[3px] h-3.5 bg-primary rounded-sm" />
          <span className="font-mono text-[10px] tracking-[0.2em] text-primary font-bold uppercase">
            {title}
          </span>
        </div>
      )}
      
      {children}
    </div>
  )
}
