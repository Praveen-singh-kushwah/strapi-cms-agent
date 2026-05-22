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
    status: null,
  };

  for (const arg of argv) {
    if (arg === '--draft') {
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

function buildPopulate(data, mediaPlan) {
  const populate = Object.fromEntries(
    Object.entries(data)
      .filter(([, value]) => value && typeof value === 'object')
      .map(([key, value]) => [key, buildPopulateForValue(value)])
  );

  for (const item of Array.isArray(mediaPlan) ? mediaPlan : []) {
    if (item && item.status === 'ready' && item.fieldPath) {
      addFieldPathToPopulate(populate, item.fieldPath);
    }
  }

  return populate;
}

function buildPopulateForValue(value) {
  if (Array.isArray(value)) {
    const sample = value.find((item) => item && typeof item === 'object');
    return sample ? buildPopulateForValue(sample) : true;
  }

  if (!isPlainObject(value)) {
    return true;
  }

  const nestedPopulate = Object.fromEntries(
    Object.entries(value)
      .filter(([, childValue]) => childValue && typeof childValue === 'object')
      .map(([key, childValue]) => [key, buildPopulateForValue(childValue)])
  );

  if (Object.keys(nestedPopulate).length === 0) {
    return true;
  }

  return { populate: nestedPopulate };
}

function ensurePopulateBranch(container, key) {
  const current = container[key];
  if (!current || current === true || !isPlainObject(current)) {
    container[key] = { populate: {} };
  } else if (!current.populate || !isPlainObject(current.populate)) {
    container[key] = { ...current, populate: {} };
  }

  return container[key].populate;
}

function addFieldPathToPopulate(populate, fieldPath) {
  const tokens = parseFieldPath(fieldPath).filter((token) => typeof token === 'string');
  if (tokens.length < 2) {
    return;
  }

  let cursor = ensurePopulateBranch(populate, tokens[0]);
  for (let index = 1; index < tokens.length; index += 1) {
    const token = tokens[index];
    if (index === tokens.length - 1) {
      cursor[token] = true;
    } else {
      cursor = ensurePopulateBranch(cursor, token);
    }
  }
}

async function findSeededDocument(repository, seed, status) {
  const populate = buildPopulate(seed.data, seed.mediaPlan);
  const preferredStatuses = status ? [status] : [seed.status || 'published', 'draft', 'published'];
  const uniqueStatuses = [...new Set(preferredStatuses)];

  for (const candidateStatus of uniqueStatuses) {
    const document = await repository.findFirst({
      status: candidateStatus,
      populate,
    });

    if (document) {
      return {
        document,
        status: candidateStatus,
      };
    }
  }

  return {
    document: null,
    status: null,
  };
}

function isPlainObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function parseFieldPath(fieldPath) {
  const tokens = [];
  const pattern = /([^[.\]]+)|\[(\d+)\]/g;
  let match;

  while ((match = pattern.exec(fieldPath)) !== null) {
    tokens.push(match[1] ?? Number(match[2]));
  }

  return tokens;
}

function getValueAtPath(target, fieldPath) {
  return parseFieldPath(fieldPath).reduce((cursor, token) => {
    if (cursor == null) {
      return undefined;
    }

    return cursor[token];
  }, target);
}

function hasUsefulValue(value) {
  if (value == null) {
    return false;
  }

  if (Array.isArray(value)) {
    return value.length > 0;
  }

  if (typeof value === 'object') {
    return Object.keys(value).length > 0;
  }

  if (typeof value === 'string') {
    return value.trim().length > 0;
  }

  return true;
}

function mediaFieldPaths(seed) {
  if (!Array.isArray(seed.mediaPlan)) {
    return new Set();
  }

  return new Set(
    seed.mediaPlan
      .filter((item) => item && item.status === 'ready' && item.fieldPath)
      .map((item) => item.fieldPath)
  );
}

function valuesMatch(expected, actual) {
  if (expected === null || expected === undefined) {
    return true;
  }

  return expected === actual;
}

function verifyValue(expected, actual, fieldPath, mediaPaths, errors, warnings) {
  if (mediaPaths.has(fieldPath)) {
    if (!hasUsefulValue(actual)) {
      errors.push(`${fieldPath}: expected uploaded media to be linked`);
    }
    return;
  }

  if (expected === null || expected === undefined) {
    return;
  }

  if (Array.isArray(expected)) {
    if (!Array.isArray(actual)) {
      errors.push(`${fieldPath}: expected an array`);
      return;
    }

    if (actual.length < expected.length) {
      errors.push(`${fieldPath}: expected at least ${expected.length} items, found ${actual.length}`);
      return;
    }

    expected.forEach((item, index) => {
      verifyValue(item, actual[index], `${fieldPath}[${index}]`, mediaPaths, errors, warnings);
    });
    return;
  }

  if (isPlainObject(expected)) {
    if (!isPlainObject(actual)) {
      errors.push(`${fieldPath}: expected an object`);
      return;
    }

    for (const [key, childExpected] of Object.entries(expected)) {
      if (!(key in actual)) {
        warnings.push(`${fieldPath}.${key}: expected seed field was not returned by Strapi`);
        continue;
      }

      verifyValue(childExpected, actual[key], `${fieldPath}.${key}`, mediaPaths, errors, warnings);
    }
    return;
  }

  if (!valuesMatch(expected, actual)) {
    errors.push(`${fieldPath}: expected ${JSON.stringify(expected)}, found ${JSON.stringify(actual)}`);
  }
}

function verifyDocument(seed, document) {
  const errors = [];
  const warnings = [];
  const mediaPaths = mediaFieldPaths(seed);

  for (const key of Object.keys(seed.data)) {
    if (!(key in document)) {
      errors.push(`${key}: missing top-level field`);
      continue;
    }

    verifyValue(seed.data[key], document[key], key, mediaPaths, errors, warnings);
  }

  for (const fieldPath of mediaPaths) {
    const value = getValueAtPath(document, fieldPath);
    if (!hasUsefulValue(value)) {
      errors.push(`${fieldPath}: media field is empty after import`);
    }
  }

  return {
    isValid: errors.length === 0,
    errors,
    warnings,
    summary: {
      documentId: document.documentId || null,
      returnedKeys: Object.keys(document).sort(),
      expectedDataKeys: Object.keys(seed.data).sort(),
      verifiedMediaFields: [...mediaPaths].sort(),
    },
  };
}

async function verifySeed(seed, status) {
  process.env.STRAPI_TELEMETRY_DISABLED = 'true';

  const appContext = await compileStrapi();
  const app = await createStrapi(appContext).load();
  try {
    const contentType = app.contentType(seed.uid);
    if (!contentType) {
      throw new Error(`Strapi content type not found: ${seed.uid}`);
    }

    const repository = app.documents(seed.uid);
    const { document, status: foundStatus } = await findSeededDocument(repository, seed, status);
    if (!document) {
      return {
        isValid: false,
        errors: [`No seeded document found for ${seed.uid}`],
        warnings: [],
        summary: {
          uid: seed.uid,
          requestedStatus: status || seed.status || 'published',
        },
      };
    }

    const verification = verifyDocument(seed, document);
    return {
      ...verification,
      summary: {
        uid: seed.uid,
        status: foundStatus,
        ...verification.summary,
      },
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
  const report = await verifySeed(seed, options.status);

  console.log(JSON.stringify({
    ...report,
    seedPath: options.seedPath,
  }, null, 2));
  process.exit(report.isValid ? 0 : 1);
}

main().catch((error) => {
  console.error(JSON.stringify({ isValid: false, error: error.message }, null, 2));
  process.exit(1);
});
