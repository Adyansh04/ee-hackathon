# Repository Guidelines

## Project Structure & Module Organization

This repository is currently a blank project scaffold. Keep new work organized by purpose as it is added:

- `src/` for application or library source code.
- `tests/` for automated tests that mirror the source layout.
- `assets/` for static files such as images, sample data, or design resources.
- `docs/` for architecture notes, API notes, and contributor-facing documentation.
- `scripts/` for repeatable local automation.

Avoid placing implementation files directly in the repository root unless they are standard project files such as `README.md`, package manifests, Docker files, or configuration.

## Build, Test, and Development Commands

No build system or dependency manifest is present yet. When adding one, document exact commands in `README.md`. Preferred examples:

- `npm install` or equivalent: install project dependencies.
- `npm run dev`: start the local development server.
- `npm test`: run the full automated test suite.
- `npm run lint`: run formatting and static checks.

If Docker or Make is added later, expose common workflows through commands such as `make test` or `docker compose up`.

## Coding Style & Naming Conventions

Follow the formatter and linter configured for the first implementation language. Until then, use 2-space indentation for web code, 4-space indentation for Python, descriptive filenames, and lowercase directory names. Prefer clear module names such as `src/api/client.ts`, `src/components/user-card.tsx`, or `tests/api/test_client.py`.

Keep functions small, name variables by domain meaning, and avoid broad utility modules until repeated patterns justify them.

## Testing Guidelines

Add tests alongside new functionality. Mirror source paths in `tests/` and use framework-standard naming, such as `*.test.ts`, `*.spec.ts`, or `test_*.py`. Cover normal behavior, key edge cases, and user-facing failures. Every feature should include tests or a pull request note explaining why tests were not practical.

## Commit & Pull Request Guidelines

There is no existing commit history to derive conventions from. Use concise, imperative commit messages, for example `Add project scaffold` or `Implement login form`. Pull requests should include a summary, validation steps, linked issues when applicable, and screenshots or recordings for UI changes.

Before requesting review, run the relevant build, test, and lint commands and note any skipped checks.

## Security & Configuration Tips

Do not commit secrets, local credentials, generated dependency folders, or machine-specific files. Use ignored local environment files such as `.env.local` and provide a committed example file, such as `.env.example`, when configuration is required.
