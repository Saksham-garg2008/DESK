# DESK

> A lightweight, cross-platform AI desktop assistant built around persistent agents, local workspace tools, and controlled agentic actions.

DESK is a desktop AI assistant built with **Python and PySide6**. It combines conversational AI with persistent agents, memory, workspace management, and a growing set of actions that allow an agent to interact with the user's desktop.

DESK is designed to remain **simple, lightweight, and practical** rather than relying on large local AI frameworks.

---

## ✨ What DESK Can Do

### 🤖 AI Agents

Create multiple AI agents with their own personas and configurations.

Each agent can maintain its own context while sharing the same DESK environment.

- Multiple independent agents
- Persistent agent configuration
- Custom agent personas
- Per-agent AI configuration
- Agent-specific Chrome profiles

---

### 🧠 Memory & Persistence

DESK keeps important application data across sessions.

Conversation history, memory, workspace data, and configuration are stored outside the application bundle so that user data survives application restarts and executable updates.

DESK uses platform-appropriate locations for persistent data:

| Platform | Data location |
|---|---|
| Windows | `%APPDATA%\DESK` |
| Linux | `$XDG_DATA_HOME/DESK` or `~/.local/share/DESK` |
| macOS | `~/Library/Application Support/DESK` |

---

### 🌐 Browser Actions

Agents can request browser actions through DESK's structured action system.

For example, an agent can request that DESK open a website without needing to know how the user's browser is installed.

DESK can also use a configured Chrome profile for an agent.

This means the **agent decides what it wants to open, while DESK controls which browser configuration is actually used.**

---

### 🖥️ Application Actions

DESK can open installed desktop applications using a human-readable application name.

The application launcher is designed to avoid maintaining a hardcoded list of applications.

Instead, DESK resolves applications using information provided by the operating system:

- **Linux** — discovers applications through `.desktop` entries
- **Windows** — searches Start Menu shortcuts
- **macOS** — uses the operating system's application launching system

The agent does not need to know executable paths, installation directories, or OS-specific launch commands.

---

## 🔐 Controlled Agentic Actions

DESK uses a structured action protocol to separate **conversation** from **desktop actions**.

An agent can request an action using a structured format:

```text
<DESK_ACTION>
{
  "action": "open_url",
  "url": "https://www.youtube.com"
}
</DESK_ACTION>
```

DESK then extracts, validates, and executes the requested action.

This creates an important separation:

```text
User
  │
  ▼
AI Agent
  │
  │  decides what action is needed
  ▼
DESK Action Protocol
  │
  │  validates & interprets
  ▼
DESK Action Executor
  │
  │  controls local execution
  ▼
Operating System
```

The model does **not** need to know the user's local executable paths, Chrome profile directories, or other machine-specific configuration.

---

## 🏗️ Architecture

DESK is organized into several core components.

```text
DESK
├── core/
│   ├── inference_manager.py
│   ├── compute_manager.py
│   ├── artifact_manager.py
│   ├── history_manager.py
│   ├── memory_manager.py
│   ├── config_loader.py
│   ├── agent_actions.py
│   ├── agent_protocol.py
│   ├── applications.py
│   ├── chrome_profiles.py
│   └── paths.py
│
├── ui/
│   ├── main_window.py
│   └── chat_panel.py
│
├── config/
│
├── bucket/
│
├── workspace/
│
└── main.py
```

### Core

The `core/` package contains DESK's application logic.

Some of the main responsibilities include:

| Component | Responsibility |
|---|---|
| `inference_manager.py` | AI inference and provider interaction |
| `compute_manager.py` | Compute-related configuration |
| `memory_manager.py` | Agent memory |
| `history_manager.py` | Conversation history |
| `artifact_manager.py` | Workspace artifacts |
| `agent_protocol.py` | Structured agent-action extraction |
| `agent_actions.py` | Action execution |
| `applications.py` | Cross-platform application discovery and launching |
| `chrome_profiles.py` | Chrome/Chromium profile discovery |
| `paths.py` | Application resources and persistent user-data paths |

---

## 🧩 Action Architecture

DESK intentionally keeps **AI reasoning** separate from **machine-specific execution**.

For example, an agent may determine:

> "The user wants to open Spotify."

The agent does not need to know whether Spotify is located at:

```text
/usr/bin/spotify
```

or:

```text
C:\Users\...\Spotify.exe
```

Instead, it requests:

```json
{
  "action": "open_application",
  "application": "Spotify"
}
```

DESK resolves the application using the host operating system.

This keeps the agent protocol portable while allowing the execution layer to remain OS-specific.

---

## 🎨 Desktop Interface

DESK uses **PySide6** for its desktop interface.

The interface includes:

- Agent management
- Chat interface
- Persistent conversations
- Workspace and artifacts
- Settings
- Agent configuration
- Chrome profile configuration
- Theme and display configuration

---

## 📦 Installation

### Download a Release

Pre-built executables are available from the project's GitHub Releases page.

[DESK Releases](https://github.com/Saksham-garg2008/DESK/releases?utm_source=chatgpt.com)

Current release builds include:

- Windows executable
- Linux executable

---

### Run From Source

Clone the repository:

```bash
git clone https://github.com/Saksham-garg2008/DESK.git
cd DESK
```

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it on Linux/macOS:

```bash
source .venv/bin/activate
```

On Windows:

```powershell
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run DESK:

```bash
python main.py
```

---

## ⚙️ Requirements

DESK is built with:

- **Python**
- **PySide6**
- AI provider APIs configured by the user

The current dependency footprint is intentionally small.

---

## 🔧 Configuration

DESK keeps application resources separate from persistent user data.

Bundled resources belong to the application installation, while user-generated data is stored in the platform-specific DESK data directory.

This separation is particularly important for packaged applications such as PyInstaller builds, where the application itself may be replaced during an update.

DESK also maintains a small data-version marker to support future data migrations without tying user data to a particular application executable.

---

## 🛠️ Building DESK

DESK uses GitHub Actions to produce packaged builds for supported desktop platforms.

The build system packages DESK into standalone executables using **PyInstaller**.

Release artifacts are published through GitHub Releases.

---

## 📚 Documentation

For deeper technical information, see the **DESK Wiki**.

The Wiki covers areas such as:

- Architecture
- Agents
- AI providers
- Agent actions
- Browser integration
- Application discovery
- Memory
- Workspace
- Persistence
- Configuration
- Development
- Building and releasing DESK

---

## 👨‍💻 Development

DESK is an actively developed open-source project.

The codebase is intentionally kept modular so that new capabilities can be added without tightly coupling AI inference, the user interface, and operating-system-specific functionality.

---

**DESK** — AI that works from your desktop.
