const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const root = path.resolve(__dirname, '..');
const readme = fs.readFileSync(path.join(root, 'README.md'), 'utf8');

test('README local links and screenshots exist', () => {
  const links = [...readme.matchAll(/\]\(([^)]+)\)|(?:src|href)="([^"]+)"/g)]
    .map(match => match[1] || match[2])
    .filter(link => !/^(https?:|#)/.test(link));
  assert.ok(links.length > 25);
  for (const link of links) {
    assert.ok(fs.existsSync(path.resolve(root, link.split('#')[0])), link);
  }
  assert.equal((readme.match(/<img /g) || []).length, 7);
});

test('README architecture fences and repository links stay consistent', () => {
  assert.equal((readme.match(/^```/gm) || []).length % 2, 0);
  assert.equal((readme.match(/^```mermaid/gm) || []).length, 2);
  for (const match of readme.matchAll(/https:\/\/github\.com\/([^/\s)]+\/[^/\s)?#]+)/g)) {
    assert.equal(match[1].replace(/\.git$/, ''), 'Xcaesar1/JourneyGo');
  }
  assert.match(readme, /api\.star-history\.com\/svg\?repos=Xcaesar1\/JourneyGo/);
});

test('renamed deployment and evaluation entry points exist', () => {
  for (const file of ['deploy/nginx/journeygo.conf.example', 'docs/CHANGELOG.md',
    'docs/BRANDING_MIGRATION.md', 'backend/evaluation/datasets/journeygo_v1.json']) {
    assert.ok(fs.existsSync(path.join(root, file)), file);
  }
  const dataset = JSON.parse(fs.readFileSync(path.join(root,
    'backend/evaluation/datasets/journeygo_v1.json'), 'utf8'));
  assert.equal(dataset.dataset_version, 'journeygo-travel-v1.0.0');
});
