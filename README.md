# DESK

<p align="center">
  <strong>AI that works from your desktop.</strong><br>
  A lightweight, cross-platform AI desktop assistant built with Python and PySide6.
</p>

<p align="center">
  <a href="https://github.com/Saksham-garg2008/DESK/releases"><img src="https://img.shields.io/github/v/release/Saksham-garg2008/DESK?style=flat-square&label=release" alt="Latest Release"></a>
  <a href="https://github.com/Saksham-garg2008/DESK"><img src="https://img.shields.io/github/stars/Saksham-garg2008/DESK?style=flat-square" alt="GitHub Stars"></a>
  <a href="https://github.com/Saksham-garg2008/DESK/issues"><img src="https://img.shields.io/github/issues/Saksham-garg2008/DESK?style=flat-square" alt="GitHub Issues"></a>
  <img src="https://img.shields.io/badge/Python-3.x-blue?style=flat-square" alt="Python">
  <img src="https://img.shields.io/badge/PySide6-Desktop%20UI-blue?style=flat-square" alt="PySide6">
  <img src="https://img.shields.io/badge/Platforms-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey?style=flat-square" alt="Platforms">
</p>

---

## About DESK

DESK is a lightweight desktop AI assistant built with **Python and PySide6**.

It combines conversational AI with persistent agents, memory, workspace management, browser capabilities, and controlled desktop actions.

DESK is designed around a simple principle:

> **The AI decides what it wants to do. DESK decides how that action is executed.**

The project keeps AI reasoning separate from machine-specific execution, allowing agents to work with high-level intents without needing to know local executable paths, browser profile directories, or operating-system-specific commands.

---

## ✨ What DESK Can Do

### 🤖 AI Agents

Create multiple AI agents with their own personas and configurations.

- Multiple independent agents
- Persistent agent configuration
- Custom agent personas
- Per-agent AI configuration
- Agent-specific Chrome profiles

### 🧠 Memory & Persistence

DESK keeps important application data across sessions.

Conversation history, memory, workspace data, and configuration are stored outside the application bundle so user data can survive application restarts and executable updates.

| Platform | Data location |
| --- | --- |
| Windows | `%APPDATA%\DESK` |
| Linux | `$XDG_DATA_HOME/DESK` or `~/.local/share/DESK` |
| macOS | `~/Library/Application Support/DESK` |

### 🌐 Browser Actions

Agents can request browser actions through DESK's structured action system.

An agent can determine what should be opened while DESK handles the actual browser configuration.

Chrome profiles can be configured per agent, keeping local browser configuration outside the model's decision-making process.

### 🖥️ Application Actions

DESK can open installed desktop applications using a human-readable application name.

The application launcher avoids maintaining a manually hardcoded application list and instead resolves applications using information provided by the operating system.

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

The basic flow is:

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

DESK is organized into separate components so that the user interface, AI inference, memory, workspace, and desktop actions remain modular.

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
├── bucket/
├── workspace/
└── main.py
```

### Core Components

| Component | Responsibility |
| --- | --- |
| `inference_manager.py` | AI inference and provider interaction |
| `compute_manager.py` | Compute-related configuration |
| `memory_manager.py` | Agent memory |
| `history_manager.py` | Conversation history |
| `artifact_manager.py` | Workspace artifacts |
| `agent_protocol.py` | Structured agent-action extraction |
| `agent_actions.py` | Action execution |
| `applications.py` | Cross-platform application discovery and launching |
| `chrome_profiles.py` | Chrome/Chromium profile handling |
| `paths.py` | Application and persistent-data paths |

---

## 🧩 Action Architecture

DESK intentionally keeps **AI reasoning** separate from **machine-specific execution**.

For example, an agent may determine:

> "The user wants to open Spotify."

The agent does not need to know where Spotify is installed.

Instead, it can request:

```json
{
  "action": "open_application",
  "application": "Spotify"
}
```

DESK resolves the application using the host operating system.

This keeps the agent protocol portable while allowing the execution layer to remain OS-specific.

---

## 📱 DESK Companion

DESK is also being developed alongside an Android companion project.

**[DESK Companion](https://github.com/Saksham-garg2008/DESK-Companion)**

The desktop application remains the core DESK project, while the Android companion is maintained separately as its own repository.

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

**[Download DESK Releases](https://github.com/Saksham-garg2008/DESK/releases)**

Current release builds include:

- Windows executable
- Linux executable

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

The project intentionally keeps its dependency footprint small.

---

## 🔧 Configuration & Data

DESK keeps application resources separate from persistent user data.

Bundled resources belong to the application installation, while user-generated data is stored in the platform-specific DESK data directory.

This separation is particularly important for packaged applications, where the application itself may be replaced during an update.

---

## 🛠️ Building DESK

DESK uses **PyInstaller** for packaged application builds and **GitHub Actions** for automated release builds.

Release artifacts are published through GitHub Releases.

---

## 📚 Documentation

The **DESK Wiki** contains deeper technical documentation covering:

- Architecture
- Agents and memory
- Agentic actions
- Browser actions
- Application discovery
- Data and persistence
- Configuration
- Building from source
- Contributing

---

## 🤝 Contributing

Contributions, ideas, bug reports, and improvements are welcome.

See **[CONTRIBUTING.md](CONTRIBUTING.md)** for contribution guidelines.

---

<p align="center">
  <strong>DESK</strong><br>
  AI that works from your desktop.
</p>
