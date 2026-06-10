# DESK

**Your entire AI office. One desktop app.**

DESK is a native desktop application that lets solopreneurs run a full AI-powered office from a single interface. Create multiple AI agents, each with their own personality, purpose, and intelligence. Talk to all of them. Let them build things for you.

> *The entire office now sits on a desktop. Solopreneurs shake buildings.*

---

## What DESK Does

You hire agents. Each agent has a name, a role, and a brain — local or cloud. You talk to them the same way you'd talk to a team. They remember your conversations, build things for you, and keep everything organized in a Workspace.

No browser tabs. No switching between ChatGPT and Claude and Gemini. One app. Everything in one place.

---

## Features

### The Agents
- **Hire agents** — give them a name, a system prompt, a color
- **Fire agents** — hard delete, everything gone cleanly
- **Edit agents** — rename, reprompt, recolor, swap their brain mid-conversation
- **Right-click** any agent strip for a context menu

### The Intelligence
- **7 backends supported** — Ollama (local), OpenAI, Anthropic, Google Gemini, Mistral, Groq, OpenRouter
- **Mix and match** — one agent on local Llama, another on GPT-4, another on Gemini Flash
- **Free tier models** — Gemini 2.0 Flash, Groq Llama 3.3, OpenRouter DeepSeek R1, Mistral Nemo — all marked clearly
- **Streaming responses** — output appears in real time

### The Workspace *(New in v2)*
- **Artifact detection** — when an agent builds a file, DESK captures it automatically. No special commands. The agent just knows.
- **Workspace panel** — all your agents' files in one place. Searchable. Organized by agent.
- **Code versioning** — same filename, updated content → new version. Up to 3 versions per file.
- **Code Inspector** — click any file, a side panel opens. Switch between versions. Copy the full file. Download it. Resizable.
- **Clean chat** — artifact code blocks are suppressed in chat. You see the agent's explanation and a clickable file chip. The code lives in the Workspace, not the conversation.
- **Inline snippets** — short code examples (not full files) appear inline with a one-click copy button

### The History
- **Persistent chat** — every conversation saved automatically per agent
- **File attachments** — drag & drop images and documents into chat
- **Images rendered inline** — send a screenshot, the agent sees it
- **Clear chat** — wipes history and artifacts for that agent

### The Interface
- **The Pole** — the left sidebar. One colored strip per agent. Click to switch. Shift+Tab to cycle.
- **Compute modes** — High (parallel agents, 4 threads) or Low (serial, RAM-safe for 4GB machines)
- **Response length** — Concise / Standard / Detailed / Full, set globally or per agent
- **Settings panel** — all config in one place
- **Keys panel** — API keys stored locally, never sent anywhere except the provider you configure

---

## Supported Backends

| Backend | Type | Notable Free Models |
|---|---|---|
| Ollama | Local | All models — free forever |
| Google Gemini | Cloud | Gemini 2.0 Flash, 2.5 Flash Lite, 1.5 Flash |
| Groq | Cloud | Llama 3.3 70B, DeepSeek R1, Qwen QwQ 32B |
| OpenRouter | Cloud | Llama 3.3, Gemma 3 27B, DeepSeek R1 |
| Mistral | Cloud | Mistral Nemo |
| OpenAI | Cloud | All paid |
| Anthropic | Cloud | All paid |

---

## Getting Started

### Requirements
- Windows 10/11
- Python 3.11+ (if running from source)
- For local models: [Ollama](https://ollama.com) installed separately

### Run from Source

```bash
# Clone the repo
git clone https://github.com/yourusername/DESK.git
cd DESK

# Install dependencies
pip install PySide6

# Copy the keys template
cp config/keys.template.json config/keys.json

# Run
python main.py
```

### Windows Executable

Download `DESK-v2.0.0-windows.zip` from the [Releases](../../releases) page. Unzip and run `DESK.exe`. No Python required.

---

## Project Structure

```
DESK/
├── config/              → app.json, agents.json, keys.json, models.json, artifacts.json
├── bucket/              → agent .md files (filename = agent name, content = system prompt)
├── workspace/
│   └── history/         → chat history per agent + attached images
├── core/
│   ├── inference_manager.py   → all LLM calls route through here
│   ├── artifact_manager.py    → workspace artifact detection + versioning
│   ├── compute_manager.py     → threading + compute modes
│   ├── config_loader.py       → reads/writes all config JSON
│   └── history_manager.py     → chat persistence
├── ui/
│   ├── main_window.py
│   ├── panels/
│   │   ├── chat_panel.py
│   │   ├── workspace_panel.py
│   │   ├── code_inspector_panel.py
│   │   ├── settings_panel.py
│   │   └── keys_panel.py
│   ├── dialogs/
│   │   ├── add_agent_dialog.py
│   │   └── edit_agent_dialog.py
│   └── styles/
│       └── theme.qss
├── utils/
│   └── file_watcher.py
└── main.py
```

---

## How the Workspace Works

When an agent responds with code, DESK automatically:

1. Detects every fenced code block in the response
2. Infers the filename from context — the agent says "here's `index.html`" and DESK reads it
3. Saves the file to the agent's Workspace folder
4. If the same filename appears again with different content, a new version is created (max 3 kept)
5. Suppresses the raw code from the chat — replaces it with a clickable file chip

The agent's explanation stays. The file chip is clickable — opens the Code Inspector on the right side of the screen.

---

## Building the Executable

```bash
pip install pyinstaller

py -m PyInstaller main.py \
  --onefile \
  --windowed \
  --name DESK \
  --add-data "config;config" \
  --add-data "bucket;bucket" \
  --add-data "workspace;workspace" \
  --add-data "ui/styles;ui/styles"
```

Output: `dist/DESK.exe`

---

## Design Principles

- **Never hardcode an API call** — everything routes through `InferenceManager`
- **Refresh never deletes data** — soft UI rebuild only, no history touched
- **Fire is the only hard delete** — agent + bucket file + config + history + artifacts
- **Folder as source of truth** — `bucket/` is live-synced, agents appear when `.md` files appear
- **Local first** — keys stored on your machine, never transmitted anywhere except the provider

---

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+N` | New Agent |
| `Shift+Tab` | Cycle through agents |
| `Ctrl+W` | Toggle Workspace panel |
| `Ctrl+,` | Settings |

---

## Roadmap

- **Town Hall** — multi-agent collaboration. Agents talk to each other. You're the founder in the room.
- **NotePad** — private notepad, separate from agent conversations
- **ScratchPad** — agent reasoning traces for complex problems
- **Avatars** — custom visual identity per agent
- **Agent chaining** — output of one agent feeds into another
- **Plugin system** — extend agent behavior via Python

---

## License

MIT