---
name: arch-aware-coder
description: Enforces reading architecture docs and checking for existing functions before writing new features or fixing code.
---

# Architecture-Aware Coder

When the user asks to "implement a new feature", "modify the database", "fix code", "fix_code", or explicitly invokes "use arch-aware-coder", follow these steps strictly before writing any code:

1. **Understand Architecture:** Use the `view_file` tool to read `ARCH.md` and `DB_ARCH.md` (if you haven't already in this session) to ensure you understand the project structure, dependencies, and database schemas.
2. **Plan the Logic:** Break down the user's request into the necessary functions, bug fixes, and database queries needed.
3. **Search for Existing Code:** Before implementing a new function to solve a problem or fix a bug, use `grep_search` or `view_file` on utility/service files to check if a function that solves this problem (or a similar one) already exists in the codebase.
4. **Code:** Only write a new function if you have verified that an existing one cannot be reused or adapted. When fixing code, ensure the fix aligns with the patterns defined in the architecture documents.
