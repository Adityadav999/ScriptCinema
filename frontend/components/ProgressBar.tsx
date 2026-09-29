'use client'

import { motion } from 'framer-motion'

interface ProgressBarProps {
  progress: number // 0–100
  className?: string
}

export default function ProgressBar({ progress, className = '' }: ProgressBarProps) {
  const clamped = Math.min(100, Math.max(0, progress))

  return (
    <div className={`w-full h-2 bg-white/10 rounded-full overflow-hidden ${className}`}>
      <motion.div
        className="h-full rounded-full relative overflow-hidden"
        style={{
          background: 'linear-gradient(90deg, #64dcb4, #dc82ff)',
        }}
        initial={{ width: 0 }}
        animate={{ width: `${clamped}%` }}
        transition={{ duration: 0.5, ease: 'easeOut' }}
      >
        {/* Shimmer overlay */}
        <motion.div
          className="absolute inset-0 bg-gradient-to-r from-transparent via-white/25 to-transparent"
          animate={{ x: ['-100%', '200%'] }}
          transition={{ duration: 1.5, repeat: Infinity, ease: 'linear' }}
        />
      </motion.div>
    </div>
  )
}
