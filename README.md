# doc2course

A **Claude Code** skill: turn a document into a narrated, fact-checked explainer video.
It takes an arXiv paper, **lecture slides**, a handout, or any other PDF, and makes anything from a 5-minute teaser to a
30-minute chaptered lecture video.

Forked from [SunandBean/paper2video](https://github.com/SunandBean/paper2video), which takes arXiv papers and makes 4-5 minute videos.

```
/doc2course ~/Downloads/week8-lab.pdf                    # lecture slides → lecture-mode video (chapters, examples, quizzes)
/doc2course ~/Downloads/week8-lab.pdf 한국어              # Korean narration and subtitles
/doc2course https://arxiv.org/abs/2610.30340             # a paper → 10-15 min walk-through (standard mode)
/doc2course 2610.30340 short                             # the original 4-5 min teaser
```

![demo: depth to 3D points, query-based detection, BEV occupancy](docs/demo.gif)

*Clips from the bundled example (made by paper2video in `short` mode): an explainer of NVIDIA's
[Foundation4D](https://arxiv.org/abs/2610.30340) (CC BY 4.0). All visuals are generated; every on-screen number traces back to the paper.*

## What changed from paper2video

| | paper2video | doc2course |
|---|---|---|
| Input | arXiv link | arXiv link, **local PDF** (slides, handouts, notes, reports), PDF link. Detects slides vs. papers, renders page images so the agent can read diagrams and screenshots, and lets the agent transcribe pages that have no text layer |
| Length | 4-5 min | `short` 4-6 min · `standard` 10-15 min (papers) · `lecture` about 1-1.5 min per content slide (slides) · `deep` 20-40 min |
| Structure | 10-14 scenes | chapters (progress-bar ticks, heading, MP4 chapter markers, `chapters.txt`); teaching pattern per chapter: concept → worked example → common mistake → quiz with thinking pause → summary |
| Templates | paper / results / 3D | plus `chapterCard`, `definitionCard`, `quizCard`, `codeBlock`, `recapList`, `pageImage` |
| Claims | quote, table, derived, opinion | plus `background` (standard knowledge a lecture assumes) and `example` (worked examples); quotes can be pinned to a `page`; transcribed pages are checked against the page image |
| Long runs | | TTS sentence cache (edit one chapter, re-synthesize one chapter), per-chapter preview and verification |

## Install

Requires git, Node 18+, Python 3.10-3.13 and about 1 GB of disk. macOS or Linux; Korean videos on Linux need Noto Sans CJK.

```bash
# ~/.claude/skills/doc2course
curl -fsSL https://raw.githubusercontent.com/calzsvg/doc2course/main/install.sh | bash
# with the clone on another disk (the skill folder gets a symlink; tools, caches, jobs and videos stay on that disk)
curl -fsSL https://raw.githubusercontent.com/calzsvg/doc2course/main/install.sh | P2V_DIR=/Volumes/External/doc2course bash
```

Claude Code plugin route: `/plugin marketplace add calzsvg/doc2course`, then `/plugin install doc2course@calzsvg`.

Where finished videos go: a video made from a **local PDF is saved next to that PDF** (`~/lectures/week8.pdf` →
`~/lectures/week8 - <video title>.mp4`, plus `.chapters.txt` for long videos). Videos of arXiv papers and PDF links go to the
videos folder. Set `P2V_OUT` to send every video to one folder, or `P2V_NEXT_TO_SOURCE=0` to turn the next-to-PDF rule off.

Where everything else goes: tools and caches (Node packages, headless Chromium, Python venv, voice models) in the tools folder;
jobs (and videos not made from a local PDF) in `~/doc2course/` for installed copies, or inside the clone when the skill folder is a symlink
to a clone elsewhere or a development checkout. Override with `P2V_HOME` (jobs and videos), `P2V_OUT`, `P2V_JOBS`, `P2V_TOOLS`.
`p2v doctor` prints every folder.

## Use

```
/doc2course <arxiv link | file.pdf | pdf link> [overrides]
/doc2course ~/lectures/db-week8.pdf deep, Korean
/doc2course ~/lectures/db-week8.pdf my own slides        # allows showing slide images (credited)
/doc2course 2610.35607 12 min, voice am_michael
```

Everything the skill does is also a terminal command, `p2v` in the skill folder:

```bash
p2v doctor                                  # folders and what is installed
p2v fetch ~/Downloads/lecture.pdf           # local PDF → job (prints the job id, document type, pages without text)
p2v preview <job> --scenes ch2,ch2_example  # preview one chapter
p2v verify <job>                            # fresh-context verifier → VERIFY.md
p2v render <job> [--workers N] [--gpu auto|cpu]
p2v run <source>                            # unattended run (claude -p)
p2v smoke [--ko] · p2v test · p2v help
```

## What's inside

- `SKILL.md` workflow and defaults Claude follows
- `engine/` timeline player (chapters), 3D/2D primitives, templates (papers and lectures)
- `p2v` single command for every step; `scripts/` fetch (arXiv / local / link, page images), TTS (cached), claims check, render/mux (chapters)
- `references/` verification layers, scene authoring, long-form teaching, licensing
- `.claude-plugin/` plugin manifests; `install.sh`; `CLAUDE.md` for Claude working on this repo
- `local/` optional, git-ignored: your own extra steps (e.g. a publishing checklist); the skill runs them after its final report
- `jobs/2610.30340/` worked example (Foundation4D, NVIDIA, CC BY 4.0), `jobs/_smoke/`, `jobs/_smoke_ko/` toolchain tests

License: MIT (see LICENSE), based on paper2video by Sunbin Kim. The example job includes text from the Foundation4D paper (arXiv 2610.30340, NVIDIA, CC BY 4.0).

Third-party: three.js (MIT), ffmpeg-static (downloads a GPL-3.0 FFmpeg build at install), kokoro-onnx (MIT) and Kokoro-82M weights (Apache-2.0),
supertonic (MIT code, Supertonic 3 weights under OpenRAIL-M), Playwright (Apache-2.0), pypdf (BSD), pypdfium2 (Apache-2.0 / BSD; PDFium BSD-3), Pillow (MIT-CMU).
