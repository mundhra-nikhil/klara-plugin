# Legacy Development Workflow

*(Note: The current standard workflow is to run `npm run dev:all` inside the `KlaraApp` directory which launches everything in a single terminal via concurrently. The instructions below are kept for legacy/fallback purposes.)*

## Run Locally (Legacy 3-Terminal Approach)

You need to run both the backend API server and the frontend Add-in server in separate terminals.

#### 1. Run the Backend API Server

Open a terminal, navigate to the backend directory, and run the FastAPI server natively:

```powershell
cd KlaraApp/backend
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

#### 2. Run the Frontend Add-in Server

Open a second terminal, navigate to the Add-in frontend directory, and start the webpack development server:

```powershell
cd KlaraApp
npm run dev-server
```

#### 3. Launch Microsoft Word & Attach Debugger

Open a third terminal, navigate to the Add-in frontend directory, and start the Office add-in debugger:

```powershell
cd KlaraApp
npm start
```
