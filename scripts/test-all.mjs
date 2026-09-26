import { spawnSync } from 'node:child_process';
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

console.log('\x1b[36m%s\x1b[0m', '=== Running Frontend Lint & Typecheck ===');
const isWin = process.platform === 'win32';
const npmCmd = isWin ? 'npm.cmd' : 'npm';
const lintRes = spawnSync(npmCmd, ['run', 'lint'], { cwd: frontendDir, stdio: 'inherit', shell: isWin });
if (lintRes.status !== 0) {
  console.error('\x1b[31m[ERROR] Frontend lint failed!\x1b[0m');
  process.exit(lintRes.status || 1);
}

console.log('\x1b[36m%s\x1b[0m', '\n=== Running Backend Pytest ===');
const pythonPath = getPythonExecutable();
const testRes = spawnSync(pythonPath, ['-m', 'pytest', '-q'], { cwd: backendDir, stdio: 'inherit', shell: isWin });
if (testRes.status !== 0) {
  console.error('\x1b[31m[ERROR] Backend test suite failed!\x1b[0m');
  process.exit(testRes.status || 1);
}

console.log('\x1b[32m%s\x1b[0m', '\n[SUCCESS] All frontend and backend checks passed cleanly!');
