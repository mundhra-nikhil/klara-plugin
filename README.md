# Klara AI Implementation Plan

This repository contains the Klara Word Add-in — an AI-powered document quality assurance tool for Microsoft Word.

## Table of Contents
- [Project Structure](#project-structure)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [Getting Started](#getting-started)
- [Features](#features)

## Project Structure

```
klara-ai-implementation-plan/
├── .gitignore
├── README.md
├── klara-addin-preview.png
├── klara-addin-v2.png
├── KlaraApp/                          # Main add-in application
│   ├── .eslintrc.json                 # ESLint rules (Office Add-in plugin)
│   ├── .hintrc                        # Hint web linting config
│   ├── babel.config.json              # Babel transpilation presets
│   ├── manifest.json                  # Microsoft Teams app manifest
│   ├── manifest.xml                   # Office Add-in manifest (Word host)
│   ├── package.json                   # Dependencies & scripts
│   ├── tsconfig.json                  # TypeScript compiler options
│   ├── webpack.config.js              # Webpack 5 build configuration
│   ├── .vscode/                       # VS Code workspace settings
│   │   ├── extensions.json            # Recommended extensions
│   │   ├── launch.json                # Debug configurations (Word Desktop)
│   │   ├── settings.json              # ESLint validation settings
│   │   └── tasks.json                 # Build/lint/watch tasks
│   ├── assets/                        # Add-in icons (16px–128px PNG)
│   ├── dist/                          # Build output directory
│   └── src/
│       └── taskpane/
│           ├── index.tsx              # Entry point (Office.onReady → React render)
│           ├── taskpane.html          # HTML shell (loads Office JS API)
│           ├── taskpane.css           # Klara-specific styles (629 lines)
│           ├── global-styles.css      # Design system (light/dark themes, OKLCH)
│           ├── types.ts               # TypeScript interfaces (16 types)
│           ├── word-context.ts        # Word JavaScript API wrappers
│           ├── taskpane.ts            # Legacy text insertion utility
│           ├── api/                   # Backend API integration layer
│           │   ├── client.ts          # Axios instance with auth interceptors
│           │   ├── auth.ts            # Login, SSO, refresh, logout
│           │   ├── qc.ts              # QC findings, reviews, checklists
│           │   ├── documents.ts       # Document operations & download
│           │   ├── ai-jobs.ts         # AI job trigger, status, cancel
│           │   ├── config.ts          # POI rules & MS365 config
│           │   └── wordFeaturesApi.ts # Track changes, comments, co-authoring
│           └── components/            # React UI components
│               ├── TaskPane.tsx       # Main container + login overlay + tabs
│               ├── SuggestionsTab.tsx # AI findings list (accept/reject workflow)
│               ├── ChecksTab.tsx      # QC checklist with pass/fail status
│               ├── WorkflowsTab.tsx   # AI job triggers with progress polling
│               ├── ChatInput.tsx      # AI chat interface
│               ├── Header.tsx         # Header component
│               ├── HeroList.tsx       # Hero list component
│               ├── TextInsertion.tsx  # Text insertion component
│               └── App.tsx            # Legacy template component
└── office-js-docs-pr/                 # Microsoft Office JS documentation reference
```

## Tech Stack

- **Frontend**: React 18.2, TypeScript 5.4
- **UI Library**: Fluent UI React Components v9, Fluent UI Icons
- **Build**: Webpack 5, Babel (preset-env, preset-typescript), ts-loader
- **HTTP Client**: Axios 1.6.8 (with auth interceptors & token refresh)
- **Polyfills**: core-js, regenerator-runtime, es6-promise
- **CSS**: css-loader, style-loader, Less support
- **Office Add-in Tooling**: office-addin-debugging, office-addin-dev-certs, office-addin-lint, office-addin-manifest
- **Linting**: ESLint (office-addins plugin), Hint (web linting), Prettier
- **Target Browsers**: Last 2 versions + IE 11
- **Dev Server**: webpack-dev-server 5.2.5 (HTTPS, hot reload, port 3000)

## Architecture

The add-in follows a **three-layer design**:

### 1. UI Layer (`src/taskpane/components/`)
React components that render the task pane inside Word. Built with Fluent UI v9 for a native Office experience.

| Component | Description |
|---|---|
| `TaskPane.tsx` | Main container managing auth state, tab navigation, findings data, and chat |
| `SuggestionsTab.tsx` | Displays AI-generated QC findings with accept/reject and in-document navigation |
| `ChecksTab.tsx` | QC checklist grouped by category with pass/fail/warn/pending status |
| `WorkflowsTab.tsx` | AI job triggers (full QC, TOA, TOC, PDF comparison) with progress polling |
| `ChatInput.tsx` | AI chat interface for document queries |

### 2. Service Layer (`src/taskpane/api/`)
Axios-based API clients that communicate with the backend (`http://localhost:8000/api/v1`).

| Module | Endpoints |
|---|---|
| `client.ts` | Axios instance with `Authorization: Bearer` interceptor, 401 handling, token refresh retry |
| `auth.ts` | `POST /auth/login`, `/auth/refresh`, `/auth/logout`, `getSsoToken()` |
| `qc.ts` | `GET /qc/findings`, `PATCH /qc/findings/:id/resolve`, `GET /qc/reviews`, `GET /qc/checklists` |
| `documents.ts` | `GET /documents/:id`, `GET /documents/:id/content`, `POST /documents/:id/run-klara` |
| `ai-jobs.ts` | `POST /ai-jobs`, `GET /ai-jobs/:id`, `POST /ai-jobs/:id/cancel` |
| `config.ts` | `GET /config/poc-rules`, `GET /config/ms365` |
| `wordFeaturesApi.ts` | Track changes, AI edits, comments, co-authoring operations |

### 3. Integration Layer (`src/taskpane/word-context.ts`)
Wrappers around the Word JavaScript API for document interaction.

| Function | Description |
|---|---|
| `searchAndSelect(text, occurrence)` | Searches document and selects the Nth match |
| `highlightRange(range, color)` | Highlights a text range |
| `clearHighlights()` | Clears all highlights |
| `replaceText(text, replacement, occurrence)` | Finds and replaces text |
| `getDocumentMetadata()` | Gets document title and author |
| `getDocumentSelection()` | Gets current selection text |

## Getting Started

### Prerequisites
- Node.js 18+
- Microsoft Word (desktop)
- Microsoft 365 account (for SSO)

### Installation

```bash
cd KlaraApp
npm install
```

### Run Locally

You need to run both the backend API server and the frontend Add-in server in separate terminals.

#### 1. Run the Backend API Server

Open a terminal, navigate to the backend directory, and run the FastAPI server:

```powershell
cd backend
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

#### 2. Run the Frontend Add-in Server

Open a second terminal, navigate to the Add-in frontend directory, and start the webpack development server:

```powershell
cd KlaraApp
npm run dev-server
```

#### Additional Scripts

```bash
# Start the dev server with auto-debugging in Word
npm start

# Build for production
npm run build

# Build for development
npm run build:dev

# Watch mode (rebuild on changes)
npm run watch
```

### Linting

```bash
npm run lint
npm run lint:fix
npm run prettier
```

### Debugging
Open VS Code and use the **Word Desktop (Edge Chromium)** debug configuration to attach the DevTools debugger.

## Features

### AI-Powered Quality Control
- Automated analysis of documents for quality issues including spelling, grammar, formatting, and style inconsistencies
- Findings are ranked by severity and displayed in the Suggestions tab with original vs. replacement text diffs
- Supports multiple finding types: spelling, grammar, formatting, style, and content suggestions

### Accept/Reject Workflow
- **Accept** a finding to navigate to the text in Word, highlight it, and apply the suggested replacement
- **Reject** individual findings or reject all at once to dismiss suggestions
- **Accept All / Reject All** batch operations for quick bulk decisions
- Each finding shows the original text, suggested replacement, and severity level

### Real-Time Chat
- AI-powered chat interface for asking questions about the document
- Upload documents and get AI-assisted responses directly within the task pane
- Chat messages displayed in a conversational format with text input

### QC Checklist Management
- Pre-built quality control checklists grouped by category
- Track pass/fail/warn/pending status for each checklist item
- Click any item to navigate to the corresponding location in the document and highlight it
- Summary bar showing overall checklist completion status

### AI Workflow Automation
- **Full QC Pass** — Run comprehensive quality analysis on the document
- **Apply Client Template** — Apply organization-specific formatting rules
- **Generate TOA** — Build a Table of Authorities from citations
- **Build TOC** — Generate a Table of Contents from headings
- **Compare to Source PDF** — Validate document against source PDF
- Real-time progress tracking with cancel support

### Authentication
- Email/password login with token-based authentication
- Microsoft SSO integration via `getSsoToken()`
- Automatic token refresh on 401 responses with request retry
- Secure in-memory token storage with localStorage fallback

### Word Document Integration
- Search and select text within the document
- Highlight text ranges with configurable colors
- Replace text at specific occurrences
- Get document metadata (title, author)
- Track changes management (enable/disable, accept/reject revisions)
- Comment management (add, reply, resolve)
- Co-authoring support (active editors, presence sync, conflict resolution)
