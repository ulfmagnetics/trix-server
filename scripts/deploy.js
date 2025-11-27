#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// Read deployment configuration from project root
const projectRoot = path.join(__dirname, '..');
const configPath = path.join(projectRoot, 'deploy-config.json');
let config;

try {
  const configData = fs.readFileSync(configPath, 'utf8');
  config = JSON.parse(configData);
} catch (error) {
  console.error('Error reading deploy-config.json:', error.message);
  process.exit(1);
}

const sourceDir = path.join(projectRoot, config.sourceDir);
const buildDir = path.join(sourceDir, 'build');
const targetDrive = config.targetDrive;

console.log('MatrixPortal Deployment with mpy-cross');
console.log('=======================================');
console.log(`Source: ${sourceDir}`);
console.log(`Target: ${targetDrive}`);
console.log('');

// Check if source directory exists
if (!fs.existsSync(sourceDir)) {
  console.error(`Error: Source directory '${sourceDir}' does not exist.`);
  process.exit(1);
}

// Check if target drive exists
if (!fs.existsSync(targetDrive)) {
  console.error(`Error: Target drive '${targetDrive}' is not accessible.`);
  console.error('Make sure your MatrixPortal is connected and mounted.');
  process.exit(1);
}

// Files that should remain as .py (not compiled)
const keepAsPython = new Set(['code.py', 'boot.py', 'secrets.py', 'config.py']);

// Files that should be deleted (have .mpy versions)
const filesToDelete = [
  'display.py',
  'context.py',
  'crash_logger.py',
  'utils.py',
  path.join('routes', '__init__.py'),
  path.join('routes', 'display.py'),
  path.join('routes', 'fetch.py'),
  path.join('routes', 'clear.py'),
  path.join('routes', 'crash.py')
];

/**
 * Step 1: Run build.sh via WSL to compile Python modules
 */
function buildMpyFiles() {
  console.log('[1/4] Compiling Python modules with mpy-cross...');
  console.log('');

  try {
    // Convert Windows path to WSL path
    const wslProjectPath = projectRoot.replace(/\\/g, '/').replace(/^([A-Z]):/, (_match, drive) => {
      return `/mnt/${drive.toLowerCase()}`;
    });

    // Run build.sh in WSL Ubuntu 24.04
    const buildCommand = `wsl -d Ubuntu-24.04 bash -c "cd '${wslProjectPath}' && ./build.sh"`;
    execSync(buildCommand, { stdio: 'inherit' });

    console.log('');
    console.log('Build complete!');
    console.log('');
  } catch (error) {
    console.error('Build failed:', error.message);
    console.error('');
    console.error('Make sure:');
    console.error('  1. WSL is installed and configured');
    console.error('  2. mpy-cross is installed in WSL at /usr/local/bin/mpy-cross');
    console.error('  3. build.sh has execute permissions (chmod +x build.sh)');
    process.exit(1);
  }
}

/**
 * Step 2: Delete old .py files that now have .mpy versions
 */
function deleteOldPyFiles() {
  console.log('[2/4] Cleaning old .py files from target...');

  let deletedCount = 0;
  for (const relPath of filesToDelete) {
    const targetPath = path.join(targetDrive, relPath);
    if (fs.existsSync(targetPath)) {
      try {
        fs.unlinkSync(targetPath);
        console.log(`  Deleted: ${relPath}`);
        deletedCount++;
      } catch (error) {
        console.error(`  Failed to delete ${relPath}: ${error.message}`);
      }
    }
  }

  if (deletedCount === 0) {
    console.log('  No old .py files to delete');
  }
  console.log('');
}

/**
 * Step 3: Copy compiled .mpy files from build directory
 */
function copyMpyFiles() {
  console.log('[3/4] Copying compiled .mpy files...');

  if (!fs.existsSync(buildDir)) {
    console.error(`Error: Build directory '${buildDir}' does not exist.`);
    console.error('Run the build step first.');
    process.exit(1);
  }

  // Copy root-level .mpy files
  const buildFiles = fs.readdirSync(buildDir);
  for (const file of buildFiles) {
    if (file.endsWith('.mpy')) {
      const srcPath = path.join(buildDir, file);
      const destPath = path.join(targetDrive, file);
      fs.copyFileSync(srcPath, destPath);
      console.log(`  Copied: ${file}`);
    }
  }

  // Copy routes/ .mpy files
  const buildRoutesDir = path.join(buildDir, 'routes');
  if (fs.existsSync(buildRoutesDir)) {
    const targetRoutesDir = path.join(targetDrive, 'routes');
    if (!fs.existsSync(targetRoutesDir)) {
      fs.mkdirSync(targetRoutesDir, { recursive: true });
    }

    const routeFiles = fs.readdirSync(buildRoutesDir);
    for (const file of routeFiles) {
      if (file.endsWith('.mpy')) {
        const srcPath = path.join(buildRoutesDir, file);
        const destPath = path.join(targetRoutesDir, file);
        fs.copyFileSync(srcPath, destPath);
        console.log(`  Copied: routes/${file}`);
      }
    }
  }

  console.log('');
}

/**
 * Step 4: Copy non-compiled .py files (code.py, boot.py, etc.)
 */
function copyPyFiles() {
  console.log('[4/4] Copying non-compiled .py files...');

  for (const file of keepAsPython) {
    const srcPath = path.join(sourceDir, file);
    if (fs.existsSync(srcPath)) {
      const destPath = path.join(targetDrive, file);
      fs.copyFileSync(srcPath, destPath);
      console.log(`  Copied: ${file}`);
    } else {
      console.log(`  Skipped: ${file} (not found)`);
    }
  }

  console.log('');
}

// Perform the deployment
try {
  buildMpyFiles();
  deleteOldPyFiles();
  copyMpyFiles();
  copyPyFiles();

  console.log('=======================================');
  console.log('Deployment complete!');
  console.log('=======================================');
  console.log('');
  console.log('Your MatrixPortal should reset and run with compiled .mpy modules.');
  console.log('Expected memory improvement: 9-14 KB more free RAM');
} catch (error) {
  console.error('Deployment failed:', error.message);
  process.exit(1);
}
