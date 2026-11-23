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
| `training_lessons` | Return four Persian educational lessons | Hard-coded training descriptions only |
| `training_case` | Compute a score over one of four synthetic event sets | No device logs or captured data |
| `training_quiz` | Present or score a three-choice training question | Fixed answer key and explanations only |

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

## Offline training walkthrough (owner-only)

The host must authenticate the canonical owner and authorize each operation.
The adapter is still disabled on live sites until the approved deployment and
host registration occur. No public access is added by this change.

1. Call `training_lessons` to enumerate the three Persian lessons.
2. Call `training_case` with `{"case_id":"overprivileged_app"}` to inspect a fictional app asking for SMS, accessibility and overlay capabilities. Its training score is high; this is **not** proof of malware.
3. Repeat with `{"case_id":"normal_notes"}` and `{"case_id":"fictional_transfer"}` to compare severity.
4. Call `training_quiz` with `{"lesson_id":"android_permissions"}` to obtain the multiple-choice question, then with `{"lesson_id":"android_permissions","choice":"B"}` to grade it.

All examples are internally hard-coded. Inputs do not accept a phone number,
IP, remote hostname, chat logs, photos or arbitrary device events. No networking,
message collection, stealth operations, real device control or file writes are
implemented. Unit tests cover invalid inputs and absence of external effects.

## Covert surveillance and intrusion detection — simulated exercise

This addition is a **defensive exercise**, not a stealth intrusion feature.
The `fictional_covert_surveillance` case contains four hard-coded fictional
indicators: unexpected privileged permission, unexplained background activity,
simulated demo media access with **no file reads**, and a simulated transfer with
**no network connection**. Only static training strings and scores are returned.

- Run `training_case` with `{"case_id":"fictional_covert_surveillance"}`.
- Present `training_quiz` with `{"lesson_id":"covert_surveillance_detection"}`.
- A high exercise score is not a claim of compromise on any real phone.
- This feature does not accept real phone identifiers, files, accounts or messages.
