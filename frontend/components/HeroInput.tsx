'use client'

import { useState, useRef, KeyboardEvent } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Github, Sparkles, Loader2, AlertCircle } from 'lucide-react'

interface HeroInputProps {
  onGenerate: (url: string) => void
  loading: boolean
  error: string
}

export default function HeroInput({ onGenerate, loading, error }: HeroInputProps) {
  const [value, setValue] = useState('')
  const [focused, setFocused] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleSubmit = () => {
    if (!value.trim() || loading) return
    onGenerate(value.trim())
  }

  const handleKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') handleSubmit()
  }

  const isValid = value.includes('github.com/')

  return (
    <div className="w-full space-y-3">
      {/* Input wrapper */}
      <motion.div
        animate={
          focused
            ? { boxShadow: '0 0 0 1px rgba(100,220,180,0.4), 0 0 30px rgba(100,220,180,0.1)' }
            : { boxShadow: '0 0 0 1px rgba(255,255,255,0.08)' }
        }
        transition={{ duration: 0.2 }}
        className="flex items-center bg-[#12141f] rounded-xl overflow-hidden"
      >
        {/* GitHub icon */}
        <div className="pl-4 pr-3 flex-shrink-0">
          <Github
            size={18}
            className={`transition-colors ${focused || isValid ? 'text-[#64dcb4]' : 'text-gray-500'}`}
          />
        </div>

        {/* Input */}
        <input
          ref={inputRef}
          type="url"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          onKeyDown={handleKey}
          placeholder="https://github.com/owner/repository"
          disabled={loading}
          className="flex-1 bg-transparent py-4 text-sm text-gray-100 placeholder-gray-600 focus:outline-none font-mono disabled:opacity-50"
          autoComplete="off"
          spellCheck={false}
        />

        {/* Generate button */}
        <div className="pr-2 flex-shrink-0">
          <motion.button
            onClick={handleSubmit}
            disabled={loading || !value.trim()}
            whileHover={{ scale: loading ? 1 : 1.03 }}
            whileTap={{ scale: loading ? 1 : 0.97 }}
            className={`
              flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold transition-all
              ${isValid && !loading
                ? 'bg-[#64dcb4] text-black hover:bg-[#50c8a0]'
                : 'bg-white/10 text-gray-400 cursor-not-allowed'
              }
            `}
          >
            {loading ? (
              <>
                <Loader2 size={14} className="animate-spin" />
                <span>Generating…</span>
              </>
            ) : (
              <>
                <Sparkles size={14} />
                <span>Generate</span>
              </>
            )}
          </motion.button>
        </div>
      </motion.div>

      {/* Error message */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            className="flex items-center gap-2 text-red-400 text-sm px-1"
          >
            <AlertCircle size={14} className="flex-shrink-0" />
            {error}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Hint */}
      {!error && (
        <p className="text-xs text-gray-600 px-1">
          Works with any public GitHub repository · No login required
        </p>
      )}
    </div>
  )
}
