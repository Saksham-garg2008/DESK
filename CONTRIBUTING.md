# Contributing to DESK

Thank you for your interest in contributing to DESK.

DESK is an open-source project, and contributions can include code, documentation, testing, bug reports, ideas, and improvements to the developer experience.

## Before You Start

Take a moment to understand the part of DESK you want to change.

The project separates responsibilities across areas such as:

- `ui/` — PySide6 interface
- `core/` — application logic
- `config/` — configuration
- `workspace/` — workspace-related data
- `bucket/` — application resources

For changes involving AI actions, pay particular attention to:

- `core/agent_protocol.py`
- `core/agent_actions.py`

Try to keep UI code, AI reasoning, and operating-system-specific execution separate.

## Development Setup

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

Install the project dependencies:

```bash
pip install -r requirements.txt
```

Run DESK:

```bash
python main.py
```

## Keep Changes Focused

Prefer small, focused changes over large rewrites.

Focused changes are easier to:

- Test
- Review
- Debug
- Revert
- Understand later

Avoid changing unrelated parts of the application in the same commit unless the changes are genuinely connected.

## Cross-Platform Development

DESK is designed for Windows, Linux, and macOS.

When adding operating-system-specific functionality:

- Avoid assuming a fixed executable path.
- Avoid hardcoding application locations.
- Keep platform-specific behavior isolated.
- Prefer operating-system mechanisms over assumptions about a user's setup.

A feature that works on one machine is not necessarily portable.

## Android Companion

The repository also contains the code for the **DESK Android Companion** inside the `Companion/` directory.

Contributions to the Android Companion are welcome, but changes should remain clearly separated from the desktop application where possible.

### Companion Structure

The Android Companion lives under:

```text
Companion/
```

When working on the Companion:

- Keep Android-specific code inside `Companion/`.
- Avoid introducing Android-specific dependencies into the main desktop application.
- Keep communication between DESK and the Companion clearly defined.
- Do not duplicate desktop-side functionality inside the Companion unless there is a clear reason.
- Document any changes that affect communication or shared behavior between DESK and Companion.

### Working on Companion Features

Before modifying the Companion:

1. Understand how the existing Companion code communicates with DESK.
2. Identify whether the change affects only Android or also requires desktop-side changes.
3. Keep platform-specific logic within the appropriate component.
4. Test the Companion independently where possible.
5. If a change affects both sides, test the complete DESK ↔ Companion workflow.

### Cross-Platform Considerations

DESK is intended to work across desktop platforms, while the Companion is Android-specific.

When contributing code that involves both:

```text
DESK Desktop
     │
     │  Communication / Integration
     ▼
Android Companion
```

Keep the boundary between the two components explicit. A change to one side should not unnecessarily introduce platform-specific assumptions into the other.

### Companion Pull Requests

For pull requests involving the Companion, clearly mention:

- What was changed in `Companion/`
- Whether the desktop application was also modified
- Whether communication between DESK and Companion was affected
- How the change was tested
- Any Android-specific requirements needed to reproduce the change

If a change affects both the desktop application and Companion, explain the interaction between the two in the pull request description.

## Agentic Actions

DESK intentionally separates AI-generated intent from local execution.

When working on agentic functionality, preserve this separation.

The AI should express **what it wants to accomplish**, while DESK remains responsible for interpreting, validating, and executing supported actions.

Do not introduce unrestricted shell execution or direct arbitrary system access as a shortcut for implementing an action.

## Testing

Before submitting a change:

1. Run DESK locally.
2. Test the functionality you changed.
3. Check that existing functionality still works.
4. Consider behavior on other supported operating systems.
5. Verify that persistent user data and configuration are not unintentionally affected.

For UI changes, test the relevant interaction manually.

For action-related changes, test both valid requests and requests that should not execute.

## Commit Messages

Keep commit messages concise and descriptive.

Good examples:

```text
Add application discovery for Linux
Fix persistent workspace paths
Improve Chrome profile handling
Update agent action validation
```

Avoid vague messages such as:

```text
changes
update
stuff
fix
```

## Pull Requests

A pull request should explain:

- What changed
- Why it changed
- How it was tested
- Any platform-specific considerations

Keep pull requests focused on one logical change where possible.

## Bug Reports

When reporting a bug, include:

- DESK version
- Operating system
- Steps to reproduce
- Expected behavior
- Actual behavior
- Relevant error messages or logs
- Any useful configuration details

A clear reproduction case makes debugging substantially easier.

## Feature Suggestions

Feature suggestions are welcome.

Describe:

- What you would like DESK to do
- Why it would be useful
- How you expect the interaction to work

Avoid prescribing an implementation unless the implementation itself is important to the proposal.

## Code Style

Follow the existing style of the codebase.

Prefer:

- Clear names
- Small functions
- Focused modules
- Explicit behavior
- Minimal dependencies

Avoid unnecessary abstractions when a simpler implementation is sufficient.

## Documentation

If a change alters an existing behavior or developer workflow, update the relevant documentation when appropriate.

Documentation should describe the current behavior rather than speculative future functionality.

## Final Check

Before opening a pull request, make sure:

- [ ] The project starts successfully.
- [ ] The changed functionality has been tested.
- [ ] Existing functionality still works.
- [ ] No unnecessary dependencies were introduced.
- [ ] No machine-specific paths were hardcoded.
- [ ] Persistent user data is not unintentionally affected.
- [ ] Documentation was updated if necessary.
