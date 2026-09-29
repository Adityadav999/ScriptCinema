# 🎬 ScriptCinema

> Transform any GitHub repository into a cinematic video — automatically.

ScriptCinema is an open-source tool that takes a GitHub repository URL and renders a beautiful, high-quality `.mp4` video showcasing the codebase: its structure, languages, top files, commit history, and project stats — all presented as cinematic animated scenes.

---

## ✨ Features

- 🔗 **Input any public GitHub repo URL**
- 🎬 **7 cinematic scenes** auto-generated from repo data
- 💻 **Syntax-highlighted code** scrolling on screen
- 🌳 **Animated file tree** explorer
- 📊 **Language breakdown** bar chart
- 📜 **Commit history** timeline
- ⭐ **Stats card** (stars, forks, issues, contributors)
- 📥 **Download as `.mp4`**

---

## 🗂️ Project Structure

```
ScriptCinema/
├── frontend/        # Next.js 14 app (TypeScript + Tailwind)
└── backend/         # FastAPI + MoviePy video pipeline
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+ & pnpm
- (Optional) GitHub Personal Access Token for higher API rate limits

---

### Backend Setup

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt

# Copy and configure env
cp .env.example .env
# Add your GITHUB_TOKEN to .env (optional but recommended)

uvicorn main:app --reload --port 8000
```

---

### Frontend Setup

```bash
cd frontend
pnpm install
pnpm dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## 🎥 How It Works

1. **Input** — Paste a GitHub repo URL into the form
2. **Fetch** — Backend fetches repo metadata, file tree, commits, and code via GitHub API
3. **Scene Build** — Data is structured into 7 cinematic scenes
4. **Render** — MoviePy + Pillow renders each scene as animated frames
5. **Output** — Scenes assembled into a `.mp4`, ready to download

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14, TypeScript, Tailwind CSS, Framer Motion |
| Backend | Python 3.11, FastAPI |
| Video Engine | MoviePy + Pillow |
| GitHub Data | PyGithub |
| Syntax Highlighting | Pygments |

---

## 📄 License

MIT © [ScriptCinema](https://github.com/Adityadav999/ScriptCinema)
