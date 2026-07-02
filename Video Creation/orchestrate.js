/**
 * orchestrate.js
 * Your Company — Video Studio Environment Detection
 *
 * Deployment target: Windows PCs with NVIDIA GPUs (8GB+ VRAM). HYBRID mode
 * is the canonical path — Runway generates cinematic B-roll, HyperFrames
 * assembles locally on the GPU.
 *
 * The script runs in two contexts:
 *   1. On the host Windows machine (PowerShell/cmd) — full detection, writes
 *      .runway-route.json so the Cowork sandbox can reuse the result.
 *   2. Inside the Cowork bash sandbox (Linux) — reads the cached
 *      .runway-route.json written by a previous host-side run.
 *
 * Env overrides (from .env):
 *   FORCE_ENGINE=HYBRID | HYPERFRAMES_LOCAL | RUNWAY_CHROME
 *
 * Engines (Windows-only deployment):
 *   HYBRID            Windows + NVIDIA → recommended. Runway B-roll + HyperFrames.
 *   HYPERFRAMES_LOCAL Windows, no NVIDIA detected → CPU rendering only.
 *   RUNWAY_CHROME     Cloud Runway only. Use if HyperFrames can't run locally.
 */

const os = require('os');
const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const VRAM_FLOOR_GB = 6;   // Below this, HyperFrames GPU rendering is unreliable
const VRAM_TARGET_GB = 8;  // Joseph's deployment baseline

function loadDotenv() {
  const envPath = path.join(__dirname, '.env');
  if (!fs.existsSync(envPath)) return;
  const text = fs.readFileSync(envPath, 'utf8');
  for (const rawLine of text.split('\n')) {
    const line = rawLine.trim();
    if (!line || line.startsWith('#')) continue;
    const eq = line.indexOf('=');
    if (eq < 0) continue;
    const key = line.slice(0, eq).trim();
    let val = line.slice(eq + 1).trim();
    if ((val.startsWith('"') && val.endsWith('"')) ||
        (val.startsWith("'") && val.endsWith("'"))) {
      val = val.slice(1, -1);
    }
    if (!(key in process.env)) {
      process.env[key] = val;
    }
  }
}

loadDotenv();

function detectGPU() {
  // Returns { hasNvidiaGPU, gpuName, vramMb }
  let hasNvidiaGPU = false;
  let gpuName = 'None detected';
  let vramMb = null;

  // Primary: nvidia-smi for name + total memory in MB
  try {
    const result = execSync(
      'nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits',
      { stdio: ['ignore', 'pipe', 'ignore'], encoding: 'utf8' }
    ).trim();
    if (result) {
      const first = result.split('\n')[0].trim();
      const parts = first.split(',').map(s => s.trim());
      if (parts.length >= 2) {
        hasNvidiaGPU = true;
        gpuName = parts[0];
        vramMb = parseInt(parts[1], 10) || null;
      }
    }
  } catch (e) {
    hasNvidiaGPU = false;
  }

  // Fallback: PowerShell Get-CimInstance for name only (no VRAM)
  if (!hasNvidiaGPU) {
    try {
      const ps = execSync(
        'powershell -NoProfile -Command "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"',
        { stdio: ['ignore', 'pipe', 'ignore'], encoding: 'utf8' }
      );
      gpuName = ps.split('\n').map(l => l.trim()).filter(Boolean)[0] || 'Unknown GPU';
    } catch (e) {
      // ignore
    }
  }

  return { hasNvidiaGPU, gpuName, vramMb };
}

