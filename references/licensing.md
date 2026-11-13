# Licensing checklist

Ideas, facts and numbers are not copyrightable; expression (figures, text, tables as images) is.
Explaining in your own words with your own visuals is the default.

| arXiv license | paper figures in the video |
|---|---|
| CC BY 4.0 / CC0 | allowed with attribution; say "adapted from ... (CC BY 4.0), changes made" |
| CC BY-SA 4.0 | allowed; the adapted figure must be CC BY-SA |
| CC BY-NC-* | non-commercial only: avoid if the video earns money |
| CC BY-ND / BY-NC-ND | no modification: avoid |
| arXiv non-exclusive (most papers) | no reuse grant: ask the authors, or draw your own |

The license shows under "Download" on the abs page; `fetch_paper.py` records it in `meta.json`.

Local files and PDF links (lecture slides, handouts): `meta.json.figure_reuse` starts as `unknown`. Draw your own visuals.
If the user says the material is theirs or that they may reuse it, re-run `p2v fetch <file> --figures own` and then
page images (`pageImage`) may appear, credited on screen. Lecture slides often contain third-party figures
(textbook images, screenshots of products, logos): even with `--figures own`, avoid pages that are mostly someone
else's figure or logo. A video made from someone else's course material is for personal study unless the
lecturer allows more; say so in the report.

Also check:
- Dataset imagery inside figures (Waymo Open, nuScenes, ...) has its own terms that the paper's CC license may not cover. Avoid.
- Company names in narration are fine; logos and liveries are not.
- Fair use is case-by-case; do not rely on it for commercial use. (General guidance, not legal advice.)
- Narration: Kokoro voices (Apache-2.0) are fine. Supertonic 3 (non-English default) weights are OpenRAIL-M: use is allowed, including commercial, subject to the use restrictions in its LICENSE; read it before monetizing. Google Translate TTS: commercial terms unchecked, previews only.
- Music: only tracks whose license covers how the video will be used; record the source in BRIEF.md.
- Description credit: title, authors, arXiv link, license, "not affiliated with the authors".
