---
name: run-opencode
description: Run OpenCode CLI for AI-powered code analysis, refactoring, and troubleshooting. Use for direct prompts, file context analysis, and terminal output processing.
---

# OpenCode CLI

OpenCode is an AI-powered coding assistant CLI that can analyze code, refactor files, fix errors, and process terminal output.

## Installation

OpenCode should be installed globally via npm:

```bash
npm install -g opencode
```

Check installation:

```bash
opencode --version
```

## Basic Usage

### Run Direct Prompts

Execute a prompt against your project files:

```bash
opencode run "Explain what the main entry point of this project does"
```

### File Context Analysis

Include specific files in your prompt using the `@` symbol:

```bash
opencode run "Refactor @src/index.js to use modern async/await syntax"
```

Multiple files:

```bash
opencode run "Update @src/api/client.ts and @src/utils/helpers.ts to use the new error handling pattern"
```

### Terminal Output Processing

Pipe terminal output directly into OpenCode for debugging and analysis:

```bash
# Fix failing tests
npm test | opencode run "Fix whatever error is causing this test suite to fail"

# Generate git commit messages
git diff | opencode run "Generate a clear, professional git commit message based on these changes"

# Analyze build errors
npm run build 2>&1 | opencode run "Explain and fix these build errors"
```

### Session Management

Continue the last session:

```bash
opencode run --continue "Continue with the refactoring"
```

Fork a session before continuing:

```bash
opencode run --session <session-id> --fork "Try a different approach"
```

## Common Workflows

### Code Review

```bash
# Review recent changes
git diff HEAD~1 | opencode run "Review this diff for potential bugs and improvements"

# Review specific file
opencode run "Review @src/components/Header.tsx for accessibility issues"
```

### Error Troubleshooting

```bash
# Debug test failures
pytest | opencode run "Analyze these test failures and suggest fixes"

# Debug runtime errors
cat error.log | opencode run "Explain this error and suggest how to fix it"
```

### Refactoring

```bash
# Apply coding standards
opencode run "Refactor @src/utils/formatters.ts to follow TypeScript best practices"

# Performance optimization
opencode run "Optimize @src/api/client.ts for better performance"
```

### Documentation

```bash
# Generate documentation
opencode run "Generate JSDoc comments for @src/utils/helpers.ts"

# Update README
opencode run "Update the README.md to reflect the new API changes"
```

## Advanced Options

### Model Selection

```bash
opencode run --model anthropic/claude-3-opus "Analyze this code"
```

### Session Management

```bash
# List sessions
opencode session list

# Continue specific session
opencode run --session abc123 --continue "Continue the work"

# Fork session
opencode run --session abc123 --fork "Try alternative approach"
```

### File Attachments

```bash
opencode run --file src/main.ts --file config.json "Analyze these files"
```

### Output Format

```bash
# JSON output for scripting
opencode run --format json "Analyze this code" > output.json
```

## Tips

- **Use specific file paths** with `@` for focused analysis
- **Pipe relevant output** (errors, diffs, logs) for context-aware troubleshooting
- **Continue sessions** to maintain context across multiple interactions
- **Use clear, specific prompts** for better results
- **Chain commands** for complex workflows: `git diff | opencode run "..." | apply-fixes`

## Gotchas

- OpenCode requires network connectivity to reach AI providers
- File paths with `@` must be relative to current directory
- Piped input is treated as context, not as the primary prompt
- Session continuity depends on session ID persistence
- Large file outputs may need to be trimmed before piping

## Troubleshooting

### Command not found

```bash
# Check OpenCode is installed
which opencode

# Reinstall if needed
npm install -g opencode
```

### File context not working

Ensure file paths are correct and relative to current directory:

```bash
# Correct
opencode run "Analyze @src/index.ts"

# Incorrect (absolute path)
opencode run "Analyze @/usr/local/project/src/index.ts"
```

### Pipe not processing

Some commands buffer output. Use `2>&1` to merge stderr:

```bash
npm test 2>&1 | opencode run "Fix these errors"
```

### Session lost

Sessions have limited retention. For important work, save outputs:

```bash
opencode run "Complex analysis" > analysis-results.txt
```