function detectEnvironment() {
  const platform = os.platform();   // 'win32' on host, 'linux' in Cowork sandbox
  const arch = os.arch();
  const cpus = os.cpus();
  const cpuModel = cpus[0]?.model || 'Unknown';
  const cpuCount = cpus.length;
  const totalRAMgb = Math.round(os.totalmem() / 1024 / 1024 / 1024);
  const freeRAMgb = Math.round(os.freemem() / 1024 / 1024 / 1024);
  const nodeVersion = process.version;

  let gpu = { hasNvidiaGPU: false, gpuName: 'None detected', vramMb: null };
  if (platform === 'win32') {
    gpu = detectGPU();
  }
  const vramGb = gpu.vramMb ? Math.round(gpu.vramMb / 1024) : null;

  let hyperframesAvailable = false;
  try {
    execSync('npx --no-install hyperframes --version', {
      stdio: ['ignore', 'ignore', 'ignore'],
      timeout: 5000
    });
    hyperframesAvailable = true;
  } catch (e) {
    hyperframesAvailable = false;
  }

  const sharedAssetsPath = path.join(__dirname, 'src', 'shared_assets');
  let sharedAssets = [];
  try {
    sharedAssets = fs.readdirSync(sharedAssetsPath).filter(f =>
      ['.mp4', '.webm', '.mov', '.png', '.jpg', '.jpeg', '.gif', '.wav', '.mp3'].includes(
        path.extname(f).toLowerCase()
      )
    );
  } catch (e) { /* folder may not exist yet */ }

  let recommendedEngine;
  let engineReason;
  let hybridCapable = false;
  let resolvedFrom = 'auto-detect';
  const warnings = [];

  const forced = process.env.FORCE_ENGINE;
  if (forced && ['HYBRID', 'HYPERFRAMES_LOCAL', 'RUNWAY_CHROME'].includes(forced)) {
    recommendedEngine = forced;
    engineReason = 'FORCE_ENGINE=' + forced + ' set in environment / .env — overriding auto-detection.';
    hybridCapable = (forced === 'HYBRID');
    resolvedFrom = 'FORCE_ENGINE';
  } else if (platform === 'linux') {
    // Cowork bash sandbox. Read the cached host-side detection if present.
    const routePath = path.join(__dirname, '.runway-route.json');
    if (fs.existsSync(routePath)) {
      try {
        const saved = JSON.parse(fs.readFileSync(routePath, 'utf8'));
        recommendedEngine = (saved.routing && saved.routing.recommendedEngine) || 'HYBRID';
        engineReason = 'Cowork sandbox (Linux). Reusing host-side detection from .runway-route.json (written ' + saved.timestamp + ').';
        hybridCapable = (saved.routing && saved.routing.hybridCapable) || false;
        resolvedFrom = 'cached host detection';
      } catch (e) {
        recommendedEngine = 'HYBRID';
        engineReason = 'Cowork sandbox, .runway-route.json present but unreadable. Defaulting to HYBRID (deployment target).';
        resolvedFrom = 'fallback';
        warnings.push('Could not parse .runway-route.json — run `node orchestrate.js` on the Windows host to repopulate.');
      }
    } else {
      recommendedEngine = 'HYBRID';
      engineReason = 'Cowork sandbox (Linux). No host-side detection cache. Defaulting to HYBRID since deployment target is Windows + NVIDIA. Run `node orchestrate.js` on the host machine to confirm GPU + VRAM, or set FORCE_ENGINE in .env.';
      resolvedFrom = 'fallback (deployment default)';
      warnings.push('No .runway-route.json cache. Run orchestrate.js on the Windows host once to populate.');
    }
  } else if (platform === 'win32' && gpu.hasNvidiaGPU) {
    recommendedEngine = 'HYBRID';
    engineReason = 'Windows + NVIDIA GPU detected (' + gpu.gpuName + (vramGb ? ', ' + vramGb + 'GB VRAM' : '') + '). HYBRID mode active.';
    hybridCapable = true;
    if (vramGb !== null && vramGb < VRAM_FLOOR_GB) {
      warnings.push('VRAM ' + vramGb + 'GB is below the ' + VRAM_FLOOR_GB + 'GB floor for reliable HyperFrames GPU rendering. Consider HYPERFRAMES_LOCAL (CPU) for heavy shader transitions or large composites.');
    } else if (vramGb !== null && vramGb < VRAM_TARGET_GB) {
      warnings.push('VRAM ' + vramGb + 'GB is below the ' + VRAM_TARGET_GB + 'GB deployment target. HYBRID will work but expect slower renders on 4K and shader-heavy scenes.');
    }
  } else if (platform === 'win32' && !gpu.hasNvidiaGPU) {
    recommendedEngine = 'HYPERFRAMES_LOCAL';
    engineReason = 'Windows detected, no NVIDIA GPU found via nvidia-smi. Falling back to HyperFrames CPU mode. Runway B-roll still available via Chrome MCP.';
    hybridCapable = false;
    warnings.push('No NVIDIA GPU detected. If a card is installed, ensure nvidia-smi is on PATH (typically C:\\Windows\\System32\\nvidia-smi.exe).');
  } else {
    recommendedEngine = 'RUNWAY_CHROME';
    engineReason = 'Unrecognized environment (' + platform + '/' + arch + '). Deployment target is Windows — this script is not expected to run here. Defaulting to cloud Runway workflow.';
    hybridCapable = false;
    resolvedFrom = 'fallback';
    warnings.push('Platform is not Windows. Joseph confirmed this project runs on Windows PCs only.');
  }

  const result = {
    timestamp: new Date().toISOString(),
    machine: {
      platform: platform === 'win32' ? 'Windows' : platform,
      arch,
      cpuModel,
      cpuCount,
      totalRAMgb,
      freeRAMgb,
      node: nodeVersion
    },
    gpu: {
      hasNvidiaGPU: gpu.hasNvidiaGPU,
      gpuName: gpu.gpuName,
      vramMb: gpu.vramMb,
      vramGb,
      vramFloorGb: VRAM_FLOOR_GB,
      vramTargetGb: VRAM_TARGET_GB
    },
    capabilities: {
      hyperframesAvailable,
      hyperframesInstallCmd: hyperframesAvailable ? null : 'npx skills add heygen-com/hyperframes && npm install',
      runwayChrome: true,
      sharedAssetsCount: sharedAssets.length,
      sharedAssets
    },
    routing: {
      recommendedEngine,
      engineReason,
      hybridCapable,
      resolvedFrom,
      hybridMode: hybridCapable
        ? 'Runway generates cinematic B-roll → saved to src/shared_assets/ → HyperFrames assembles final video locally on GPU'
        : null
    },
    warnings
  };

  console.log(JSON.stringify(result, null, 2));

  // Write .runway-route.json from the host machine only, never from the
  // Cowork Linux sandbox (which would overwrite the host detection).
  if (platform === 'win32') {
    try {
      const routePath = path.join(__dirname, '.runway-route.json');
      fs.writeFileSync(routePath, JSON.stringify(result, null, 2), 'utf8');
    } catch (e) {
      console.error('Warning: could not write .runway-route.json:', e.message);
    }
  }

  return result;
}

detectEnvironment();
