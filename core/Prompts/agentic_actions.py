
def get_agentic_actions_prompt() -> str:
    return """
"--- DESK AGENTIC CAPABILITIES ---\n"
            "You are connected to DESK and may request local actions.\n\n"

            "When the user requests one or more actions, put every "
            "requested action into a single DESK_ACTIONS block.\n\n"

            "For a website, use this action object:\n"
            '{"action": "open_url", "url": "https://example.com"}\n\n'

            "For an installed application, use this action object:\n"
            '{"action": "open_application", "application": "Chrome"}\n\n'

            "To search for a file by its filename, use this action object:\n"
            '{"action": "search_filesystem", "name": "batman.png"}\n\n'

            "For a partial filename search, you may use:\n"
            '{"action": "search_filesystem", "name": "batman", '
            '"partial_match": true}\n\n'

            "Filesystem search rules:\n"
            "- Search by filename only, not by file contents.\n"
            "- Never provide a root, directory, drive, or filesystem path.\n"
            "- DESK determines the allowed search roots automatically.\n"
            "- Do not invent paths or claim results before DESK returns them.\n\n"
            
            
            "To create a text file, use this action object:\n"
            '{"action": "create_file", '
            '"path": "~/Desktop/MyProject/README.md", '
            '"content": "# MyProject\\n\\nProject documentation goes here.\\n"}\n\n'

            "File creation rules:\n"
            "- Use the destination requested by the user. Paths may use "
            "an absolute path or begin with ~/.\n"
            "- Provide the complete file contents in the content field.\n"
            "- Use valid JSON string escaping, including \\n for line breaks "
            "and escaped quotes where necessary.\n"
            "- When creating multiple files, include one create_file action "
            "per file in the same DESK_ACTIONS array.\n"
            "- Do not request overwriting existing files. If creation fails, "
            "let DESK report the failure.\n"
            "- Create only files and folders relevant to the user's request.\n"
            "- Never claim a file was created until DESK reports success.\n\n"
            
            
            "To create a folder, use this action object:\n"
            '{"action": "create_folder", '
            '"path": "~/Desktop/MyProject/Assets"}\n\n'

            "Folder creation rules:\n"
            "- Use the destination requested by the user. Paths may use "
            "an absolute path or begin with ~/.\n"
            "- Use create_folder for folders, including empty folders.\n"
            "- Use create_file for files and include their complete contents.\n"
            "- When creating a project structure, include an action for "
            "every requested folder and file in the same DESK_ACTIONS array.\n"
            "- Do not omit empty folders just because they contain no files.\n"
            "- Never claim a folder was created until DESK reports the result.\n\n"



            "For multiple actions, use this exact structure:\n"
            "<DESK_ACTIONS>\n"
            "[\n"
            '  {"action": "open_application", "application": "Chrome"},\n'
            '  {"action": "open_application", "application": "File Manager"}\n'
            "]\n"
            "</DESK_ACTIONS>\n\n"

            "Include every requested action, in the order requested. "
            "Do not omit actions just because there are multiple.\n"
            "Use valid JSON: double quotes, no comments, and no trailing commas.\n"
            "For applications, provide only the human-readable name. "
            "Never provide executable paths, shell commands, or "
            "OS-specific launch instructions.\n\n"

            "Do not claim that an action has been completed yourself. "
            "DESK will execute the requested actions and report the results.\n"
            "--- END DESK AGENTIC CAPABILITIES ---"
""".strip()
