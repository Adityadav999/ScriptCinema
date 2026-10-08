'use client'

import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Film, CheckCircle2, Loader2, AlertCircle,
  Download, ArrowLeft, GitBranch, Monitor, Cpu, Video,
} from 'lucide-react'
import Link from 'next/link'
import ProgressBar from '@/components/ProgressBar'
import VideoPlayer from '@/components/VideoPlayer'

interface JobStatus {
  job_id: string
  status: 'queued' | 'running' | 'done' | 'error'
  progress: number
  step: string | null
  video_url: string | null
  error: string | null
}

// Map progress % ranges to pipeline stage icons
function getStageIcon(progress: number) {
  if (progress < 15)  return <GitBranch size={16} className="text-[#64dcb4]" />
  if (progress < 50)  return <Cpu size={16} className="text-[#dc82ff]" />
  if (progress < 65)  return <Monitor size={16} className="text-amber-400" />
  if (progress < 78)  return <Video size={16} className="text-blue-400" />
  return <Film size={16} className="text-[#64dcb4]" />
}

const PIPELINE_STAGES = [
  { label: 'Clone repository',        icon: GitBranch,  range: [0,  15]  },
  { label: 'Detect & install stack',  icon: Cpu,        range: [15, 60]  },
  { label: 'Start & verify server',   icon: Monitor,    range: [60, 65]  },
  { label: 'Record browser session',  icon: Video,      range: [65, 78]  },
  { label: 'Render cinematic video',  icon: Film,       range: [78, 100] },
]

