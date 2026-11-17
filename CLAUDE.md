# CLAUDE.md

This repo is the **doc2course** Claude Code skill. Two kinds of work happen here:

1. **Making a video** (the user gave a paper, slides or PDF): read `SKILL.md` and follow it. The skill folder is this
   repo's root; every command is `<repo>/p2v <subcommand>`. Jobs and videos go to the folders `p2v doctor` prints.
2. **Changing the skill itself**: keep these invariants.
   - Every frame is a pure function of time (`S.t`, `S.P(k)`); no state accumulated across frames (parallel render, preview jumps).
   - Templates draw no digits of their own: every on-screen number must be covered by `claims.json` (`scripts/check_claims.py`).
   - `scripts/p2v_paths.py` and `scripts/lib.mjs` decide folders the same way; change both together.
   - Tools and caches live in the tools folder (`P2V_TOOLS`), never in `~/Library/Caches` or `~/.cache`.
   - Run `./p2v test` after changes (no tools or network needed). `./p2v smoke` needs `./p2v setup` first.
   - Do not commit unless asked.
