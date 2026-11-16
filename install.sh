#!/usr/bin/env bash
# doc2video installer / updater (git clone instead of the plugin marketplace).
#   curl -fsSL https://raw.githubusercontent.com/calzsvg/doc2course/main/install.sh | bash                 # Claude Code
#   curl -fsSL https://raw.githubusercontent.com/calzsvg/doc2course/main/install.sh | bash -s -- --codex   # Codex
#   ... | bash -s -- --both                                                                              # both agents
# Run it again to update. Claude Code: ~/.claude/skills/doc2video (/doc2video). Codex: ${CODEX_HOME:-~/.codex}/skills/doc2video
# ($doc2video). --both clones once for Claude Code and links the Codex folder to it.
# Override the clone location with P2V_DIR=/path (e.g. on an external disk; the agent folders then get a symlink to it,
# and tools, jobs and videos all stay next to the clone).
set -euo pipefail

# Everything runs inside main, called on the last line, so a download cut off halfway executes nothing.
main() {
  local target="claude" a
  for a in "$@"; do case "$a" in --codex) target=codex ;; --both) target=both ;; --claude) target=claude ;;
    *) echo "doc2video: unknown option $a (--claude, --codex, --both)"; exit 2 ;; esac; done
  local claude_dir="$HOME/.claude/skills/doc2video" codex_dir="${CODEX_HOME:-$HOME/.codex}/skills/doc2video"
  local default; [ "$target" = codex ] && default="$codex_dir" || default="$claude_dir"
  local dir="${P2V_DIR:-$default}" repo="https://github.com/calzsvg/doc2course.git" c
  for c in git node npm python3 curl; do command -v "$c" >/dev/null || { echo "doc2video: '$c' is required"; exit 1; }; done
  if [ -d "$dir/.git" ]; then
    echo "== updating $dir"
    git -C "$dir" pull --ff-only || { echo "doc2video: could not fast-forward $dir (local changes?). Resolve them, then run this again."; exit 1; }
  elif [ -e "$dir" ]; then
    echo "doc2video: $dir exists but is not a git clone. Move it or set P2V_DIR."; exit 1
  else
    echo "== installing into $dir"; mkdir -p "$(dirname "$dir")"; git clone --depth 1 "$repo" "$dir"
  fi
  link() {   # agent skill folder -> clone (when the clone lives elsewhere)
    local l="$1"; [ "$l" = "$dir" ] && return 0
    mkdir -p "$(dirname "$l")"
    if [ -L "$l" ] || [ ! -e "$l" ]; then ln -sfn "$dir" "$l"; echo "linked $l -> $dir"; else echo "note: $l exists; not replaced"; fi
  }
  case "$target" in claude) link "$claude_dir" ;; codex) link "$codex_dir" ;; both) link "$claude_dir"; link "$codex_dir" ;; esac
  "$dir/p2v" setup
  local videos; videos=$("$dir/p2v" paths | sed -n "s/^export P2V_OUT='\(.*\)'$/\1/p")
  printf '\ndoc2video is ready.\n  Claude Code:  /doc2video ~/Downloads/lecture.pdf\n  Codex:        $doc2video ~/Downloads/lecture.pdf\n  Videos land in: %s\n  Update later:   run this installer again\n' "$videos"
}

main "$@"
