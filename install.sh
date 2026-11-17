#!/usr/bin/env bash
# doc2course installer / updater (git clone instead of the plugin marketplace).
#   curl -fsSL https://raw.githubusercontent.com/calzsvg/doc2course/main/install.sh | bash
# Run it again to update. Installs into ~/.claude/skills/doc2course (Claude Code: /doc2course).
# Override the clone location with P2V_DIR=/path (e.g. on an external disk; the skill folder then gets a symlink to it,
# and tools, jobs and videos all stay next to the clone).
set -euo pipefail

# Everything runs inside main, called on the last line, so a download cut off halfway executes nothing.
main() {
  [ $# -eq 0 ] || { echo "doc2course: unknown option $1 (the installer takes no options)"; exit 2; }
  local claude_dir="$HOME/.claude/skills/doc2course"
  local dir="${P2V_DIR:-$claude_dir}" repo="https://github.com/calzsvg/doc2course.git" c
  for c in git node npm python3 curl; do command -v "$c" >/dev/null || { echo "doc2course: '$c' is required"; exit 1; }; done
  if [ -d "$dir/.git" ]; then
    echo "== updating $dir"
    git -C "$dir" pull --ff-only || { echo "doc2course: could not fast-forward $dir (local changes?). Resolve them, then run this again."; exit 1; }
  elif [ -e "$dir" ]; then
    echo "doc2course: $dir exists but is not a git clone. Move it or set P2V_DIR."; exit 1
  else
    echo "== installing into $dir"; mkdir -p "$(dirname "$dir")"; git clone --depth 1 "$repo" "$dir"
  fi
  link() {   # skill folder -> clone (when the clone lives elsewhere)
    local l="$1"; [ "$l" = "$dir" ] && return 0
    mkdir -p "$(dirname "$l")"
    if [ -L "$l" ] || [ ! -e "$l" ]; then ln -sfn "$dir" "$l"; echo "linked $l -> $dir"; else echo "note: $l exists; not replaced"; fi
  }
  link "$claude_dir"
  "$dir/p2v" setup
  local videos; videos=$("$dir/p2v" paths | sed -n "s/^export P2V_OUT='\(.*\)'$/\1/p")
  printf '\ndoc2course is ready.\n  Claude Code:  /doc2course ~/Downloads/lecture.pdf\n  Videos land in: %s\n  Update later:   run this installer again\n' "$videos"
}

main "$@"
