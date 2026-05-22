const fs = require('node:fs');
const path = require('node:path');
const { compileStrapi, createStrapi } = require('@strapi/strapi');

const DEFAULT_SEED_PATH = path.resolve(
  __dirname,
  '..',
  '..',
  'ai-agent',
  'generated',
  'strapi',
  'seed',
  'landing-page.seed.json'
);

function isKnownShutdownAbort(error) {
  return error && error.message === 'aborted';
}

process.on('uncaughtException', (error) => {
  if (isKnownShutdownAbort(error)) {
    process.exit(0);
  }

  console.error(JSON.stringify({ isValid: false, error: error.message }, null, 2));
  process.exit(1);
});

process.on('unhandledRejection', (error) => {
  if (isKnownShutdownAbort(error)) {
    process.exit(0);
  }

  console.error(JSON.stringify({ isValid: false, error: error.message }, null, 2));
  process.exit(1);
});

function parseArgs(argv) {
  const options = {
    seedPath: DEFAULT_SEED_PATH,
    dryRun: false,
    status: null,
  };

  for (const arg of argv) {
    if (arg === '--dry-run') {
      options.dryRun = true;
    } else if (arg === '--draft') {
      options.status = 'draft';
    } else if (arg === '--published') {
      options.status = 'published';
    } else {
      options.seedPath = path.resolve(process.cwd(), arg);
    }
  }

  return options;
}

function readSeed(seedPath) {
  if (!fs.existsSync(seedPath)) {
    throw new Error(`Seed file not found: ${seedPath}`);
  }

  const seed = JSON.parse(fs.readFileSync(seedPath, 'utf8'));
  if (!seed.uid || !seed.data || typeof seed.data !== 'object') {
    throw new Error('Seed file must contain uid and data');
  }

  return seed;
}

async function importSeed(seed, status) {
  process.env.STRAPI_TELEMETRY_DISABLED = 'true';

  const appContext = await compileStrapi();
  const app = await createStrapi(appContext).load();
  try {
    const contentType = app.contentType(seed.uid);
    if (!contentType) {
      throw new Error(`Strapi content type not found: ${seed.uid}`);
    }

    const repository = app.documents(seed.uid);
    const existingDraft = await repository.findFirst({ status: 'draft' });
    const existingPublished = await repository.findFirst({ status: 'published' });
    const existing = existingDraft || existingPublished;
    const requestedStatus = status || seed.status || 'published';

    const document = existing?.documentId
      ? await repository.update({
          documentId: existing.documentId,
          data: seed.data,
          status: requestedStatus,
        })
      : await repository.create({
          data: seed.data,
          status: requestedStatus,
        });

    return {
      action: existing?.documentId ? 'updated' : 'created',
      uid: seed.uid,
      documentId: document?.documentId || existing?.documentId || null,
      status: requestedStatus,
      dataKeys: Object.keys(seed.data).sort(),
    };
  } finally {
    try {
      await app.destroy();
    } catch (error) {
      if (error.message !== 'aborted') {
        throw error;
      }
    }
  }
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const seed = readSeed(options.seedPath);
  const summary = {
    seedPath: options.seedPath,
    uid: seed.uid,
    status: options.status || seed.status || 'published',
    dataKeys: Object.keys(seed.data).sort(),
    mediaAssetCount: Array.isArray(seed.mediaAssets) ? seed.mediaAssets.length : 0,
    warnings: seed.warnings || [],
  };

  if (options.dryRun) {
    console.log(JSON.stringify({ isValid: true, dryRun: true, ...summary }, null, 2));
    process.exit(0);
  }

  const importReport = await importSeed(seed, options.status);
  console.log(JSON.stringify({ isValid: true, dryRun: false, ...summary, importReport }, null, 2));
  process.exit(0);
}

main().catch((error) => {
  console.error(JSON.stringify({ isValid: false, error: error.message }, null, 2));
  process.exit(1);
});
