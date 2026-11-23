# Owner Android Security Lab — mojtaba.bot.ai

**Scope:** Internal capability of the single canonical bot. This is a defensive
offline educational integration, not a new robot, public API, phone-control
service, messaging extractor, surveillance tool, or background process.

## Registration

The canonical Django host can request this adapter with
`build_canonical_runtime(..., enable_android_security_lab=True)`, only after
the existing active canonical Agent/database identity check. The opt-in
parameter is a host-side Python argument, not a web request field, model
instruction or persisted permission. The default is **disabled** and the
existing public portal does not expose this module.

The host's existing `CapabilityHub` owns requests and prevents replay. An
adapter's JSON response is **not** proof of live device state.

## Available operations

| Operation | Behavior | Data scope |
| --- | --- | --- |
| `status` | List capabilities and hard denials | No device |
| `simulate_authentication` | Synthetic local authentication check | Fixed fictional credentials |
| `export_synthetic_messages` | Return three demonstration records | No real messages |
| `inspect_device_report` | Validate a manually supplied whitelisted security report | No contacts, numbers, messages or photo paths |
| `triage_apk` | SHA256, ZIP bounds, optional cleartext Manifest permission hints | User-supplied base64 APK, never installed or executed |

Compiled Android binary manifests are **not decoded**. A complete commercial
APK security assessment requires additional tooling and consented owner
workflow. No external network request, location, read-SMS API, photo reader,
device enrollment or remote control is implemented here.

## Trust and deployment boundaries

- The existing Termux folder `~/android_defense_lab/` is **not** remotely
  mounted or exposed to public ChatGPT users by this PR.
- Device security reports must be supplied by an authenticated operator through
  an approved private host workflow. Do not store private device records in Git.
- Host enrollment, route integration, staging CI, deployment and live checks are
  independent gates. **Repository code does not attest live activation.**
- Do not automatically run this capability when a visitor opens the bot portal.
- For complete test scope run:
  `python -m unittest tests.test_mojtaba_android_security_lab`
- Operational changes to the hosting environment require a separately
  authorized deployment and rollout procedure.

## Explicitly unsupported

Covert access; interception of WhatsApp/SMS; extraction of other people's
files or photos; surveillance; scanning other handsets; stealth installation;
remote device control without the device owner's informed authorization.
