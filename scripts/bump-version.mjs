#!/usr/bin/env node
// Uso: node scripts/bump-version.mjs X.Y.Z
// Atualiza a versão em todos os lugares: VERSION, package.json (raiz e
// frontend) e frontend/app.json. Depois: commit, `git tag vX.Y.Z` e push da
// tag — o workflow release.yml publica a release no GitHub.
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const next = process.argv[2];

if (!/^\d+\.\d+\.\d+$/.test(next ?? '')) {
  console.error('Uso: node scripts/bump-version.mjs X.Y.Z');
  process.exit(1);
}

// Troca só o primeiro campo "version" (substituição pontual preserva a
// formatação do arquivo; reserializar o JSON geraria diffs de ruído).
function updateVersionField(rel) {
  const path = join(root, rel);
  const raw = readFileSync(path, 'utf8');
  const out = raw.replace(/("version"\s*:\s*")[^"]*(")/, `$1${next}$2`);
  if (out === raw && !raw.includes(`"version": "${next}"`)) {
    console.error(`Campo "version" não encontrado em ${rel}`);
    process.exit(1);
  }
  writeFileSync(path, out);
  console.log(`${rel} -> ${next}`);
}

writeFileSync(join(root, 'VERSION'), `${next}\n`);
console.log(`VERSION -> ${next}`);
updateVersionField('package.json');
updateVersionField('frontend/package.json');
updateVersionField('frontend/app.json');
