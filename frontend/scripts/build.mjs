// Production build: esbuild bundles TypeScript/React, Tailwind CSS v4 is
// compiled through its programmatic API, and index.html is written with
// content-hashed asset names.   node scripts/build.mjs [--watch]
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import * as esbuild from 'esbuild';
import { compile } from 'tailwindcss';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const dist = path.join(root, 'dist');
const watch = process.argv.includes('--watch');
const twBase = path.dirname(fileURLToPath(import.meta.resolve('tailwindcss/package.json')));

function walk(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((d) =>
    d.isDirectory() ? walk(path.join(dir, d.name)) : [path.join(dir, d.name)]);
}

// Tailwind's Oxide scanner is replaced by a conservative tokenizer: every
// token in the sources is offered as a candidate and Tailwind ignores the
// ones that are not utilities.
function candidates() {
  const set = new Set();
  for (const f of walk(path.join(root, 'src'))) {
    if (!/\.(tsx?|html)$/.test(f)) continue;
    // split only on characters that can never occur inside a utility, so
    // arbitrary values such as grid-cols-[minmax(0,1fr)_2fr] survive intact
    for (const t of fs.readFileSync(f, 'utf8').split(/[\s"'`{};]+/)) {
      if (!t) continue;
      set.add(t);
      const trimmed = t.replace(/^[(<>,]+|[)>,.:]+$/g, '');
      if (trimmed && trimmed !== t) set.add(trimmed);
    }
  }
  return [...set];
}

async function buildCss() {
  const entry = path.join(root, 'src', 'styles.css');
  const loadStylesheet = async (id, base) => {
    let p;
    if (id === 'tailwindcss') p = path.join(twBase, 'index.css');
    else if (id.startsWith('tailwindcss/')) p = path.join(twBase, id.slice(12));
    else p = path.resolve(base, id);
    return { path: p, base: path.dirname(p), content: fs.readFileSync(p, 'utf8') };
  };
  const c = await compile(fs.readFileSync(entry, 'utf8'), { base: path.dirname(entry), loadStylesheet });
  const css = c.build(candidates());
  const out = await esbuild.transform(css, { loader: 'css', minify: !watch });
  return out.code;
}

const hash = (s) => createHash('sha256').update(s).digest('hex').slice(0, 10);

async function buildAll() {
  const t0 = Date.now();
  const res = await esbuild.build({
    entryPoints: [path.join(root, 'src', 'main.tsx')],
    bundle: true, format: 'esm', target: 'es2022', jsx: 'automatic', write: false,
    minify: !watch, sourcemap: watch ? 'inline' : false, legalComments: 'none',
    define: { 'process.env.NODE_ENV': JSON.stringify(watch ? 'development' : 'production') },
    logLevel: 'warning',
  });
  const js = res.outputFiles[0].text;
  const css = await buildCss();
  fs.rmSync(dist, { recursive: true, force: true });
  fs.mkdirSync(path.join(dist, 'assets'), { recursive: true });
  const jsName = `app-${hash(js)}.js`;
  const cssName = `app-${hash(css)}.css`;
  fs.writeFileSync(path.join(dist, 'assets', jsName), js);
  fs.writeFileSync(path.join(dist, 'assets', cssName), css);
  for (const f of fs.readdirSync(path.join(root, 'public'))) fs.copyFileSync(path.join(root, 'public', f), path.join(dist, f));
  const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8')
    .replace('%CSS%', `/assets/${cssName}`).replace('%JS%', `/assets/${jsName}`);
  fs.writeFileSync(path.join(dist, 'index.html'), html);
  console.log(`built ${jsName} (${(js.length / 1024).toFixed(0)} kB) ${cssName} (${(css.length / 1024).toFixed(0)} kB) in ${Date.now() - t0} ms`);
}

await buildAll();
if (watch) {
  console.log('watching src/ ...');
  let timer;
  fs.watch(path.join(root, 'src'), { recursive: true }, () => {
    clearTimeout(timer);
    timer = setTimeout(() => buildAll().catch((e) => console.error(e.message)), 120);
  });
}
