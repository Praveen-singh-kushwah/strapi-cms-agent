const path = require('node:path');
const { spawnSync } = require('node:child_process');

const MAX_OUTPUT_CHARS = 3000;

function parseArgs(argv) {
  const options = {
    skipImport: false,
  };

  for (const arg of argv) {
    if (arg === '--skip-import') {
      options.skipImport = true;
    }
  }

  return options;
}

function npmCommandArgs(scriptName, extraArgs = []) {
  const npmExecPath = process.env.npm_execpath;
  if (npmExecPath) {
    return {
      command: process.execPath,
      args: [npmExecPath, 'run', scriptName, ...extraArgs],
    };
  }

  return {
    command: process.platform === 'win32' ? 'npm.cmd' : 'npm',
    args: ['run', scriptName, ...extraArgs],
  };
}

function nodeScriptArgs(scriptName, args = []) {
  return {
    command: process.execPath,
    args: [path.resolve(__dirname, scriptName), ...args],
  };
}

function runCommand(stepName, command, args) {
  const result = spawnSync(command, args, {
    cwd: path.resolve(__dirname, '..'),
    env: {
      ...process.env,
      STRAPI_TELEMETRY_DISABLED: 'true',
      XDG_CONFIG_HOME: process.env.XDG_CONFIG_HOME || path.resolve(__dirname, '..', '.xdg-config'),
    },
    encoding: 'utf8',
    maxBuffer: 1024 * 1024 * 20,
    shell: false,
  });

  const stdout = result.stdout || '';
  const stderr = result.stderr || '';
  const combinedOutput = [stdout, stderr].filter(Boolean).join('\n');

  return {
    step: stepName,
    command: [command, ...args].join(' '),
    exitCode: typeof result.status === 'number' ? result.status : 1,
    isValid: result.status === 0,
    parsedJson: parseLastJsonObject(combinedOutput),
    outputPreview: tail(combinedOutput),
    error: result.error ? result.error.message : null,
  };
}

function parseLastJsonObject(output) {
  const text = stripAnsi(output).trim();
  if (!text) {
    return null;
  }

  for (let index = text.lastIndexOf('{'); index >= 0; index = text.lastIndexOf('{', index - 1)) {
    const candidate = text.slice(index);
    try {
      return JSON.parse(candidate);
    } catch {
      // Keep scanning backward until we find the final JSON object.
    }
  }

  return null;
}

function stripAnsi(value) {
  return value.replace(/\u001b\[[0-9;]*m/g, '');
}

function tail(value) {
  const stripped = stripAnsi(value).trim();
  if (stripped.length <= MAX_OUTPUT_CHARS) {
    return stripped;
  }

  return stripped.slice(-MAX_OUTPUT_CHARS);
}

function summarizeStep(result) {
  const summary = {
    isValid: result.isValid,
    exitCode: result.exitCode,
  };

  if (result.parsedJson && typeof result.parsedJson === 'object') {
    summary.report = result.parsedJson;
  }

  if (!result.isValid) {
    summary.error = result.error;
    summary.outputPreview = result.outputPreview;
  }

  return summary;
}

function validateParsedJson(stepName, result) {
  if (!result.isValid) {
    return result;
  }

  if (!result.parsedJson) {
    return {
      ...result,
      isValid: false,
      exitCode: 1,
      error: `${stepName} did not return a parseable JSON report`,
    };
  }

  if (result.parsedJson.isValid !== true) {
    return {
      ...result,
      isValid: false,
      exitCode: 1,
      error: `${stepName} returned isValid=false`,
    };
  }

  return result;
}

function runValidation(options) {
  const report = {
    isValid: false,
    steps: {},
    errors: [],
  };

  const buildCommand = npmCommandArgs('build');
  const build = runCommand('build', buildCommand.command, buildCommand.args);
  report.steps.build = summarizeStep(build);
  if (!build.isValid) {
    report.errors.push('build failed');
    return report;
  }

  const dryRunCommand = nodeScriptArgs('import-generated-seed.js', ['--dry-run']);
  const seedDryRun = validateParsedJson(
    'seedDryRun',
    runCommand('seedDryRun', dryRunCommand.command, dryRunCommand.args),
  );
  report.steps.seedDryRun = summarizeStep(seedDryRun);
  if (!seedDryRun.isValid) {
    report.errors.push(seedDryRun.error || 'seed dry-run failed');
    return report;
  }

  if (options.skipImport) {
    report.steps.seedImport = {
      isValid: true,
      skipped: true,
    };
  } else {
    const importCommand = nodeScriptArgs('import-generated-seed.js');
    const seedImport = validateParsedJson(
      'seedImport',
      runCommand('seedImport', importCommand.command, importCommand.args),
    );
    report.steps.seedImport = summarizeStep(seedImport);
    if (!seedImport.isValid) {
      report.errors.push(seedImport.error || 'seed import failed');
      return report;
    }
  }

  const verifyCommand = nodeScriptArgs('verify-generated-seed.js');
  const seedVerify = validateParsedJson(
    'seedVerify',
    runCommand('seedVerify', verifyCommand.command, verifyCommand.args),
  );
  report.steps.seedVerify = summarizeStep(seedVerify);
  if (!seedVerify.isValid) {
    report.errors.push(seedVerify.error || 'seed verification failed');
    return report;
  }

  report.isValid = true;
  return report;
}

function main() {
  const options = parseArgs(process.argv.slice(2));
  const report = runValidation(options);
  console.log(JSON.stringify(report, null, 2));
  process.exit(report.isValid ? 0 : 1);
}

main();
