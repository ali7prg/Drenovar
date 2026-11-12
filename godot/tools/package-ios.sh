#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd "$(dirname "$0")/.." && pwd)"
output_dir="${1:-"$project_root/build/ios"}"
mkdir -p "$output_dir"
output_dir="$(cd "$output_dir" && pwd)"
godot_bin="${GODOT_BIN:-godot}"
"$godot_bin" --headless --path "$project_root/project" --editor --import
"$godot_bin" --headless --path "$project_root/project" --export-release iOS "$output_dir/DRENOVAR.ipa"
test -s "$output_dir/DRENOVAR.xcodeproj/project.pbxproj"
test -s "$output_dir/DRENOVAR.pck"
if [[ "$(uname -s)" != Darwin ]]; then
  printf '%s\n' 'Xcode project and iOS resource pack exported. A macOS build host is required to link the iPhone binary.'
  exit 0
fi

xcodebuild -project "$output_dir/DRENOVAR.xcodeproj" -scheme DRENOVAR \
  -configuration Release -sdk iphoneos -arch arm64 \
  -derivedDataPath "$output_dir/DerivedData" \
  CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO DEVELOPMENT_TEAM= \
  build
app="$output_dir/DerivedData/Build/Products/Release-iphoneos/DRENOVAR.app"
test -s "$app/DRENOVAR"
file "$app/DRENOVAR" | grep -q arm64
payload="$(mktemp -d)"
trap 'rm -rf "$payload"' EXIT
mkdir -p "$payload/Payload"
ditto "$app" "$payload/Payload/DRENOVAR.app"
(
  cd "$payload"
  zip -q -r -y "$output_dir/DRENOVAR-unsigned.ipa" Payload
)
unzip -tq "$output_dir/DRENOVAR-unsigned.ipa"
