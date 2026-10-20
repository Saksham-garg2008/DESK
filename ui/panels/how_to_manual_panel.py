
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTabWidget,
    QTextBrowser,
    QFrame,
)
from PySide6.QtCore import Qt


class HowToManualPanel(QWidget):
    """Offline, in-app user manual for DESK."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("how_to_manual_panel")
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header
        header = QWidget()
        header.setObjectName("manual_header")
        header.setFixedHeight(72)

        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(28, 0, 28, 0)
        header_layout.setSpacing(14)

        icon = QLabel("💡")
        icon.setStyleSheet("font-size: 24px;")
        header_layout.addWidget(icon)

        title_column = QVBoxLayout()
        title_column.setSpacing(3)

        title = QLabel("HOW TO MANUAL")
        title.setStyleSheet(
            "font-size: 13px; font-weight: 700; "
            "letter-spacing: 2px; color: #E2E2E8;"
        )
        title_column.addWidget(title)

        subtitle = QLabel("A practical guide to using DESK")
        subtitle.setStyleSheet("font-size: 11px; color: #656570;")
        title_column.addWidget(subtitle)

        header_layout.addLayout(title_column)
        header_layout.addStretch()

        offline = QLabel("AVAILABLE OFFLINE")
        offline.setStyleSheet(
            "font-size: 9px; font-weight: 600; letter-spacing: 1px; "
            "color: #77778C; border: 1px solid #30303A; "
            "border-radius: 4px; padding: 5px 8px;"
        )
        header_layout.addWidget(offline)

        outer.addWidget(header)

        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet("color: #26262E;")
        outer.addWidget(divider)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setObjectName("manual_tabs")
        self.tabs.setDocumentMode(True)
        self.tabs.setMovable(False)

        sections = [
            (
                "What is DESK",
                "01  /  INTRODUCTION",
                "Your AI office.",
                """
                <p>DESK is a desktop application for working with configurable
                AI agents. Each agent can have its own role, instructions,
                model configuration, conversation, and saved memory.</p>

                <h2>How it fits together</h2>
                <ul>
                  <li><b>Agents</b> are the assistants you work with.</li>
                  <li><b>Models</b> generate responses through the selected
                  provider or local inference setup.</li>
                  <li><b>Memory</b> helps preserve selected information
                  between conversations.</li>
                  <li><b>Workspace</b> gives you access to generated artifacts.</li>
                  <li><b>Settings and Keys</b> configure application behaviour
                  and provider credentials.</li>
                </ul>

                <h2>Local does not always mean offline</h2>
                <p>A model running locally through a configured local
                inference provider may work without internet access once
                everything it needs is installed. Cloud providers generally
                require a network connection and valid credentials.</p>

                <p>DESK does not automatically make every model local,
                private, free, or available offline. The actual behaviour
                depends on your provider and configuration.</p>
                
                <h2>Android Companion</h2>
                <p>
                  DESK includes a QR-code generator for its Android Companion connection
                  flow. Press <strong>Ctrl + Shift + P</strong> to open it and follow
                  the connection instructions displayed by DESK.
                </p>

                <h2>Getting started</h2>
                <ol>
                  <li>Create an agent with <b>+ New Agent</b>.</li>
                  <li>Give it a clear role and instructions.</li>
                  <li>Choose a configured backend and model.</li>
                  <li>Send a message and review the response.</li>
                  <li>Explore Memory and Workspace as you use the agent.</li>
                </ol>
                """,
            ),
            (
                "AI Agents",
                "02  /  AGENTS",
                "Different roles. Separate conversations.",
                """
                <p>An agent is a configured AI assistant. You can create
                different agents for different tasks instead of using one
                conversation for everything.</p>

                <h2>Create an agent</h2>
                <p>Use <b>+ New Agent</b> in the top bar or press
                <b>Alt + N</b> on Windows/Linux. Define its name, role,
                instructions, and available model settings in the creation
                interface.</p>

                <h2>System prompts</h2>
                <p>The system prompt defines the agent's role, priorities,
                style, and working instructions. Be specific about its
                objective, what a good result looks like, and any constraints.</p>

                <h2>Switch between agents</h2>
                <p>Select an agent from the vertical agent strips. You can
                also use <b>Shift + Tab</b> to cycle through agents or
                <b>Alt + H</b> to activate the first agent in sidebar order.</p>

                <h2>Models and providers</h2>
                <p>Model availability depends on your configuration, provider,
                credentials, installed local models, and network access.
                Changing an agent's instructions does not change the underlying
                model's capabilities.</p>

                <h2>Fire Agent</h2>
                <p>Firing an agent is a destructive delete operation. It can
                permanently remove the agent and associated conversation
                history, memory, configuration, and artifacts. Read the
                confirmation dialog carefully before proceeding.</p>
                """,
            ),
            (
                "Memory Panel",
                "03  /  CONTINUITY",
                "Keep useful context between exchanges.",
                """
                <p>The Memory panel lets you inspect and edit the saved memory
                associated with agents. Memory is distinct from the complete
                conversation transcript.</p>

                <h2>Review or edit memory</h2>
                <ol>
                  <li>Open Memory using the brain icon in the vertical pole,
                  or press <b>Alt + M</b>.</li>
                  <li>Select an agent from the list.</li>
                  <li>Review or edit its memory text.</li>
                  <li>Press <b>Save</b> to persist your edits.</li>
                </ol>

                <h2>Regenerate</h2>
                <p><b>Regenerate</b> requests a fresh memory update from
                available recent conversation history. This makes an inference
                request and can take time, particularly with a local model.
                If there is no conversation history, there may be nothing to
                summarize.</p>

                <h2>Memory Agent</h2>
                <p>The Memory panel also provides configuration for the
                backend and model used for memory distillation. If that
                configuration is unset, DESK may fall back to the agent's
                own model, as indicated by the panel.</p>

                <p>Memory is not a perfect transcript or a guarantee that
                every past detail will be recalled. Review important details
                and correct saved memory when necessary.</p>
                """,
            ),
            (
                "Settings",
                "04  /  CONFIGURATION",
                "Adjust how DESK behaves.",
                """
                <p>Open Settings from the gear icon in the vertical pole,
                or press <b>Alt + S</b>.</p>

                <h2>Application settings</h2>
                <p>Use the options shown in your installed version to
                configure DESK. The available controls are the source of
                truth for which settings can be changed.</p>

                <h2>Compute mode</h2>
                <p>The top-bar compute control switches between <b>High</b>
                and <b>Low</b> modes. You can also press
                <b>Alt + Right Arrow</b>. These modes control DESK's compute
                setting; they do not guarantee a particular response speed
                or quality across all models and hardware.</p>

                <h2>Agent-specific configuration</h2>
                <p>Agents can have their own role instructions, backend,
                and model. Check the relevant agent configuration when
                a response behaves differently than expected.</p>

                <p>If a provider or model fails, verify the selected model,
                credentials, local installation where applicable, and
                network requirements before troubleshooting further.</p>
                """,
            ),
            (
                "Keys",
                "05  /  PROVIDER ACCESS",
                "Connect the providers you use.",
                """
                <p>Open the Keys panel using the key icon in the vertical
                pole or press <b>Alt + K</b>.</p>

                <h2>API keys</h2>
                <p>The panel provides credential fields for the supported
                cloud backends configured in DESK. Enter the key for the
                relevant provider and use its Save control.</p>

                <p>API keys are sensitive credentials. Do not share them
                in chats, screenshots, public repositories, issue reports,
                or system prompts. Use the provider's own account tools
                to revoke a key if you believe it has been exposed.</p>

                <h2>Local models</h2>
                <p>A local backend such as Ollama generally does not use a
                cloud API key in the same way. It still requires a working
                local service and an available model.</p>

                <h2>Troubleshooting a provider</h2>
                <ul>
                  <li>Check that the correct backend is selected.</li>
                  <li>Verify that the key is valid for that provider.</li>
                  <li>Check account access, usage limits, and billing where
                  applicable.</li>
                  <li>For local inference, confirm the service is running
                  and the selected model is installed.</li>
                  <li>For cloud inference, confirm network access.</li>
                </ul>
                """,
            ),
            (
                "Workspace",
                "06  /  ARTIFACTS",
                "Find the files your agents create.",
                """
                <p>Workspace is the top-bar panel for browsing agent folders
                and their generated artifacts.</p>

                <h2>Open Workspace</h2>
                <p>Click <b>Workspace</b> in the top bar or press
                <b>Alt + W</b>. The panel opens alongside the main content.</p>

                <h2>Browse artifacts</h2>
                <ul>
                  <li>Use the search field to filter agents by name.</li>
                  <li>Expand an agent's folder to inspect its artifacts.</li>
                  <li>Artifact rows may show file type, version, and
                  modification information when available.</li>
                  <li>Select an artifact to open it in the code inspector.</li>
                </ul>

                <h2>Artifacts and chat are different</h2>
                <p>A message in chat is not necessarily a saved artifact.
                DESK manages artifacts separately so supported outputs can
                be inspected and versioned. The exact file format depends
                on the artifact created.</p>

                <p>If an expected artifact is missing, check the Workspace
                after the agent has finished and look for any error or
                confirmation in the conversation.</p>
                """,
            ),
            (
                "Agentic Actions",
                "07  /  ACTIONS",
                "Let agents do supported work.",
                """
                <p>DESK supports a defined set of agent-requested actions
                through its action-handling layer. The available actions
                depend on what the installed version implements and what
                the user has configured.</p>

                <h2>Give a clear request</h2>
                <p>State the intended result, relevant names or locations,
                and any limits. For example, specify the exact folder name
                and where you want it created rather than saying only
                “organize my files.”</p>

                <h2>Review the outcome</h2>
                <p>Model-generated text is not proof that an action occurred.
                Look for DESK's actual tool result or confirmation. If the
                action fails, use the reported error to decide what to try next.</p>

                <h2>Filesystem actions</h2>
                <p>When supported by the current action implementation,
                DESK can work with permitted filesystem locations, including
                supported search, creation, or folder operations. Do not
                assume that every path or operation is allowed.</p>

                <h2>Use care with destructive actions</h2>
                <p>Review the target and consequences before confirming
                operations that delete or overwrite information. Never
                assume an action is reversible just because it was requested
                through an AI agent.</p>

                <h2>When an action is unavailable</h2>
                <p>If DESK reports that an action is unsupported, unavailable,
                or unsuccessful, do not treat the agent's explanation as
                a successful result. Use the exact capabilities and status
                reported by the application.</p>
                """,
            ),
            (
                "Shortcuts",
                "08  /  QUICK REFERENCE",
                "Navigate DESK without reaching for the mouse.",
                """
                <h2>Windows and Linux</h2>
                <table>
                  <tr><th>Shortcut</th><th>Action</th></tr>
                  <tr><td><b>Ctrl + Shift + P</b></td><td>Open the Android Companion QR-code generator</td></tr>
                  <tr><td><b>Alt + N</b></td><td>New Agent</td></tr>
                  <tr><td><b>Alt + W</b></td><td>Toggle Workspace</td></tr>
                  <tr><td><b>Alt + S</b></td><td>Settings</td></tr>
                  <tr><td><b>Alt + K</b></td><td>Keys panel</td></tr>
                  <tr><td><b>Shift + Tab</b></td><td>Next agent</td></tr>
                  <tr><td><b>Alt + Right Arrow</b></td><td>Toggle High/Low compute</td></tr>
                  <tr><td><b>Alt + D</b></td><td>Fire active agent (confirmation required)</td></tr>
                  <tr><td><b>Alt + M</b></td><td>Toggle Memory panel</td></tr>
                  <tr><td><b>Alt + H</b></td><td>Activate first agent</td></tr>
                </table>

                <h2>macOS</h2>
                <p>The expected equivalent for <b>Alt</b> is usually
                <b>Option</b> in Qt applications. These macOS mappings have
                not been independently tested in DESK.</p>
                <table>
                  <tr><th>Shortcut</th><th>Action</th></tr>
                  <tr><td><b>Option + N</b></td><td>New Agent</td></tr>
                  <tr><td><b>Option + W</b></td><td>Toggle Workspace</td></tr>
                  <tr><td><b>Option + S</b></td><td>Settings</td></tr>
                  <tr><td><b>Option + K</b></td><td>Keys panel</td></tr>
                  <tr><td><b>Shift + Tab</b></td><td>Next agent</td></tr>
                  <tr><td><b>Option + Right Arrow</b></td><td>Toggle High/Low compute</td></tr>
                  <tr><td><b>Option + D</b></td><td>Fire active agent (confirmation required)</td></tr>
                  <tr><td><b>Option + M</b></td><td>Toggle Memory panel</td></tr>
                  <tr><td><b>Option + H</b></td><td>Activate first agent</td></tr>
                </table>

                <p><b>Note:</b> Firing an agent is destructive and opens
                a confirmation dialog. Review it before proceeding.</p>
                """,
            ),
        ]

        for tab_name, eyebrow, heading, body in sections:
            page = QWidget()
            page_layout = QVBoxLayout(page)
            page_layout.setContentsMargins(0, 0, 0, 0)
            page_layout.setSpacing(0)

            article = QTextBrowser()
            article.setOpenExternalLinks(True)
            article.setFrameShape(QFrame.NoFrame)
            article.setObjectName("manual_article")
            article.setHtml(self._article_html(eyebrow, heading, body))

            page_layout.addWidget(article, 1)
            self.tabs.addTab(page, tab_name)

        outer.addWidget(self.tabs, 1)

        self.setStyleSheet("""
            QWidget#how_to_manual_panel {
                background: #18181D;
            }

            QWidget#manual_header {
                background: #151519;
                border: none;
            }

            QTabWidget#manual_tabs::pane {
                border: none;
                background: #18181D;
            }

            QTabWidget#manual_tabs QTabBar::tab {
                background: transparent;
                color: #777783;
                border: none;
                border-bottom: 2px solid transparent;
                padding: 14px 16px;
                font-size: 11px;
                font-weight: 500;
            }

            QTabWidget#manual_tabs QTabBar::tab:selected {
                color: #D5D5E4;
                border-bottom: 2px solid #8585B5;
                background: #1D1D25;
            }

            QTabWidget#manual_tabs QTabBar::tab:hover:!selected {
                color: #B0B0BC;
                background: #1B1B22;
            }

            QTextBrowser#manual_article {
                background: #18181D;
                color: #B8B8C4;
                border: none;
                padding: 0;
                selection-background-color: #36364A;
            }

            QScrollBar:vertical {
                background: transparent;
                width: 6px;
                margin: 4px 2px;
            }

            QScrollBar::handle:vertical {
                background: #34343F;
                border-radius: 3px;
                min-height: 24px;
            }

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)

    @staticmethod
    def _article_html(eyebrow: str, heading: str, body: str) -> str:
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
        <meta charset="utf-8">
        <style>
            body {{
                background: #18181D;
                color: #B8B8C4;
                font-family: "Inter", "Segoe UI", sans-serif;
                font-size: 13px;
                line-height: 1.75;
                margin: 0;
                padding: 36px 7% 48px 7%;
            }}
            .eyebrow {{
                color: #77778F;
                font-size: 10px;
                font-weight: bold;
                letter-spacing: 2px;
                margin-bottom: 12px;
            }}
            h1 {{
                color: #E4E4EC;
                font-size: 28px;
                font-weight: 500;
                margin-top: 0;
                margin-bottom: 24px;
            }}
            h2 {{
                color: #D3D3DF;
                font-size: 15px;
                font-weight: 600;
                margin-top: 30px;
                margin-bottom: 8px;
            }}
            p {{
                margin-top: 8px;
                margin-bottom: 14px;
            }}
            li {{
                margin-bottom: 7px;
            }}
            ul, ol {{
                padding-left: 22px;
            }}
            b {{
                color: #D8D8E4;
                font-weight: 600;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 12px;
                margin-bottom: 22px;
            }}
            th {{
                text-align: left;
                color: #85859A;
                font-size: 10px;
                letter-spacing: 1px;
                text-transform: uppercase;
                border-bottom: 1px solid #34343E;
                padding: 10px 12px 10px 0;
            }}
            td {{
                border-bottom: 1px solid #292930;
                padding: 11px 12px 11px 0;
                vertical-align: top;
            }}
            td:first-child {{
                white-space: nowrap;
                color: #D5D5E2;
            }}
        </style>
        </head>
        <body>
            <div class="eyebrow">{eyebrow}</div>
            <h1>{heading}</h1>
            {body}
        </body>
        </html>
        """
