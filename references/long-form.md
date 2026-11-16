# Long-form and lecture videos

Read this before writing a script in `standard`, `lecture` or `deep` mode (SKILL.md, Length modes).
The goal is a video someone can learn from without the document in front of them, not a longer teaser.

## Planning (BRIEF.md)
1. **Inventory.** List every page/slide: `content` (teaches something), `title/agenda`, `exercise`, `admin`
   (logistics, grading), `references`. Every content slide is covered or listed as skipped with a reason.
   For each content slide also list its **points**: every bullet and sub-point, every labeled part of a figure or
   table the slide explains, every step of its example (read the page image for figures and scanned slides). Each
   point is mapped to the scene and sentence that explains it. This point list is the coverage contract the verifier
   checks; only photos, decorative images and links may be left out, and each such omission is named with a reason.
2. **Chapters.** Use the document's own sections (slide section headers, numbered parts, paper sections). 4-8 chapters;
   each 2-6 minutes. A chapter that would exceed ~8 minutes is split.
3. **Budget.** Per chapter: estimated minutes, scene list, which slides/pages each scene covers. The estimate comes
   from the point list, not the other way round: if the script is longer than planned, split the part (or the
   chapter), never remove covered points, examples or check questions to save time. Speaking rate: about
   140-160 English words per minute; Korean about 300-350 characters per minute. A 20-minute script is roughly
   3,000 English words: write it chapter by chapter, checking each (`p2v check`) before the next.
4. **Learning goals.** 2-4 "after this video you can ..." lines, taken from the document's goals if it states them.

## Script patterns
Per chapter (ids are examples; scene ids must be unique across the whole script):

| scene | template | content |
|---|---|---|
| `ch2` | `chapterCard` | chapter title, one-sentence promise, agenda with this chapter highlighted. `"chapter": "Joins"` on this scene |
| `ch2_where` | custom / `flow` | where this sits: what came before, what this chapter adds |
| `ch2_concept` | custom / `definitionCard` | intuition first (an everyday picture), then the document's definition (a `quote` claim with `page`) |
| `ch2_example` | custom / `codeBlock` / `definitionCard` | a worked example, step by step; one visual beat per sentence |
| `ch2_pitfall` | `definitionCard` (pitfall) / custom | the common mistake or edge case, and how to tell |
| `ch2_quiz` | `quizCard` | one question; `"pauses": { "0": 4 }` gives 4 s of thinking time after the question |
| `ch2_sum` | `recapList` (1-3 items) | what to remember from this chapter |

Whole video: `title` → `goals` (`recapList` with the goals, or `cardGrid`) → `agenda` (`chapterCard` with `current: 0`
or a custom overview) → chapters → `recap` (`recapList`) → `end` (`endCard` with the source credit).

Writing rules:
- One idea per sentence; each sentence has a visual beat (`S.P(k)`). 2-6 sentences per scene; split longer scenes.
- Do not read slide bullets aloud. Say what the slide means and why; the screen shows the structure.
- Name the slide/page when it helps the viewer follow along with the original ("on the join slide").
  Page numbers spoken or shown are numbers: cover them with `allow_numbers` ("page reference").
- Worked examples: use small, checkable values; every invented value is an `example` claim; the scene shows the
  `on_screen_label` ("example", "예시"). The verifier recomputes the example.
- Background the document assumes (e.g. what a primary key is, in a lecture on joins) may be explained briefly as a
  `background` claim with a `basis`. Keep it short and mark the switch ("a quick reminder: ...").
- Check questions test the chapter's main point, not trivia. The answer follows from what the video said.
- Transitions name the link ("Now that rows can be matched by key, the next question is what happens to rows that
  have no match").

## Deeper than the slides
A lecture video replaces the lecture *and* the slides, so it must say more than the slides do:
- Every point in the inventory is explained in the narration, not only shown on screen.
- Add what a lecturer would say aloud: why the idea exists, the intermediate steps the slide skips, a worked example
  with small checkable values, the common mistake, and how this connects to the previous and next topic.
- A slide that only shows a figure (datapath, circuit, state diagram, table) gets a walk-through of each part.
- "Mentioned briefly" is not coverage: a point is covered when the viewer could explain it after watching.

## Lecture slides specifics
- Many decks are images (screenshots, scanned handouts, terminal output). Read the page images; transcribe text-less
  pages into `paper/transcribed.txt` before writing claims about them.
- Lab/practice slides (실습): show the command or code (`codeBlock`), say what each part does, then what the output means.
  Do not claim the commands were run or outputs reproduced unless the slide shows that output.
- Exercises/assignments on slides: present them as check questions or "try it yourself" prompts; do not solve graded
  assignments the deck marks as homework unless the user asked for solutions.
- The lecturer's name, course code and university go in the end card credit only if the user wants them; no logos.

## Production at length
- `p2v tts` caches sentences, so editing one chapter only re-synthesizes that chapter.
- `p2v preview <id> --scenes a,b,c` previews one chapter while you work; run one full `p2v preview <id>` before verifying.
- Verification per chapter (parallel subagents or `p2v verify <id> --scenes ...`), merged into one VERIFY.md with the
  overall verdict being the worst chapter verdict.
- Render time grows with length (30 fps × duration): a 20-minute video is 36,000 frames. Use the GPU default and
  `--workers`; render once, after the verifier's PASS.
- `build/chapters.txt` (also embedded in the MP4) lists chapter timestamps for the video description.
