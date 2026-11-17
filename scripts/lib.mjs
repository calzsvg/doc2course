import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';

// Paths. Mirrors scripts/p2v_paths.py; ./p2v exports the resolved values as P2V_* env vars.
const HOME = process.env.HOME || '';
const expand = p => path.resolve(p.replace(/^~(?=\/|$)/, HOME));
const real = p => { try { return fs.realpathSync(p); } catch { return path.resolve(p); } };
const under = (p, base) => { p = real(p); base = real(base); return p === base || p.startsWith(base + path.sep); };
function pluginId(root) {
  const cache = real(path.join(HOME, '.claude', 'plugins', 'cache')), r = real(root);
  if (!r.startsWith(cache + path.sep)) return null;
  const parts = r.slice(cache.length + 1).split(path.sep);
  return parts.length < 2 ? null : `${parts[1]}@${parts[0]}`.replace(/[^A-Za-z0-9_-]/g, '-');
}
export const toolsDir = root => process.env.P2V_TOOLS ? expand(process.env.P2V_TOOLS)
  : pluginId(root) ? path.join(HOME, '.claude', 'plugins', 'data', pluginId(root)) : path.join(root, '.tools');
const AGENT_HOMES = () => [path.join(HOME, '.claude')];
export const workDir = root => process.env.P2V_HOME ? expand(process.env.P2V_HOME)
  : AGENT_HOMES().some(h => under(root, h)) ? path.join(HOME, 'doc2course') : root;
export const jobsDir = root => process.env.P2V_JOBS ? expand(process.env.P2V_JOBS) : path.join(workDir(root), 'jobs');
export const videosDir = root => process.env.P2V_OUT ? expand(process.env.P2V_OUT) : path.join(workDir(root), 'videos');
// Node packages (three, ffmpeg-static, playwright) live in <tools>/node_modules.
export const toolsRequire = root => createRequire(path.join(toolsDir(root), 'package.json'));

// ffmpeg: $FFMPEG, then PATH, then the ffmpeg-static npm package.
export function resolveFfmpeg(root) {
  if (process.env.FFMPEG) return process.env.FFMPEG;
  const r = spawnSync('ffmpeg', ['-version']);
  if (r.status === 0) return 'ffmpeg';
  try {
    const p = toolsRequire(root)('ffmpeg-static');
    if (p && fs.existsSync(p)) return p;
  } catch { /* fallthrough */ }
  throw new Error('ffmpeg not found. Run ./p2v setup, install ffmpeg (brew install ffmpeg), or set FFMPEG=/path/to/ffmpeg');
}

export function run(bin, args) {
  const r = spawnSync(bin, args, { stdio: ['ignore', 'pipe', 'pipe'] });
  if (r.status !== 0) throw new Error(`${path.basename(bin)} failed: ${r.stderr.toString().slice(-800)}`);
  return r.stdout.toString();
}


// Duration of a PCM WAV from its header (fmt byte rate, data chunk size).
export function wavSeconds(file) {
  const b = fs.readFileSync(file); let i = 12, rate = 0;
  while (i + 8 <= b.length) {
    const id = b.toString('ascii', i, i + 4), size = b.readUInt32LE(i + 4);
    if (id === 'fmt ') rate = b.readUInt32LE(i + 16);
    if (id === 'data') return rate ? size / rate : 0;
    i += 8 + size + (size & 1);
  }
  return 0;
}

