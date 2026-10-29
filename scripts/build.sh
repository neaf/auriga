#!/bin/sh
# Build aasdk + autoapp from `patches/` alone (macOS).
#
# Clones both upstreams at their pinned commits into a scratch root, applies
# every patch in `patches/` in the documented order, configures and builds aasdk
# and autoapp, then reports the artifacts. The nested `openauto/` and
# `aasdk-upstream/` trees, `build-aasdk-mac/`, `build-openauto-mac/` and a
# running head unit are never touched: the script works from its own clones, so
# a successful run proves `patches/` alone reproduces a buildable stack.
# See docs/Build.md.
#
# Usage: scripts/build.sh [-d DIR | -t] [-j N] [-h]
#   -d DIR  work in DIR and keep it (default: .build-from-patches in the repo)
#   -t      work in a mktemp directory and delete it afterwards
#   -j N    parallel compile jobs (default: hw.ncpu)
#   -h      this help

set -eu

BASE=$(cd "$(dirname "$0")/.." && pwd)
PATCH_DIR=$BASE/patches
JOBS=$(sysctl -n hw.ncpu 2>/dev/null || getconf _NPROCESSORS_ONLN 2>/dev/null || echo 4)
WORK=$BASE/.build-from-patches
TEMP_WORK=0

# Pinned upstreams. Both are cloned fresh; the patch lists below are the only
# source of the Auriga changes, so an upstream commit bump is edited here and in
# docs/Build.md#build-order.
AASDK_URL=https://github.com/opencardev/aasdk.git
AASDK_COMMIT=9bf6adf933665dee26532201719fac14a047ccf1
AASDK_PATCHES="aasdk-usb-filter.patch aasdk-version-absl.patch"

OPENAUTO_URL=https://github.com/opencardev/openauto.git
OPENAUTO_COMMIT=4cc739b813622739b09352655581072fc4d39280
OPENAUTO_PATCHES="openauto-capture.patch openauto-macos.patch
openauto-auriga-usb-filter.patch openauto-auriga-gps-guard.patch
openauto-auriga-identity.patch"

APPLIED=0
FAILED=0

say() { echo "build: $*"; }
die() { FAILED=1; echo "build: $*" >&2; exit 1; }

usage() {
  cat <<'EOF'
usage: scripts/build.sh [-d DIR | -t] [-j N] [-h]

  -d DIR  work in DIR and keep it (default: .build-from-patches in the repo)
  -t      work in a mktemp directory and delete it afterwards
  -j N    parallel compile jobs (default: hw.ncpu)
  -h      this help

Clones aasdk and openauto at their pinned commits, applies every patch in
patches/ in order, configures and builds both, and reports the artifacts.
EOF
}

# A failed step keeps the scratch tree so the full log survives.
cleanup() {
  [ -n "${WORK:-}" ] && [ -d "$WORK" ] || return 0
  if [ "$TEMP_WORK" -eq 1 ] && [ "$FAILED" -eq 0 ]; then
    rm -rf "$WORK"
  elif [ "$TEMP_WORK" -eq 1 ]; then
    echo "build: kept $WORK for inspection" >&2
  fi
}

