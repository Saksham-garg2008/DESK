
def get_keyboard_shortcuts_prompt():
    return """
DESK KEYBOARD SHORTCUTS

You know the following keyboard shortcuts and should explain them accurately
when users ask how to navigate DESK or perform an action.

WINDOWS AND LINUX
- Alt + N: Open the New Agent dialog.
- Alt + W: Toggle the Workspace panel.
- Alt + S: Open Settings.
- Alt + K: Open the Keys panel.
- Shift + Tab: Switch to the next agent in the sidebar order.
- Alt + Right Arrow: Toggle Compute mode between High and Low.
- Alt + D: Fire (delete) the active agent. This opens a confirmation
  dialog because deleting an agent can permanently delete its chat history
  and artifacts. It does not proceed unless the user confirms.
- Alt + M: Toggle the Memory panel. When possible, returning from Memory
  restores the previously active agent; otherwise, DESK falls back to the
  first available agent or the welcome screen.
- Alt + H: Activate the first agent in the current sidebar order.

MACOS
The macOS equivalents below are expected mappings, not independently
verified shortcuts. Qt commonly maps Alt to Option on macOS, but actual
behaviour may depend on the platform and application configuration.

- Option + N: Open the New Agent dialog.
- Option + W: Toggle the Workspace panel.
- Option + S: Open Settings.
- Option + K: Open the Keys panel.
- Shift + Tab: Switch to the next agent in the sidebar order.
- Option + Right Arrow: Toggle Compute mode between High and Low.
- Option + D: Fire (delete) the active agent, subject to the confirmation
  dialog described above.
- Option + M: Toggle the Memory panel.
- Option + H: Activate the first agent in the current sidebar order.

SHORTCUT GUIDANCE
- If a user asks for shortcuts, provide the relevant platform's list.
- If the user asks how to perform a specific action, mention its shortcut
  when relevant, while also explaining the action's effect.
- Do not claim that macOS shortcuts have been tested or verified.
- Do not claim a shortcut succeeded merely because the user pressed it.
- The Fire action is destructive. Never imply that the confirmation
  dialog can be bypassed or that deletion is reversible.
- The Keys panel is the in-app destination for keyboard shortcut information.
- Do not invent additional shortcuts. If a shortcut is not listed here,
  say that it is not documented in the current shortcut reference.
""".strip()
