const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const root = path.resolve(__dirname, '..');
const readme = fs.readFileSync(path.join(root, 'README.md'), 'utf8');
const english = fs.readFileSync(path.join(root, 'README_en.md'), 'utf8');

for (const [name, content] of [['Chinese', readme], ['English', english]]) {
test(`${name} README local links and screenshots exist`, () => {
  const links = [...content.matchAll(/\]\(([^)]+)\)|(?:src|href)="([^"]+)"/g)]
    .map(match => match[1] || match[2])
    .filter(link => !/^(https?:|#)/.test(link));
  assert.ok(links.length > 25);
  for (const link of links) {
    assert.ok(fs.existsSync(path.resolve(root, link.split('#')[0])), link);
  }
  assert.equal((content.match(/<img /g) || []).length, 8);
  assert.match(content, /chengdu-desktop-overview\.png[^>]*width="1200"/);
  assert.match(content, /\[English\]\(README_en.md\)/);
  assert.match(content, /\[中文\]\(README.md\)/);
  assert.doesNotMatch(content, /docs\/SECURITY\.md/);
});
}

test('README architecture fences and repository links stay consistent', () => {
  assert.equal((readme.match(/^```/gm) || []).length % 2, 0);
  assert.equal((readme.match(/^```mermaid/gm) || []).length, 2);
  for (const match of readme.matchAll(/https:\/\/github\.com\/([^/\s)]+\/[^/\s)?#]+)/g)) {
    assert.equal(match[1].replace(/\.git$/, ''), 'Xcaesar1/JourneyGo');
  }
  assert.match(readme, /api\.star-history\.com\/svg\?repos=Xcaesar1\/JourneyGo/);
});

test('showcase presents attractions and technology badges without CI or star counters', () => {
  assert.match(readme, /chengdu-daily-attractions\.png/);
  assert.doesNotMatch(readme, /返程机场接驳<\/th>|高铁补充验证与可复现记录/);
  assert.doesNotMatch(readme, /badge\.svg|img\.shields\.io\/github\/stars/);
  for (const tech of ['LangGraph', 'Celery', 'PostgreSQL', 'Redis', 'TypeScript', 'Docker']) {
    assert.ok(readme.includes(`[![${tech}]`), tech);
  }
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
