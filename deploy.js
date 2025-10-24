#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

// Read deployment configuration
const configPath = path.join(__dirname, 'deploy-config.json');
let config;

try {
  const configData = fs.readFileSync(configPath, 'utf8');
  config = JSON.parse(configData);
} catch (error) {
  console.error('Error reading deploy-config.json:', error.message);
  process.exit(1);
}

const sourceDir = path.join(__dirname, config.sourceDir);
const targetDrive = config.targetDrive;

console.log('MatrixPortal Deployment');
console.log('=======================');
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

/**
 * Recursively copy files from source to destination
 */
function copyDirectory(src, dest) {
  const entries = fs.readdirSync(src, { withFileTypes: true });

  for (const entry of entries) {
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);

    if (entry.isDirectory()) {
      // Create directory if it doesn't exist
      if (!fs.existsSync(destPath)) {
        fs.mkdirSync(destPath, { recursive: true });
      }
      copyDirectory(srcPath, destPath);
    } else {
      // Copy file
      fs.copyFileSync(srcPath, destPath);
      console.log(`Copied: ${entry.name}`);
    }
  }
}

// Perform the deployment
try {
  console.log('Deploying files...');
  copyDirectory(sourceDir, targetDrive);
  console.log('');
  console.log('Deployment complete!');
  console.log('Your MatrixPortal should reset and run the new code.');
} catch (error) {
  console.error('Deployment failed:', error.message);
  process.exit(1);
}
