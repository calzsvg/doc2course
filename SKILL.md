---
name: doc2video
description: Turn a document (arXiv paper, lecture slides, handout, report: any PDF) into a narrated, fact-checked explainer video (1080p MP4) with animated 2D/3D scenes, subtitles, chapters and a verification report. Run with /doc2video (Claude Code) or $doc2video (Codex) followed by <arxiv link | path to PDF | PDF link> [overrides].
argument-hint: <arxiv link | file.pdf | pdf link> [overrides]
disable-model-invocation: true
license: MIT
compatibility: Claude Code or Codex with a local shell. Needs Node 18+, Python 3.10-3.13, ~1 GB disk (voice model + headless Chromium). Tools install on first run.
allowed-tools: Bash(${CLAUDE_SKILL_DIR}/p2v *)
---

# doc2video

Document in, explainer video out. The user picks the document; everything after that is this workflow, with
**strict cross-checking instead of script approval**. The skill never publishes anything.

Input: **$ARGUMENTS**
(If that line still shows a literal `$ARGUMENTS`, your agent did not substitute it: the input is what the user wrote
after the skill name.)

## Running commands (Claude Code and Codex)
Every step runs through one command: `${CLAUDE_SKILL_DIR}/p2v <subcommand>` (works from any directory).
- **Claude Code** replaces `${CLAUDE_SKILL_DIR}` with the skill folder. Type that full path exactly as written here,
  not a shell variable or `cd` + `./p2v`: the pre-approved permission matches this exact command.
- **Codex and other agents**: if `${CLAUDE_SKILL_DIR}` was not replaced, it means the folder that contains this
  SKILL.md. Use its absolute path everywhere below (e.g. `~/.codex/skills/doc2video/p2v doctor`).
  Codex's default sandbox has no network: `p2v setup` and `p2v fetch` of a link need it, so request approval to run
  them outside the sandbox (or the user runs them once). Everything after fetch works offline.

1. Run `p2v doctor`. It prints the folders (skill, tools, jobs, videos). If it ends with `-> run: ... setup`,
   tell the user "first run: installing tools (~1 GB, a few minutes)" and run `p2v setup` once with the longest
   timeout your shell tool allows (Claude Code: 600000 ms). If it is cut off, run it again: finished parts are skipped.
2. Write job files in the **jobs** folder that doctor printed (`<jobs>/<id>/`), never in the skill folder.
   Installed copies keep jobs in `~/doc2video/` (override with `P2V_HOME`); a development clone keeps them in the repo.
   Finished videos of local PDFs are saved next to the PDF; others go to the videos folder. Tools and caches
   (Chromium, voice models) live in the tools folder.

## Input
One source is required:
- arXiv link or id (`https://arxiv.org/abs/2610.35607`, `2610.35607`)
- a local PDF path: lecture slides, handouts, lecture notes, papers, reports (`~/Downloads/week8.pdf`). Slides from
  PowerPoint/Keynote/Google Slides must be exported to PDF first
- a PDF link that is not arXiv
- the id of a job that was already fetched (has `paper/meta.json`): skip the fetch

Anything after it is an override (e.g. `short`, `20 min`, `deep`, `Korean`, `voice am_michael`, `my own slides`).
Do not ask for more instructions. Run the whole pipeline below with these defaults:

| Default | Value | User can override with |
|---|---|---|
| Length | by document type and size, see **Length modes**. Papers: `standard`; slides/handouts: `lecture` | `short`, `standard`, `deep`, `lecture`, or a time ("12 min") |
| Language / voice | the document's language for slides/handouts (Korean deck → Korean video), else **English**; Kokoro `af_heart` (en) / Supertonic `F1` (others) | `ko` / `Korean` / `한국어`, `English`; another voice id (Kokoro `am_michael`..., Supertonic `F1`-`F5`, `M1`-`M5`) |
| Figure reuse | `meta.json.figure_reuse` decides. Local files default to `unknown` (draw everything yourself) | user says the material is theirs ("my slides", "내 강의자료") → re-run `p2v fetch <file> --figures own` |
| Verification | step 9 always runs in a **fresh context** (see step 9), all layers; equations and derivations are checked by the verifier against the source with the evidence written in VERIFY.md | n/a (never skipped) |
| Fix loop | fix and re-verify up to 3 rounds, then stop with BLOCKED and the open items | n/a |
| Templates | if the skill folder is a git clone you can edit, move any new scene that would work for other documents into `engine/templates.js`; otherwise keep it in the job's scene files and list it as a template candidate in the report | n/a |
| Publishing | never upload or post anywhere; the MP4 is the end product | n/a |
| Git | do not commit; leave changes for review | "commit it" |

Only stop to ask the user when blocked (license forbids the planned visuals, the PDF has no text layer and its pages
cannot be transcribed, verification BLOCKED after 3 rounds, or a toolchain step fails twice).

## Length modes
Longer is not padding: every extra minute must teach something (a step of a derivation, a worked example, a "why",
a common mistake, a check question). Never repeat a point in other words to fill time.