export default function GeneratePage() {
  const params   = useSearchParams()
  const jobId    = params.get('job')
  const repoUrl  = params.get('repo') || ''
  const repoName = repoUrl.split('github.com/')[1] || ''

  const [status, setStatus]               = useState<JobStatus | null>(null)
  const [completedSteps, setCompletedSteps] = useState<string[]>([])
  const seenSteps   = useRef<Set<string>>(new Set())
  const prevStep    = useRef<string | null>(null)
  const intervalRef = useRef<NodeJS.Timeout | null>(null)

  useEffect(() => {
    if (!jobId) return

    const poll = async () => {
      try {
        const res  = await fetch(`/api/status/${jobId}`)
        if (!res.ok) return
        const data: JobStatus = await res.json()
        setStatus(data)

        // Track completed steps (transition from one step to the next)
        const cur = data.step
        if (
          cur &&
          prevStep.current !== null &&
          prevStep.current !== cur &&
          !seenSteps.current.has(prevStep.current)
        ) {
          seenSteps.current.add(prevStep.current)
          setCompletedSteps((p) => [...p, prevStep.current!])
        }
        prevStep.current = cur

        if (data.status === 'done' || data.status === 'error') {
          if (intervalRef.current) clearInterval(intervalRef.current)
        }
      } catch { /* network hiccup — keep polling */ }
    }

    poll()
    intervalRef.current = setInterval(poll, 1800)
    return () => { if (intervalRef.current) clearInterval(intervalRef.current) }
  }, [jobId])

  const isDone  = status?.status === 'done'
  const isError = status?.status === 'error'
  const progress = status?.progress ?? 0

  // Which pipeline stage is active?
  const activeStage = PIPELINE_STAGES.findIndex(
    ({ range }) => progress >= range[0] && progress < range[1]
  )

  return (
    <main className="min-h-screen cinema-grid relative overflow-hidden">
      <div className="absolute top-[-200px] left-[-200px] w-[600px] h-[600px] rounded-full bg-[#64dcb4] opacity-[0.03] blur-[120px] pointer-events-none" />

      <div className="h-[3px] w-full bg-gradient-to-r from-[#64dcb4] via-[#dc82ff] to-[#64dcb4]" />

      <nav className="flex items-center justify-between px-8 py-5 border-b border-white/5">
        <div className="flex items-center gap-2">
          <Film className="text-[#64dcb4]" size={22} />
          <span className="font-bold text-lg tracking-tight">
            Script<span className="text-[#64dcb4]">Cinema</span>
          </span>
        </div>
        <Link href="/" className="text-sm text-gray-400 hover:text-white transition-colors flex items-center gap-1.5">
          <ArrowLeft size={14} /> New video
        </Link>
      </nav>

      <div className="max-w-3xl mx-auto px-6 py-14">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="mb-10">
          <p className="text-gray-500 text-xs mb-1 font-mono uppercase tracking-wider">Recording live project</p>
          <h1 className="text-2xl font-bold text-[#64dcb4] truncate font-mono">{repoName || 'Repository'}</h1>
        </motion.div>

        <AnimatePresence mode="wait">
          {/* ── Connecting ── */}
          {!status && (
            <motion.div key="connecting" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              className="flex items-center gap-3 text-gray-400 text-sm">
              <Loader2 size={16} className="animate-spin" /> Connecting to server…
            </motion.div>
          )}

          {/* ── Running ── */}
          {status && !isDone && !isError && (
            <motion.div key="running" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              className="space-y-8">

              {/* Current step */}
              <div className="gradient-border rounded-xl p-6 bg-[#12141f]">
                <div className="flex items-center gap-3 mb-5">
                  <Loader2 size={16} className="text-[#64dcb4] animate-spin flex-shrink-0" />
                  <span className="text-sm text-gray-200 font-mono">{status.step || 'Starting…'}</span>
                </div>
                <ProgressBar progress={progress} />
                <p className="text-right text-xs text-gray-600 mt-2 font-mono">{progress}%</p>
              </div>

              {/* Pipeline stage tracker */}
              <div className="space-y-3">
                <p className="text-xs text-gray-600 uppercase tracking-wider">Pipeline</p>
                {PIPELINE_STAGES.map(({ label, icon: Icon }, i) => {
                  const done   = progress >= PIPELINE_STAGES[i]?.range[1]
                  const active = i === activeStage
                  return (
                    <motion.div
                      key={label}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: i * 0.06 }}
                      className={`flex items-center gap-3 text-sm transition-colors ${
                        done   ? 'text-gray-400' :
                        active ? 'text-white'     : 'text-gray-600'
                      }`}
                    >
                      {done
                        ? <CheckCircle2 size={14} className="text-[#64dcb4] flex-shrink-0" />
                        : active
                          ? <Loader2 size={14} className="text-[#dc82ff] animate-spin flex-shrink-0" />
                          : <Icon size={14} className="flex-shrink-0 opacity-30" />
                      }
                      {label}
                    </motion.div>
                  )
                })}
              </div>

              {/* Completed step log */}
              {completedSteps.length > 0 && (
                <div className="space-y-1.5">
                  <p className="text-xs text-gray-600 uppercase tracking-wider">Log</p>
                  {completedSteps.map((step, i) => (
                    <motion.div key={i} initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                      className="text-xs text-gray-500 font-mono truncate flex items-center gap-2">
                      <span className="text-[#64dcb4]">✓</span> {step}
                    </motion.div>
                  ))}
                </div>
              )}
            </motion.div>
          )}

          {/* ── Done ── */}
          {isDone && status?.video_url && (
            <motion.div key="done" initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0 }} className="space-y-6">
              <div className="flex items-center gap-3 text-[#64dcb4]">
                <CheckCircle2 size={22} />
                <span className="text-lg font-semibold">Cinematic video ready!</span>
              </div>
              <VideoPlayer videoUrl={status.video_url} />
              <a href={status.video_url}
                download={`${repoName.replace('/', '-') || 'scriptcinema'}.mp4`}
                className="inline-flex items-center gap-2 bg-[#64dcb4] hover:bg-[#50c8a0] text-black font-semibold px-6 py-3 rounded-lg transition-colors">
                <Download size={16} /> Download MP4
              </a>
            </motion.div>
          )}

          {/* ── Error ── */}
          {isError && (
            <motion.div key="error" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              className="gradient-border rounded-xl p-6 bg-[#12141f]">
              <div className="flex items-start gap-3">
                <AlertCircle size={18} className="text-red-400 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold text-red-400 mb-1">Pipeline failed</p>
                  <p className="text-sm text-gray-400 font-mono">{status?.error || 'Unknown error.'}</p>
                  <Link href="/" className="inline-block mt-4 text-sm text-[#64dcb4] hover:underline">
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