while [ $# -gt 0 ]; do
  case $1 in
    -d) [ $# -ge 2 ] || die "-d needs a directory"; WORK=$2; shift 2 ;;
    -t) WORK=$(mktemp -d "${TMPDIR:-/tmp}/auriga-build.XXXXXX"); TEMP_WORK=1; shift ;;
    -j) [ $# -ge 2 ] || die "-j needs a number"; JOBS=$2; shift 2 ;;
    -j[0-9]*) JOBS=${1#-j}; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown option $1 (try -h)" ;;
  esac
done

[ "$(uname -s)" = Darwin ] || die "macOS only (docs/Build.md)"
command -v git >/dev/null 2>&1 || die "git is required"

# Every patch file must be in one of the ordered lists: a patch that no build
# applies is a silent disagreement between `patches/` and the source of truth.
check_complete() {
  known=$(printf '%s\n' $AASDK_PATCHES $OPENAUTO_PATCHES)
  for file in "$PATCH_DIR"/*.patch; do
    name=$(basename "$file")
    printf '%s\n' "$known" | grep -qx "$name" ||
      die "patches/$name is not applied by this script; add it to the order"
  done
}

# A pristine tree at the pinned commit: fresh clone, or reset an earlier one.
prepare_tree() {
  url=$1
  commit=$2
  dir=$3
  if [ -d "$dir/.git" ]; then
    git -C "$dir" fetch --quiet origin 2>/dev/null || true
    git -C "$dir" -c advice.detachedHead=false checkout --quiet --force "$commit"
    git -C "$dir" clean -qfd
    git -C "$dir" checkout --quiet -- .
  else
    mkdir -p "$(dirname "$dir")"
    git clone --quiet "$url" "$dir"
    git -C "$dir" -c advice.detachedHead=false checkout --quiet "$commit"
  fi
}

apply_patches() {
  dir=$1
  list=$2
  for name in $list; do
    [ -f "$PATCH_DIR/$name" ] || die "missing patches/$name"
    if ! git -C "$dir" apply "$PATCH_DIR/$name"; then
      die "patches/$name does not apply to $(basename "$dir")"
    fi
    APPLIED=$((APPLIED + 1))
    say "applied $name"
  done
}

formula() {
  path=$(brew --prefix "$1" 2>/dev/null || true)
  [ -n "$path" ] && [ -d "$path" ] || die "missing Homebrew formula $1 (docs/Build.md#toolchain)"
  echo "$path"
}

check_complete
command -v brew >/dev/null 2>&1 || die "Homebrew is required (docs/Build.md#toolchain)"

BOOST=$(formula boost@1.85)
QT=$(formula qt@5)
PROTOBUF=$(formula protobuf)
ABSEIL=$(formula abseil)
TAGLIB=$(formula taglib)
RTAUDIO=$(formula rtaudio)
UTILLINUX=$(formula util-linux)
GPSD=$(formula gpsd)
OPENSSL=$(formula openssl@3)
LIBUSB=$(formula libusb)

mkdir -p "$WORK" || die "cannot create $WORK"
trap cleanup EXIT INT TERM
WORK=$(cd "$WORK" && pwd)
LOG=$WORK/build.log
: >"$LOG"
say "work root $WORK"

# Configure and build steps are quiet on success: a parallel aasdk build emits
# tens of thousands of warning lines. The whole log stays in $LOG and its tail is
# printed when a step fails.
run_step() {
  label=$1
  shift
  say "$label"
  if ! "$@" >>"$LOG" 2>&1; then
    echo "build: $label failed; last 40 log lines:" >&2
    tail -n 40 "$LOG" >&2
    die "failed at: $label (full log $LOG)"
  fi
}

say "checkout aasdk $AASDK_COMMIT"
prepare_tree "$AASDK_URL" "$AASDK_COMMIT" "$WORK/aasdk"
say "checkout openauto $OPENAUTO_COMMIT"
prepare_tree "$OPENAUTO_URL" "$OPENAUTO_COMMIT" "$WORK/openauto"

apply_patches "$WORK/aasdk" "$AASDK_PATCHES"
apply_patches "$WORK/openauto" "$OPENAUTO_PATCHES"

run_step "configure aasdk" \
  cmake -S "$WORK/aasdk" -B "$WORK/build-aasdk" \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
  -DSKIP_BUILD_PROTOBUF=ON \
  -DSKIP_BUILD_ABSL=ON \
  -DAASDK_TEST=OFF \
  -DBoost_DIR="$BOOST/lib/cmake/Boost-1.85.0" \
  -DCMAKE_PREFIX_PATH="$BOOST;$PROTOBUF;$ABSEIL;$OPENSSL;$LIBUSB"

run_step "build aasdk (-j$JOBS)" \
  cmake --build "$WORK/build-aasdk" --target aasdk -j"$JOBS"

run_step "configure autoapp" \
  cmake -S "$WORK/openauto" -B "$WORK/build-openauto" \
  -DCMAKE_BUILD_TYPE=Release -DNOPI=ON \
  -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
  -DAASDK_INCLUDE_DIR="$WORK/aasdk/include/aasdk" \
  -DAASDK_LIB_DIR="$WORK/build-aasdk/lib/libaasdk.a" \
  -DAAP_PROTOBUF_INCLUDE_DIR="$WORK/build-aasdk/protobuf" \
  -DAAP_PROTOBUF_LIB_DIR="$WORK/build-aasdk/lib/libaap_protobuf.a" \
  -DCMAKE_CXX_FLAGS_INIT="-I$WORK/aasdk/include -I$ABSEIL/include -I$TAGLIB/include -I$GPSD/include" \
  -DBoost_DIR="$BOOST/lib/cmake/Boost-1.85.0" \
  -DTAGLIB_LIBRARIES="$TAGLIB/lib/libtag.dylib" \
  -DTAGLIB_INCLUDE_DIRS="$TAGLIB/include/taglib" \
  -DOPENSSL_LIBRARIES="$OPENSSL/lib/libssl.dylib;$OPENSSL/lib/libcrypto.dylib" \
  -DCMAKE_EXE_LINKER_FLAGS="$OPENSSL/lib/libssl.dylib $OPENSSL/lib/libcrypto.dylib" \
  -DCMAKE_PREFIX_PATH="$QT;$BOOST;$PROTOBUF;$ABSEIL;$TAGLIB;$RTAUDIO;$UTILLINUX;$GPSD;$OPENSSL;$LIBUSB"

run_step "build autoapp (-j$JOBS)" \
  cmake --build "$WORK/build-openauto" --target autoapp -j"$JOBS"

[ -f "$WORK/build-aasdk/lib/libaasdk.a" ] || die "libaasdk.a was not produced"
[ -x "$WORK/build-openauto/bin/autoapp" ] || die "autoapp was not produced"

say "ok: $APPLIED patches -> aasdk + autoapp"
echo "  aasdk:   $WORK/build-aasdk/lib/libaasdk.a"
echo "  autoapp: $WORK/build-openauto/bin/autoapp"
if [ "$TEMP_WORK" -eq 1 ]; then
  echo "  work root removed on exit (-d DIR keeps it)"
fi