| Mode | Target | Scenes | Chapters | Use |
|---|---|---|---|---|
| `short` | 4-6 min | 10-14 | none | the original paper2video teaser |
| `standard` (papers) | 10-15 min | 25-40 | 4-6 | full walk-through: background the reader needs, every contribution, the main results with their conditions, ablations, limits |
| `lecture` (slides, handouts) | about 1-1.5 min per content slide, 12-40 min total | one scene per 1-2 content slides, plus chapter cards, examples and checks | the deck's own sections (4-8) | replaces attending the lecture: explain each slide, add the reasoning the lecturer would say aloud, worked examples, one check question per chapter, recap at the end |
| `deep` | 20-40 min | 40-80 | 6-10 | everything in `standard`/`lecture`, plus derivations step by step and extra worked examples |

Decks over ~60 content slides: say so in the report and split into parts (`--job <id>-part1`, ...) rather than one
60+ minute video, unless the user asked for one video.

## Pipeline

| # | Step | Command / output |
|---|---|---|
| 1 | Fetch | `p2v fetch <source>` → `<jobs>/<id>/paper/{meta.json, paper.pdf, paper.txt, pages/p-NNN.jpg}` and the job skeleton. It prints the job id, `doc_type` (paper / slides / document) and the pages without a text layer |
| 2 | Read + outline | Read `paper.txt` fully **and look at the page images** (`paper/pages/`) for slides and for any page with diagrams, code, tables or equations. If fetch listed pages with no text layer, transcribe them into `paper/transcribed.txt` (`=== page N ===` markers, text exactly as shown, no additions). Fill `BRIEF.md`: license block first, length mode and target minutes, chapters, outline, shot list |
| 3 | Script | `script.json`: scenes → sentences `[subtitle, tts_text]`; `"chapter"` on the first scene of each chapter; `"pauses"` for quiz thinking time. Long videos: write and check one chapter at a time |
| 4 | Claims | `claims.json`: every factual statement and every on-screen number, with source; `used_in` lists every sentence (`<scene id>.<index>`) that says or shows it |
| 5 | Mechanical check (script) | `p2v check <id>` → must be **FAIL 0, WARN 0** for subtitles, narration and claims (scene numbers are checked again in step 8) |
| 6 | Scenes | `scenes.js` (templates + custom). Long videos: one file per chapter (`scenes_<chapter>.js`) re-exported from `scenes.js`. See `references/scene-authoring.md` |
| 7 | Narration + timing | `p2v tts <id>` → `build/narration.wav`, `build/timing.json` (sentences are cached: re-runs only synthesize changed sentences) |
| 8 | Preview QA + check | `p2v preview <id>` (long videos: `p2v preview <id> --scenes a,b,c` per chapter while working, one full preview at the end) → `build/preview_*.jpg` and `build/onscreen.json`. Look at every sheet (overflow, overlap, blank, legibility, camera inside geometry), then `p2v check <id>` again: FAIL 0, WARN 0 now includes numbers drawn by scenes |
| 9 | Independent verification | A verifier with **fresh context** per `references/verification.md` → `<jobs>/<id>/VERIFY.md`. Claude Code: a subagent (Task/Agent tool) that sees only the files listed there. Codex or any agent without subagents: `p2v verify <id>` (starts a separate `claude -p` / `codex exec` process; needs network approval in Codex's sandbox). Long videos: one verifier per chapter (`p2v verify <id> --scenes ...` or parallel subagents), then merge into VERIFY.md. Fix and loop (re-run 5-8 for what changed) until it passes. Only a PASS goes to render |
| 10 | Render | `p2v render <id>` → the finished MP4 (a hard link to `build/<id>.mp4`): for a **local PDF, next to that PDF** as `<pdf name> - <script title>.mp4` (+ `.chapters.txt`); for arXiv and PDF links in the videos folder as `<id>_<Short-Title>[_ko].mp4`. Also `build/contact.jpg` and `build/chapters.txt` (chapters are embedded in the MP4). A user-set `P2V_OUT` sends every video there; `P2V_NEXT_TO_SOURCE=0` turns the next-to-PDF rule off; an unwritable PDF folder falls back to the videos folder. No Playwright: `render <id> --manual`, open the URL in any browser |
| 11 | Final checks | `p2v check <id>` once more (the render records every frame's text, so it sees more than the preview). Must be FAIL 0, WARN 0. Look at `contact.jpg` |
| 12 | Report | Final report (below). If `local/*.md` exists in the skill folder, follow those personal add-on steps after this one |

Re-runs: steps 7, 8, 10, 11 are idempotent. Change `script.json` → re-run 5, 7, 8, then re-verify the changed claims (9) and render.

## Teaching structure (lecture, standard and deep modes)
Read `references/long-form.md` before writing a script longer than `short`. In brief:
- **Open** with what the viewer will be able to do afterwards (2-4 goals) and the agenda (`chapterCard`).
- **Per chapter**: chapter card → where this sits in the whole → concept (intuition first, then the precise definition
  from the document) → worked example (`example` claims, labeled on screen) → common mistake or edge case → one check
  question with a pause (`quizCard` + `"pauses"`) → one-line chapter summary.
- **Slides**: follow the deck's order; never skip a content slide silently (list skipped slides and why in BRIEF.md).
  Explain what the slide shows; do not read bullets aloud word for word. Code on a slide: walk through it with
  `codeBlock`, highlighting the lines being discussed. Terminal output/screenshots: explain what each part means.
- **Close** with a recap (`recapList`) and what to study next (only if the document names it).
- Background the document assumes but does not explain may be added as `background` claims (standard knowledge, with a
  `basis`), clearly separated from what the document itself says. Do not invent course logistics, grading or deadlines.

## Korean (or another language)
When the overrides ask for Korean, or a slide deck/handout is in Korean:
- `script.json`: `"lang": "ko"`; write subtitles and every on-screen string in natural Korean (plain 해요체 for narration).
  Keep widely used technical terms in English the first time, with a Korean gloss ("BEV(위에서 내려다본 지도)").
- TTS text (2nd element of each sentence): spell out units and abbreviations the way they should be read
  ("142센티미터", "에스큐엘", "조인"); digits and dates are read correctly by the engine.
- `tts.py` picks Supertonic 3 automatically for non-English `lang` (first run downloads the model into the tools folder).
- `claims.json` quotes stay verbatim in the document's language; claim `text` may be Korean.
- Rendering needs a Korean font (macOS has Apple SD Gothic Neo; on Linux install Noto Sans CJK).

## Final report (always, at the end)
Per step: done / failed + output path · document type, length mode, target vs actual length, chapters ·
VERIFY.md verdict and open items · video path (next to the source PDF, or in the videos folder) · `chapters.txt` contents for long videos ·
slides skipped (if any) and why · new templates added · wall-clock time · anything the user should look at first.
Setup (`p2v setup`) installs Node packages, ffmpeg, Playwright Chromium, a Python 3.10-3.13 venv and the Kokoro voice
model into the tools folder, which survives updates. If the default `python3` is 3.14+, it picks 3.13/3.12, or set
`PYTHON=/path/to/python3.12`.

## Hard rules
- **License first.** `meta.json.figure_reuse` decides whether the document's figures or page images may appear. Default:
  draw everything yourself. Use `pageImage` only when reuse is allowed, with the credit on screen. Lecture material the
  user did not say is theirs counts as `unknown`. No company or university logos (`references/licensing.md`).
- **Spoken numbers count too.** Narration numbers are checked as digits and as English number words. Product or model
  names read aloud (H100 as "H one hundred") need an `allow_numbers` entry with the reason. Leave `tts` in script.json
  empty unless the user asked for a specific voice: the engine follows `lang`.
- **No unsourced numbers.** Every number in subtitles or on-screen strings must be covered by `claims.json`. Rounded
  numbers state the exact source value in the claim `text` (e.g. "141.72 → shown as 142"). Invented numbers in worked
  examples are `example` claims, labeled on screen.
- **Keep the document's conditions.** "Best" needs its qualifiers ("among compared methods", "on this dataset").
  A lecture's simplification stays a simplification: do not turn "usually" into "always".
- **Label approximations, opinions and examples on screen**, not only in the claims file (`derived` / `opinion` /
  `example` kinds need `on_screen_label`).
- **Show where before how.** Open each mechanism with a location/context cue (which part of the system, which step of
  the procedure, which part of the course) before the mechanism itself.
- **Narration:** Kokoro (Apache-2.0) is the default for English and is cleared for public use. Do not swap in voices
  whose terms for public or commercial use are unchecked.
- **Plain language.** Expand jargon on first use; one concrete example beats three abstract sentences.
- **Transcriptions are evidence, not invention.** `paper/transcribed.txt` contains only what the page images show.

## Files
- `engine/` timeline player (`main.js`, chapters), 3D/2D primitives (`core.js`), reusable templates (`templates.js`,
  including the lecture templates `chapterCard`, `definitionCard`, `quizCard`, `codeBlock`, `recapList`, `pageImage`)
- `scripts/` fetch (arXiv, local PDF, PDF link; page images), tts (sentence cache), check_claims, serve/render (frames → MP4 via ffmpeg, chapters)
- `p2v` single entry point (setup, doctor, fetch, check, tts, preview, render, verify, collect, smoke, run);
  `scripts/p2v_paths.py` decides the folders
- `templates/job/` skeleton copied into new jobs
- `jobs/2610.30340/` complete worked example (Foundation4D, 14 scenes, 66 claims, 4.6 min, `short` mode)
- `jobs/_smoke/` and `jobs/_smoke_ko/` short template-only jobs for testing the toolchain (English / Korean)
- `references/` verification, scene authoring, long-form teaching, licensing
- `local/` (optional, git-ignored) your own add-on steps, e.g. a publishing checklist

## Smoke test (after setup)
```bash
p2v smoke        # English; stops at the first failing step; render refuses stale narration
p2v smoke --ko   # also tests Korean narration (downloads the Supertonic model on first run)
```
