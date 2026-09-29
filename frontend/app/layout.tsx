import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'ScriptCinema — GitHub Repo to Cinematic Video',
  description:
    'Transform any GitHub repository into a beautiful cinematic video. Showcase your codebase, commit history, language stats, and more — automatically.',
  keywords: ['github', 'video', 'cinematic', 'code', 'repository', 'developer tools'],
  openGraph: {
    title: 'ScriptCinema',
    description: 'Turn any GitHub repo into a cinematic video.',
    type: 'website',
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="dark">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className={`${inter.className} bg-[#0a0a14] text-gray-100 antialiased min-h-screen`}>
        {children}
      </body>
    </html>
  )
}
