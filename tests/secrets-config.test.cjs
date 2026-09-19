const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const root = path.resolve(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');

test('real environment files are ignored while example templates remain trackable', () => {
  const privatePaths = ['.env', '.env.staging', '.env.production', 'backend/.env',
    'backend/.env.production', 'frontend/.env.production', 'frontend/.env.local',
    'backend/runtime_settings.json'];
  const examples = ['.env.demo.example', '.env.staging.example', 'backend/.env.example',
    'frontend/.env.example'];
  const ignored = execFileSync('git', ['check-ignore', '--no-index', '--stdin'], {
    cwd: root, input: [...privatePaths, ...examples].join('\n') + '\n', encoding: 'utf8',
  }).trim().split(/\r?\n/);
  assert.deepEqual(ignored, privatePaths);
});

test('environment examples contain only empty or explicitly fake credentials', () => {
  for (const file of ['.env.demo.example', '.env.staging.example', 'backend/.env.example',
    'frontend/.env.example']) {
    for (const line of read(file).split(/\r?\n/)) {
      const match = line.match(/^([A-Z_]*(?:KEY|PASSWORD|ACCESS_CODE|JS_CODE))=(.*)$/);
      if (!match || !match[2]) continue;
      assert.match(match[2], /^(replace-with-|your[-_]|journeygo-demo-local-only$)/,
        `${file}: ${match[1]} must be blank or a placeholder`);
    }
  }
  assert.doesNotMatch(read('frontend/.env.example'), /^VITE_AMAP_WEB_KEY=/m);
});

test('Docker context excludes environment files, runtime secrets and local artifacts', () => {
  const patterns = read('.dockerignore').split(/\r?\n/);
  for (const pattern of ['.env*', '**/.env*', '**/runtime_settings.json', 'artifacts']) {
    assert.ok(patterns.includes(pattern), pattern);
  }
});
