'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { motion } from 'framer-motion'
import HeroInput from '@/components/HeroInput'
import { Film, Zap, Code2, GitBranch, Download, Monitor } from 'lucide-react'

const FEATURES = [
  { icon: GitBranch, title: 'Auto Clone & Run',   desc: 'Clones your repo and starts it in a real environment automatically' },
  { icon: Zap,       title: 'Stack Detection',    desc: 'Auto-detects Next.js, Vite, CRA, Flask, FastAPI, Django & more' },
  { icon: Monitor,   title: 'Live Browser',       desc: 'A real Chromium browser opens and navigates your running app' },
  { icon: Code2,     title: 'Smart Interaction',  desc: 'Clicks nav links, fills forms, scrolls pages automatically' },
  { icon: Film,      title: 'Cinematic Recording', desc: 'Full browser session recorded and graded with intro/outro' },
  { icon: Download,  title: 'MP4 Download',       desc: 'Download the final cinematic video of your real project' },
]

const EXAMPLE_REPOS = [
  'https://github.com/vercel/next.js',
  'https://github.com/facebook/react',
  'https://github.com/microsoft/vscode',
  'https://github.com/Adityadav999/ScriptCinema',
]

export default function HomePage() {
  const router = useRouter()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleGenerate = async (url: string) => {
    if (!url.includes('github.com')) {
      setError('Please enter a valid GitHub repository URL.')
      return
    }
    setError('')
    setLoading(true)

    try {
      const res = await fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repo_url: url }),
      })

      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || 'Failed to start generation.')
      }

      const { job_id } = await res.json()
      router.push(`/generate?job=${job_id}&repo=${encodeURIComponent(url)}`)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Something went wrong.')
      setLoading(false)
    }
  }

  return (
    <main className="min-h-screen cinema-grid relative overflow-hidden">
      {/* Ambient glow orbs */}
      <div className="absolute top-[-200px] left-[-200px] w-[600px] h-[600px] rounded-full bg-[#64dcb4] opacity-[0.04] blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-200px] right-[-200px] w-[600px] h-[600px] rounded-full bg-[#dc82ff] opacity-[0.04] blur-[120px] pointer-events-none" />

      {/* Top accent bar */}
      <div className="h-[3px] w-full bg-gradient-to-r from-[#64dcb4] via-[#dc82ff] to-[#64dcb4]" />

      {/* Nav */}
      <nav className="flex items-center justify-between px-8 py-5 border-b border-white/5">
        <div className="flex items-center gap-2">
          <Film className="text-[#64dcb4]" size={22} />
          <span className="font-bold text-lg tracking-tight">
            Script<span className="text-[#64dcb4]">Cinema</span>
          </span>
        </div>
        <a
          href="https://github.com/Adityadav999/ScriptCinema"
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm text-gray-400 hover:text-white transition-colors flex items-center gap-1.5"
        >
          <GitBranch size={14} />
          GitHub
        </a>
      </nav>

      {/* Hero */}
      <section className="flex flex-col items-center text-center px-6 pt-24 pb-16">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7 }}
        >
          <div className="inline-flex items-center gap-2 bg-[#64dcb4]/10 border border-[#64dcb4]/20 text-[#64dcb4] text-xs font-medium px-3 py-1.5 rounded-full mb-6">
            <span className="w-1.5 h-1.5 rounded-full bg-[#64dcb4] animate-pulse" />
            Open Source · Free to Use
          </div>

          <h1 className="text-5xl md:text-7xl font-bold tracking-tight mb-6 leading-tight">
            Turn any{' '}
            <span className="text-[#64dcb4] text-glow">GitHub Repo</span>
            <br />
            into a{' '}
            <span className="text-[#dc82ff]">Cinematic Video</span>
          </h1>

          <p className="text-gray-400 text-lg md:text-xl max-w-2xl mx-auto mb-12 leading-relaxed">
            Paste a GitHub repository URL and ScriptCinema automatically generates a beautiful
            high-quality video showcasing your codebase, commit history, and project stats.
          </p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.2 }}
          className="w-full max-w-2xl"
        >
          <HeroInput onGenerate={handleGenerate} loading={loading} error={error} />

          {/* Example repos */}
          <div className="mt-5 flex flex-wrap justify-center gap-2">
            <span className="text-xs text-gray-500 mr-1 mt-1">Try:</span>
            {EXAMPLE_REPOS.map((repo) => {
              const name = repo.split('github.com/')[1]
              return (
                <button
                  key={repo}
                  onClick={() => handleGenerate(repo)}
                  disabled={loading}
                  className="text-xs text-gray-400 hover:text-[#64dcb4] bg-white/5 hover:bg-[#64dcb4]/10 border border-white/10 hover:border-[#64dcb4]/30 px-2.5 py-1 rounded-md transition-all disabled:opacity-50"
                >
                  {name}
                </button>
              )
            })}
          </div>
        </motion.div>
      </section>

      {/* Features */}
      <section className="max-w-5xl mx-auto px-6 pb-24">
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5, duration: 0.6 }}
          className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4"
        >
          {FEATURES.map((feat, i) => (
            <motion.div
              key={feat.title}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.5 + i * 0.08, duration: 0.5 }}
              className="gradient-border rounded-xl p-5 bg-[#12141f] hover:bg-[#161828] transition-colors group"
            >
              <feat.icon
                size={20}
                className="text-[#64dcb4] mb-3 group-hover:scale-110 transition-transform"
              />
              <h3 className="font-semibold text-sm mb-1">{feat.title}</h3>
              <p className="text-gray-500 text-xs leading-relaxed">{feat.desc}</p>
            </motion.div>
          ))}
        </motion.div>
      </section>

      {/* Footer */}
      <footer className="text-center py-6 text-gray-600 text-xs border-t border-white/5">
        Made with ❤️ by{' '}
        <a
          href="https://github.com/Adityadav999"
          className="text-[#64dcb4] hover:underline"
        >
          Adityadav999
        </a>{' '}
        · ScriptCinema
      </footer>
    </main>
  )
}
