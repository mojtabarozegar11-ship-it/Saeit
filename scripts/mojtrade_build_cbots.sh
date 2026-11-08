#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if ! command -v dotnet >/dev/null 2>&1; then
  echo "BLOCKED: .NET SDK is missing. No cTrader compilation performed." >&2
  exit 2
fi
sdk_major="$(dotnet --version | cut -d. -f1)"
if [[ "${sdk_major}" -lt 8 ]]; then
  echo "BLOCKED: cTrader CLI requires a .NET 8 compatible cBot build." >&2
  exit 2
fi

for project in MojTradeDemoBot MojTradeOmegaXDemoBot; do
  dotnet build "${root}/trading/build/${project}/${project}.csproj" \
    --configuration Release --property:AlgoPublish=False
done

echo "Build step finished. Independently verify .algo outputs and cTrader metadata."
