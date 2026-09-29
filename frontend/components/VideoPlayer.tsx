'use client'

import { useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { Play, Pause, Maximize2 } from 'lucide-react'

interface VideoPlayerProps {
  videoUrl: string
}

export default function VideoPlayer({ videoUrl }: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const [playing, setPlaying] = useState(false)
  const [progress, setProgress] = useState(0)

  const togglePlay = () => {
    const v = videoRef.current
    if (!v) return
    if (v.paused) {
      v.play()
      setPlaying(true)
    } else {
      v.pause()
      setPlaying(false)
    }
  }

  const handleTimeUpdate = () => {
    const v = videoRef.current
    if (!v || !v.duration) return
    setProgress((v.currentTime / v.duration) * 100)
  }

  const handleEnded = () => setPlaying(false)

  const seek = (e: React.MouseEvent<HTMLDivElement>) => {
    const v = videoRef.current
    if (!v) return
    const rect = e.currentTarget.getBoundingClientRect()
    const pct = (e.clientX - rect.left) / rect.width
    v.currentTime = pct * v.duration
  }

  const fullscreen = () => {
    videoRef.current?.requestFullscreen?.()
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-xl overflow-hidden border border-white/10 bg-black group relative"
      style={{ aspectRatio: '16/9' }}
    >
      {/* Video element */}
      <video
        ref={videoRef}
        src={videoUrl}
        onTimeUpdate={handleTimeUpdate}
        onEnded={handleEnded}
        onClick={togglePlay}
        className="w-full h-full object-cover cursor-pointer"
        preload="metadata"
      />

      {/* Controls overlay */}
      <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 via-black/30 to-transparent p-4 opacity-0 group-hover:opacity-100 transition-opacity">
        {/* Progress bar */}
        <div
          className="w-full h-1.5 bg-white/20 rounded-full mb-3 cursor-pointer"
          onClick={seek}
        >
          <div
            className="h-full bg-gradient-to-r from-[#64dcb4] to-[#dc82ff] rounded-full transition-all"
            style={{ width: `${progress}%` }}
          />
        </div>

        {/* Buttons */}
        <div className="flex items-center gap-3">
          <button
            onClick={togglePlay}
            className="text-white hover:text-[#64dcb4] transition-colors"
          >
            {playing ? <Pause size={18} /> : <Play size={18} />}
          </button>

          <div className="flex-1" />

          <button
            onClick={fullscreen}
            className="text-white hover:text-[#64dcb4] transition-colors"
          >
            <Maximize2 size={16} />
          </button>
        </div>
      </div>

      {/* Big play button when paused */}
      {!playing && (
        <div
          className="absolute inset-0 flex items-center justify-center cursor-pointer"
          onClick={togglePlay}
        >
          <motion.div
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.95 }}
            className="w-16 h-16 rounded-full bg-[#64dcb4]/90 flex items-center justify-center"
          >
            <Play size={28} className="text-black ml-1" fill="black" />
          </motion.div>
        </div>
      )}
    </motion.div>
  )
}