export function mux(root, job, ffmpeg = resolveFfmpeg(root), expected = 0) {
  const b = path.join(jobsDir(root), job, 'build');
  // ffmpeg's image sequence stops silently at the first gap, so check that every frame arrived.
  const have = new Set(fs.readdirSync(path.join(b, 'frames')).filter(f => /^\d{5}\.jpg$/.test(f)));
  const want = expected || have.size;
  const missing = []; for (let k = 0; k < want && missing.length < 5; k++) if (!have.has(String(k).padStart(5, '0') + '.jpg')) missing.push(k);
  if (missing.length || have.size < want) throw new Error(`frames incomplete: have ${have.size}/${want}, first missing ${missing.join(', ')}`);
  const frames = path.join(b, 'frames', '%05d.jpg');
  const audio = path.join(b, 'narration.wav');
  const output = path.join(b, `${job}.mp4`);
  // The video must cover the whole narration: -shortest below would otherwise cut the audio tail silently.
  if (fs.existsSync(audio)) {
    const sec = wavSeconds(audio), vid = want / 30;
    if (sec > vid + 0.1) throw new Error(`narration (${sec.toFixed(2)} s) is longer than the video (${vid.toFixed(2)} s): timing.json and narration.wav do not match. Re-run tts, then render.`);
  }
  const args = ['-y', '-loglevel', 'error', '-framerate', '30', '-i', frames];
  const hasAudio = fs.existsSync(audio);
  if (hasAudio) args.push('-i', audio);
  // Chapters (scenes with a "chapter" field in script.json): embedded in the MP4 and written as build/chapters.txt.
  const ch = chapters(root, job, want / 30);
  const chTxt = path.join(b, 'chapters.txt'), chMeta = path.join(b, 'chapters.ffmeta');
  fs.rmSync(chTxt, { force: true }); fs.rmSync(chMeta, { force: true });
  if (ch.length) {
    fs.writeFileSync(chTxt, ch.map(c => `${clock(c.start)} ${c.title}`).join('\n') + '\n');
    const esc = s => s.replace(/[=;#\\\n]/g, m => '\\' + m);
    fs.writeFileSync(chMeta, ';FFMETADATA1\n' + ch.map(c =>
      `[CHAPTER]\nTIMEBASE=1/1000\nSTART=${Math.round(c.start * 1000)}\nEND=${Math.round(c.end * 1000)}\ntitle=${esc(c.title)}\n`).join(''));
    args.push('-i', chMeta, '-map', '0:v');
    if (hasAudio) args.push('-map', '1:a');
    const mi = hasAudio ? 2 : 1;
    args.push('-map_metadata', String(mi), '-map_chapters', String(mi));
  }
  args.push('-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p');
  if (hasAudio) args.push('-c:a', 'aac', '-ar', '48000', '-b:a', '160k', '-shortest');
  args.push('-movflags', '+faststart', output);
  run(ffmpeg, args);
  // Contact sheet: frames evenly spaced over the whole video (4x4 up to 8 minutes, 6x6 for longer videos).
  const grid = want > 30 * 60 * 8 ? 6 : 4;
  const step = Math.max(1, Math.floor(want / (grid * grid)));
  const contact = path.join(b, 'contact.jpg');
  run(ffmpeg, ['-y', '-loglevel', 'error', '-i', output, '-vf', `select='not(mod(n+${Math.floor(step / 2)}\\,${step}))',scale=480:-1,tile=${grid}x${grid}`, '-fps_mode', 'vfr', '-frames:v', '1', contact]);
  const shortcut = publish(root, job, output);
  return { output, contact, shortcut };
}

// Chapters from script.json: a scene with "chapter": "Title" starts a chapter (the first one is moved to 0:00,
// as video sites expect). Returns [{ title, start, end }] in seconds, or [] when the script has no chapters.
export function chapters(root, job, total = 0) {
  const J = path.join(jobsDir(root), job);
  let timing, script;
  try { timing = JSON.parse(fs.readFileSync(path.join(J, 'build', 'timing.json'), 'utf8')); script = JSON.parse(fs.readFileSync(path.join(J, 'script.json'), 'utf8')); }
  catch { return []; }
  const byId = Object.fromEntries((script.scenes || []).map(s => [s.id, s]));
  const out = [];
  for (const sc of timing) { const t = byId[sc.id]?.chapter; if (t) out.push({ title: String(t), start: sc.start }); }
  if (!out.length) return [];
  out[0].start = 0;
  const end = total || timing.reduce((a, s) => Math.max(a, s.start + s.dur), 0);
  out.forEach((c, i) => { c.end = i + 1 < out.length ? out[i + 1].start : end; });
  return out;
}
export const clock = sec => {
  const s = Math.floor(sec), h = Math.floor(s / 3600), m = Math.floor(s / 60) % 60, r = String(s % 60).padStart(2, '0');
  return h ? `${h}:${String(m).padStart(2, '0')}:${r}` : `${m}:${r}`;
};

// Where a finished video goes:
//   local PDF source (paper/meta.json source "local")  next to the PDF, "<pdf name> - <script title>.mp4"
//                                                       (+ "<same>.chapters.txt" when the script has chapters)
//   anything else (arXiv, PDF link)                     videosDir(): $P2V_OUT or <work>/videos/, "<id>_<Short-Title>[_ko].mp4"
// $P2V_OUT, when set, wins for every source; P2V_NEXT_TO_SOURCE=0 turns the "next to the PDF" rule off.
// Hard link when possible (no extra disk), copy otherwise. Re-renders overwrite the same name.
const readJob = (root, job, f) => { try { return JSON.parse(fs.readFileSync(path.join(jobsDir(root), job, f), 'utf8')); } catch { return {}; } };
export function sourceDir(root, job) {
  // ./p2v always exports P2V_OUT (the default videos folder) and sets P2V_OUT_EXPLICIT=1 only when the user set it;
  // a script run directly (node scripts/...) treats any P2V_OUT as the user's choice.
  const explicitOut = process.env.P2V_OUT_EXPLICIT === undefined ? !!process.env.P2V_OUT : process.env.P2V_OUT_EXPLICIT === '1';
  if (explicitOut || process.env.P2V_NEXT_TO_SOURCE === '0') return null;
  const meta = readJob(root, job, 'paper/meta.json');
  return meta.source === 'local' && meta.file && fs.existsSync(meta.file) ? path.dirname(meta.file) : null;
}
const safeName = s => s.normalize('NFC').replace(/[\/:*?"<>|\u0000-\u001f]+/g, ' - ').replace(/\s+/g, ' ').replace(/( - )+/g, ' - ').trim().slice(0, 140).trim();
export function videoName(root, job, nextToSource = !!sourceDir(root, job)) {
  const meta = readJob(root, job, 'paper/meta.json'), script = readJob(root, job, 'script.json');
  if (nextToSource) {
    const stem = path.basename(meta.file || meta.file_name || job).replace(/\.pdf$/i, '');
    const title = safeName(script.title || '');
    return `${safeName(stem)}${title ? ' - ' + title : ' - ' + job}.mp4`;
  }
  const title = (meta.title || script.title || '').split(':')[0].trim();
  const slug = title.normalize('NFKD').replace(/[^\w\s-]/g, '').trim().split(/\s+/).slice(0, 6).join('-').slice(0, 60);
  const lang = (script.lang || 'en').toLowerCase();
  const suffix = lang !== 'en' && !job.toLowerCase().endsWith('_' + lang) ? '_' + lang : '';   // "_smoke_ko", not "_smoke_ko_ko"
  return `${job}${slug ? '_' + slug : ''}${suffix}.mp4`;
}
function place(src, dest) {
  fs.rmSync(dest, { force: true });
  try { fs.linkSync(src, dest); } catch { fs.copyFileSync(src, dest); }
}
export function publish(root, job, output) {
  const chapters = path.join(path.dirname(output), 'chapters.txt');
  const put = (dir, name) => {
    fs.mkdirSync(dir, { recursive: true });
    const dest = path.join(dir, name);
    place(output, dest);
    const ch = dest.replace(/\.mp4$/, '.chapters.txt');
    if (fs.existsSync(chapters)) place(chapters, ch); else fs.rmSync(ch, { force: true });
    return dest;
  };
  const src = sourceDir(root, job);
  if (src) {
    try { return put(src, videoName(root, job, true)); }
    catch (e) { console.error(`could not write next to the source PDF (${src}): ${e.code || e.message}; using the videos folder`); }
  }
  return put(videosDir(root), videoName(root, job, false));
}
