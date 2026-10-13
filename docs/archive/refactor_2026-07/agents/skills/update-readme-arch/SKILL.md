---
name: update-readme-arch
description: Guidelines for syncing README.md and docs/ARCH.md with system changes, removing deprecated components, adding new ones, and detailing the new backtest system.
---

# System Documentation Sync Guidelines (README.md & ARCH.md)

When requested to update documentation, improve the system, or when any changes are made to the codebase structure (especially regarding the new backtest system), strictly adhere to the following workflow:

## 1. Document Synchronization & Cleanup
*   **Remove deprecated information:** Review the existing [README.md](file:///f:/Projects/alpha_farm/README.md) and [ARCH.md](file:///f:/Projects/alpha_farm/docs/ARCH.md) files, and remove all descriptions, instructions, diagrams, or code samples related to components, libraries, or modules that have been removed or replaced.
*   **Document new features:** Add comprehensive details regarding new modules, functionalities, directory structures, APIs, or dependencies integrated into the system.

## 2. Detail the New Backtest System
When updating or adding features to the new backtest system, ensure the documentation in [README.md](file:///f:/Projects/alpha_farm/README.md) is highly detailed and includes:
*   **Architecture & Workflow:** Explain how the backtest engine ingests data, executes strategies, and outputs results.
*   **Configuration Guide:** Define all configuration files, input parameters, required environment variables, and their corresponding formats.
*   **Operations Guide:** Provide specific commands to run the backtest, practical usage examples, and guides on how to interpret/analyze output metrics.

## 3. General Documentation Principles
*   **Align with Reality:** All documentation must accurately reflect 100% of the current codebase state. Never include speculative details or unimplemented features.
*   **Structured Formatting:** Use standard Markdown formatting (tables, Mermaid diagrams if applicable, and code blocks) to make documents readable, clean, and professional.
