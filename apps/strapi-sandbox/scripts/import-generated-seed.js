const fs = require('node:fs');
const path = require('node:path');
const mime = require('mime-types');
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

function countMediaPlanStatus(mediaPlan, status) {
  if (!Array.isArray(mediaPlan)) {
    return 0;
  }

  return mediaPlan.filter((item) => item && item.status === status).length;
}

function countUploadableMedia(mediaPlan) {
  if (!Array.isArray(mediaPlan)) {
    return 0;
  }

  return mediaPlan.filter((item) => item && item.resolvedPath && fs.existsSync(item.resolvedPath)).length;
}

function cloneJson(value) {
  return JSON.parse(JSON.stringify(value));
}

function buildUploadFileInput(mediaItem) {
  const filepath = mediaItem.resolvedPath;
  const originalFilename = path.basename(filepath);
  const stat = fs.statSync(filepath);

  return {
    filepath,
    originalFilename,
    mimetype: mime.lookup(filepath) || 'application/octet-stream',
    size: stat.size,
  };
}

async function findExistingUploadedFile(app, uploadFile) {
  const existingFiles = await app.db.query('plugin::upload.file').findMany({
    where: {
      name: uploadFile.originalFilename,
      mime: uploadFile.mimetype,
    },
    orderBy: { id: 'desc' },
    limit: 1,
  });
  return existingFiles[0] || null;
}

async function uploadOrReuseMediaItem(app, mediaItem) {
  const uploadFile = buildUploadFileInput(mediaItem);
  const existingFile = await findExistingUploadedFile(app, uploadFile);
  if (existingFile) {
    return {
      action: 'reused',
      fieldPath: mediaItem.fieldPath,
      fileId: existingFile.id,
      fileName: existingFile.name,
      url: existingFile.url,
    };
  }

  const uploadedFiles = await app.plugin('upload').service('upload').upload({
    data: {
      fileInfo: {
        name: uploadFile.originalFilename,
        alternativeText: mediaItem.alt || '',
      },
    },
    files: uploadFile,
  });
  const uploadedFile = Array.isArray(uploadedFiles) ? uploadedFiles[0] : uploadedFiles;

  return {
    action: 'uploaded',
    fieldPath: mediaItem.fieldPath,
    fileId: uploadedFile.id,
    fileName: uploadedFile.name,
    url: uploadedFile.url,
  };
}

async function uploadReadyMedia(app, mediaPlan) {
  const report = {
    uploadedCount: 0,
    reusedCount: 0,
    missingCount: 0,
    files: [],
    missing: [],
  };

  if (!Array.isArray(mediaPlan)) {
    return report;
  }

  const uploadCache = new Map();
  for (const item of mediaPlan) {
    if (!item || !item.fieldPath || !item.resolvedPath || !fs.existsSync(item.resolvedPath)) {
      report.missingCount += 1;
      report.missing.push({
        fieldPath: item?.fieldPath || '',
        src: item?.src || '',
        resolvedPath: item?.resolvedPath || '',
      });
      continue;
    }

    const cacheKey = path.resolve(item.resolvedPath);
    let fileReport = uploadCache.get(cacheKey);
    if (!fileReport) {
      fileReport = await uploadOrReuseMediaItem(app, item);
      uploadCache.set(cacheKey, fileReport);
      if (fileReport.action === 'uploaded') {
        report.uploadedCount += 1;
      } else if (fileReport.action === 'reused') {
        report.reusedCount += 1;
      }
    } else {
      fileReport = {
        ...fileReport,
        action: `${fileReport.action}-cached`,
        fieldPath: item.fieldPath,
      };
    }

    report.files.push(fileReport);
  }

  return report;
}

function parseDataPath(fieldPath) {
  const tokens = [];
  const pattern = /([^[.\]]+)|\[(\d+)\]/g;
  let match;

  while ((match = pattern.exec(fieldPath)) !== null) {
    tokens.push(match[1] ?? Number(match[2]));
  }

  return tokens;
}

function setValueAtPath(target, fieldPath, value) {
  const tokens = parseDataPath(fieldPath);
  if (!tokens.length) {
    return false;
  }

  let cursor = target;
  for (let index = 0; index < tokens.length - 1; index += 1) {
    const token = tokens[index];
    if (cursor == null || !(token in cursor)) {
      return false;
    }
    cursor = cursor[token];
  }

  cursor[tokens[tokens.length - 1]] = value;
  return true;
}

function applyUploadedMedia(data, mediaReport) {
  const linked = [];
  const skipped = [];

  for (const file of mediaReport.files) {
    if (setValueAtPath(data, file.fieldPath, file.fileId)) {
      linked.push({
        fieldPath: file.fieldPath,
        fileId: file.fileId,
        action: file.action,
      });
    } else {
      skipped.push({
        fieldPath: file.fieldPath,
        reason: 'field path not found in seed data',
      });
    }
  }

  return { linked, skipped };
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

    const data = cloneJson(seed.data);
    const mediaReport = await uploadReadyMedia(app, seed.mediaPlan);
    const mediaLinkReport = applyUploadedMedia(data, mediaReport);
    const repository = app.documents(seed.uid);
    const existingDraft = await repository.findFirst({ status: 'draft' });
    const existingPublished = await repository.findFirst({ status: 'published' });
    const existing = existingDraft || existingPublished;
    const requestedStatus = status || seed.status || 'published';

    const document = existing?.documentId
      ? await repository.update({
          documentId: existing.documentId,
          data,
          status: requestedStatus,
        })
      : await repository.create({
          data,
          status: requestedStatus,
        });

    return {
      action: existing?.documentId ? 'updated' : 'created',
      uid: seed.uid,
      documentId: document?.documentId || existing?.documentId || null,
      status: requestedStatus,
      dataKeys: Object.keys(data).sort(),
      mediaReport,
      mediaLinkReport,
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
    mediaPlanReadyCount: countMediaPlanStatus(seed.mediaPlan, 'ready'),
    mediaPlanMissingCount: countMediaPlanStatus(seed.mediaPlan, 'missing'),
    mediaPlanUploadableCount: countUploadableMedia(seed.mediaPlan),
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
