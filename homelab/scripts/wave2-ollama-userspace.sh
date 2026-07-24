#!/bin/bash
# Wave 2: install a complete Ollama under ~/opt/ollama (no sudo).
# Use when /usr/local ollama is broken (missing llama-server) and sudo needs a password.
# Does NOT enable systemd / boot. Session-only: PATH + ollama serve.
set -euo pipefail

PREFIX="${OLLAMA_USER_PREFIX:-$HOME/opt/ollama}"
TMPDIR="${TMPDIR:-/tmp}"
ARCHIVE="$TMPDIR/ollama-linux-amd64.tar.zst"
URL="${OLLAMA_DOWNLOAD_URL:-https://ollama.com/download/ollama-linux-amd64.tar.zst}"

echo "== stop broken system ollama if listening =="
pkill -f '[o]llama serve' 2>/dev/null || true
sleep 1

echo "== download $URL =="
curl -fL --retry 3 --retry-delay 2 -o "$ARCHIVE" "$URL"
ls -lh "$ARCHIVE"

echo "== extract to $PREFIX =="
rm -rf "$PREFIX"
mkdir -p "$PREFIX"
# Official archive is zstd tar: bin/ollama + lib/ollama/...
if command -v zstd >/dev/null 2>&1; then
  zstd -d -c "$ARCHIVE" | tar -x -C "$PREFIX"
elif tar --help 2>&1 | grep -q -- '--zstd'; then
  tar --zstd -xf "$ARCHIVE" -C "$PREFIX"
else
  # fallback: decompress then untar
  unzstd -f "$ARCHIVE" -o "${ARCHIVE%.zst}"
  tar -xf "${ARCHIVE%.zst}" -C "$PREFIX"
fi
# Some archives nest under a top dir; normalize if needed
if [[ ! -x "$PREFIX/bin/ollama" ]]; then
  inner="$(find "$PREFIX" -maxdepth 3 -type f -name ollama | head -1)"
  if [[ -n "$inner" ]]; then
    root="$(dirname "$(dirname "$inner")")"
    if [[ "$root" != "$PREFIX" ]]; then
      mkdir -p "$PREFIX/bin" "$PREFIX/lib"
      cp -a "$root/bin/." "$PREFIX/bin/" 2>/dev/null || true
      cp -a "$root/lib/." "$PREFIX/lib/" 2>/dev/null || true
    fi
  fi
fi
test -x "$PREFIX/bin/ollama"
test -e "$PREFIX/lib/ollama/llama-server" || test -e "$PREFIX/lib/ollama/runners" || \
  find "$PREFIX/lib" -name 'llama-server' -o -name 'ollama_llama_server' 2>/dev/null | head -5

# Prefer userspace on PATH for this user
mkdir -p "$HOME/bin"
ln -sfn "$PREFIX/bin/ollama" "$HOME/bin/ollama"
# shell profile hook (idempotent)
PROFILE="$HOME/.bashrc"
MARKER="# wave2-ollama-userspace"
if ! grep -qF "$MARKER" "$PROFILE" 2>/dev/null; then
  cat >>"$PROFILE" <<EOF

$MARKER
export PATH="\$HOME/bin:\$PATH"
export OLLAMA_LIBRARY_PATH="\$HOME/opt/ollama/lib/ollama\${OLLAMA_LIBRARY_PATH:+:\$OLLAMA_LIBRARY_PATH}"
EOF
fi

export PATH="$HOME/bin:$PATH"
export OLLAMA_LIBRARY_PATH="$PREFIX/lib/ollama${OLLAMA_LIBRARY_PATH:+:$OLLAMA_LIBRARY_PATH}"

echo "== version =="
"$PREFIX/bin/ollama" --version
find "$PREFIX/lib/ollama" -maxdepth 2 -type f -name 'llama-server*' 2>/dev/null | head -10 || true
ls -la "$PREFIX/lib/ollama" | head -25

echo "OK: userspace ollama at $PREFIX (boot: still OFF; start with: ollama serve)"
echo "Then: bash ~/homelab/scripts/wave2-finish.sh"
