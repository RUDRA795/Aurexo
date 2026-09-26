import { spawn } from 'node:child_process';
import path from 'node:path';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const rootDir = path.resolve(__dirname, '..');
const backendDir = path.resolve(rootDir, 'backend');
const frontendDir = path.resolve(rootDir, 'uiux');

function getPythonExecutable() {
  const isWin = process.platform === 'win32';
  const venvWin = path.join(backendDir, '.venv', 'Scripts', 'python.exe');
  const venvPosix = path.join(backendDir, '.venv', 'bin', 'python');

  if (isWin && fs.existsSync(venvWin)) return venvWin;
  if (!isWin && fs.existsSync(venvPosix)) return venvPosix;
  return isWin ? 'python' : 'python3';
}

console.log('\x1b[36m%s\x1b[0m', `
===============================================================
  ORCA — Marine EcOsystem Reasoning with Collaborative Agents
===============================================================
  [SINGLE-COMMAND RUNTIME]
  --> Primary Application: http://localhost:3000
  --> Same-Origin API:     http://localhost:3000/api/*
  --> FastAPI Backend:     http://127.0.0.1:8000
  Press Ctrl+C to stop all services.
===============================================================
`);

const pythonPath = getPythonExecutable();
console.log(`[ORCA Orchestrator] Using Python runtime: ${pythonPath}`);

// Spawn backend
const backendProc = spawn(pythonPath, ['run.py'], {
  cwd: backendDir,
  stdio: ['inherit', 'pipe', 'pipe'],
  env: { ...process.env, PYTHONUNBUFFERED: '1' }
});

backendProc.stdout.on('data', (data) => {
  const lines = data.toString().trimEnd().split('\n');
  for (const line of lines) {
    if (line.trim()) console.log(`\x1b[34m[BACKEND]\x1b[0m ${line}`);
  }
});

backendProc.stderr.on('data', (data) => {
  const lines = data.toString().trimEnd().split('\n');
  for (const line of lines) {
    if (line.trim()) console.error(`\x1b[33m[BACKEND]\x1b[0m ${line}`);
  }
});

// Spawn frontend
const isWin = process.platform === 'win32';
const frontendProc = isWin
  ? spawn('cmd.exe', ['/c', 'npm', 'run', 'dev'], {
      cwd: frontendDir,
      stdio: ['inherit', 'pipe', 'pipe']
    })
  : spawn('npm', ['run', 'dev'], {
      cwd: frontendDir,
      stdio: ['inherit', 'pipe', 'pipe']
    });

frontendProc.stdout.on('data', (data) => {
  const lines = data.toString().trimEnd().split('\n');
  for (const line of lines) {
    if (line.trim()) console.log(`\x1b[35m[FRONTEND]\x1b[0m ${line}`);
  }
});

frontendProc.stderr.on('data', (data) => {
  const lines = data.toString().trimEnd().split('\n');
  for (const line of lines) {
    if (line.trim()) console.error(`\x1b[31m[FRONTEND]\x1b[0m ${line}`);
  }
});

let isShuttingDown = false;
function cleanup() {
  if (isShuttingDown) return;
  isShuttingDown = true;
  console.log('\n[ORCA Orchestrator] Shutting down all processes...');
  if (process.platform === 'win32') {
    if (backendProc.pid) {
      try { spawn('taskkill', ['/pid', backendProc.pid.toString(), '/f', '/t']); } catch {}
    }
    if (frontendProc.pid) {
      try { spawn('taskkill', ['/pid', frontendProc.pid.toString(), '/f', '/t']); } catch {}
    }
  } else {
    try { backendProc.kill('SIGTERM'); } catch {}
    try { frontendProc.kill('SIGTERM'); } catch {}
  }
  process.exit(0);
}

process.on('SIGINT', cleanup);
process.on('SIGTERM', cleanup);
