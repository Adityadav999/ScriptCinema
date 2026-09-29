'use client'

import { useEffect, useState, useRef } from 'react'
import { useSearchParams } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import { Film, CheckCircle2, Loader2, AlertCircle, Download, ArrowLeft } from 'lucide-react'
import Link from 'next/link'
import ProgressBar from '@/components/ProgressBar'
import VideoPlayer from '@/components/VideoPlayer'

interface JobStatus {
  job_id: string
  status: 'queued' | 'running' | 'done' | 'error'
  progress: number
  scene: string | null
  video_url: string | null
  error: string | null
}

const SCENE_LABELS = [
  'Fetching repository data…',
  'Building scenes…',
  'Intro Title Card',
  'Language Breakdown',
  'File Tree Explorer',
  'Code Showcase',
  'Commit History',
  'Repository Stats',
  'Outro',
  'Encoding video…',
  'Complete',
]

export default function GeneratePage() {
  const params = useSearchParams()
  const jobId = params.get('job')
  const repoUrl = params.get('repo') || ''

  const [status, setStatus] = useState<JobStatus | null>(null)
  const [completedScenes, setCompletedScenes] = useState<string[]>([])
  const intervalRef = useRef<NodeJS.Timeout | null>(null)

  const repoName = repoUrl ? repoUrl.split('github.com/')[1] : ''

  useEffect(() => {
    if (!jobId) return

    const poll = async () => {
      try {
        const res = await fetch(`/api/status/${jobId}`)
        if (!res.ok) return
        const data: JobStatus = await res.json()
        setStatus(data)

        if (data.scene && !completedScenes.includes(data.scene)) {
          setCompletedScenes((prev) => [...prev, data.scene!])
        }

        if (data.status === 'done' || data.status === 'error') {
          if (intervalRef.current) clearInterval(intervalRef.current)
        }
      } catch {
        // Network error — keep polling
      }
    }

    poll() // immediate first poll
    intervalRef.current = setInterval(poll, 1500)
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId])

  const isDone = status?.status === 'done'
  const isError = status?.status === 'error'
  const isRunning = status?.status === 'running' || status?.status === 'queued'

  return (
    <main className="min-h-screen cinema-grid relative overflow-hidden">
      <div className="absolute top-[-200px] left-[-200px] w-[600px] h-[600px] rounded-full bg-[#64dcb4] opacity-[0.03] blur-[120px] pointer-events-none" />

      {/* Top accent */}
      <div className="h-[3px] w-full bg-gradient-to-r from-[#64dcb4] via-[#dc82ff] to-[#64dcb4]" />

      {/* Nav */}
      <nav className="flex items-center justify-between px-8 py-5 border-b border-white/5">
        <div className="flex items-center gap-2">
          <Film className="text-[#64dcb4]" size={22} />
          <span className="font-bold text-lg tracking-tight">
            Script<span className="text-[#64dcb4]">Cinema</span>
          </span>
        </div>
        <Link
          href="/"
          className="text-sm text-gray-400 hover:text-white transition-colors flex items-center gap-1.5"
        >
          <ArrowLeft size={14} />
          New video
        </Link>
      </nav>

      <div className="max-w-3xl mx-auto px-6 py-16">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-10"
        >
          <p className="text-gray-500 text-sm mb-2 font-mono">Generating video for</p>
          <h1 className="text-2xl font-bold text-[#64dcb4] truncate">
            {repoName || 'Repository'}
          </h1>
        </motion.div>

        {/* Progress section */}
        <AnimatePresence mode="wait">
          {!status && (
            <motion.div
              key="loading"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex items-center gap-3 text-gray-400 text-sm"
            >
              <Loader2 size={16} className="animate-spin" />
              Connecting to server…
            </motion.div>
          )}

          {status && !isDone && !isError && (
            <motion.div
              key="running"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="space-y-8"
            >
              {/* Current scene */}
              <div className="gradient-border rounded-xl p-6 bg-[#12141f]">
                <div className="flex items-center gap-3 mb-4">
                  <Loader2 size={18} className="text-[#64dcb4] animate-spin" />
                  <span className="text-sm text-gray-300 font-mono">
                    {status.scene || 'Starting…'}
                  </span>
                </div>
                <ProgressBar progress={status.progress} />
                <p className="text-right text-xs text-gray-500 mt-2 font-mono">
                  {status.progress}%
                </p>
              </div>

              {/* Completed scenes */}
              {completedScenes.length > 0 && (
                <div className="space-y-2">
                  <p className="text-xs text-gray-500 uppercase tracking-wider mb-3">
                    Completed Scenes
                  </p>
                  {completedScenes.map((scene, i) => (
                    <motion.div
                      key={scene}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: i * 0.05 }}
                      className="flex items-center gap-3 text-sm text-gray-400"
                    >
                      <CheckCircle2 size={14} className="text-[#64dcb4] flex-shrink-0" />
                      {scene}
                    </motion.div>
                  ))}
                </div>
              )}
            </motion.div>
          )}

          {isDone && status.video_url && (
            <motion.div
              key="done"
              initial={{ opacity: 0, scale: 0.97 }}
              animate={{ opacity: 1, scale: 1 }}
              className="space-y-6"
            >
              <div className="flex items-center gap-3 text-[#64dcb4]">
                <CheckCircle2 size={22} />
                <span className="text-lg font-semibold">Video generated successfully!</span>
              </div>

              <VideoPlayer videoUrl={status.video_url} />

              <a
                href={status.video_url}
                download={`${repoName?.replace('/', '-') || 'scriptcinema'}.mp4`}
                className="inline-flex items-center gap-2 bg-[#64dcb4] hover:bg-[#50c8a0] text-black font-semibold px-6 py-3 rounded-lg transition-colors"
              >
                <Download size={16} />
                Download MP4
              </a>
            </motion.div>
          )}

          {isError && (
            <motion.div
              key="error"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="gradient-border rounded-xl p-6 bg-[#12141f] border-red-500/20"
            >
              <div className="flex items-start gap-3">
                <AlertCircle size={18} className="text-red-400 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold text-red-400 mb-1">Generation failed</p>
                  <p className="text-sm text-gray-400">{status?.error || 'Unknown error occurred.'}</p>
                  <Link
                    href="/"
                    className="inline-block mt-4 text-sm text-[#64dcb4] hover:underline"
                  >
                    ← Try another repository
                  </Link>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </main>
  )
}
