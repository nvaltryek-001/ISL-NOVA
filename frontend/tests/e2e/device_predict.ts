// Helper for model.e2e.mjs: runs the browser's on-device pipeline (TS features + TS model)
// under Node on landmark JSON files and prints the predictions.
import fs from 'node:fs';
import { extractFeaturesFor } from '../../src/lib/features.ts';
import { WebModel } from '../../src/lib/webModel.ts';

const [header, weights, ...inputs] = process.argv.slice(2);
const w = fs.readFileSync(weights);
const m = WebModel.fromBuffers(JSON.parse(fs.readFileSync(header, 'utf8')), w.buffer.slice(w.byteOffset, w.byteOffset + w.byteLength));
const out = inputs.map((f) => {
  const { frames, aspect } = JSON.parse(fs.readFileSync(f, 'utf8'));
  const fr = extractFeaturesFor(m.header.contract, frames, aspect);
  if (fr.status !== 'ok') return { state: 'insufficient_input', top: [] };
  return m.decide(m.predictProba(fr.features), 5);
});
console.log(JSON.stringify(out));
