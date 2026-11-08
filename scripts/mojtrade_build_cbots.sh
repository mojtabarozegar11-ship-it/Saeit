#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if ! command -v dotnet >/dev/null 2>&1; then
  echo "BLOCKED: .NET SDK is missing. No cTrader compilation performed." >&2
  exit 2
fi
sdk_major="$(dotnet --version | cut -d. -f1)"
if [[ "${sdk_major}" -lt 8 ]]; then
  echo "BLOCKED: build host needs .NET 8 SDK; cTrader project target is net6.0." >&2
  exit 2
fi

build_marker="$(mktemp)"
trap 'rm -f "$build_marker"' EXIT
cd "${root}/trading/build"
echo "Selected .NET SDK in cBot build directory: $(dotnet --version)"

for project in MojTradeDemoBot MojTradeOmegaXDemoBot; do
  project_dir="${root}/trading/build/${project}"
  touch "${build_marker}"
  dotnet build "${project_dir}/${project}.csproj" \
    --configuration Release --no-incremental --property:AlgoPublish=False

  mapfile -d '' artifacts < <(find "${project_dir}" -type f -name '*.algo' \
    -newer "${build_marker}" -print0)
  if (( ${#artifacts[@]} != 1 )); then
    echo "BLOCKED: ${project} needs exactly one fresh original .algo artifact." >&2
    exit 3
  fi
  exported="$(dirname "${artifacts[0]}")/${project}.algo"
  if [[ "${artifacts[0]}" != "${exported}" ]]; then
    cp -- "${artifacts[0]}" "${exported}"
  fi
  echo "Verified fresh ${project} export alias (internal metadata unverified):"
  sha256sum "${exported}"
done

echo "Both cBots produced fresh .algo files. Broker runtime and metadata remain unverified."
