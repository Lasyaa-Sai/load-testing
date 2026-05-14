# E2E Voice & Text Testing Harness

This repo contains a sample iOS harness for testing text and voice chat flows.
The current implementation uses:

- Maestro for UI automation
- A real iOS app target in `App/VoiceTextDemo.xcodeproj`, with shared sources under `App/Sources/VoiceTextDemo/`
- App-side audio injection and capture in `AudioManager`
- A Python runner in `harness/runner/run_tests.py`
- Semantic verification in `harness/verifier/judge.py`

## Current State

The harness is implemented, but the CI path is still being stabilized around:

- simulator app install
- first-screen launch timing
- Maestro visibility checks

So this should be treated as the current implementation snapshot, not a fully green production pipeline.

## What the code does

- Maestro launches the app and taps the text or voice controls.
- `ChatViewModel` reads launch arguments and writes a JSON case result.
- `AudioManager` injects fixture audio into the app's audio path and captures the spoken response.
- `run_tests.py` runs each case, waits for the JSON result, and sends the result to the judge.
- The judge checks expected intent plus the assistant response, and can also assert tool calls.

## Repo Layout

```text
sample_testing/e2e-voice-text-harness/
├── App/
│   ├── VoiceTextDemo.xcodeproj/
│   ├── Package.swift
│   ├── Sources/VoiceTextDemo/
│   │   ├── VoiceTextDemoApp.swift
│   │   ├── ContentView.swift
│   │   ├── ChatViewModel.swift
│   │   ├── AudioManager.swift
│   │   ├── WebSocketTranscriber.swift
│   │   └── Info.plist
│   └── Tests/AudioBridgeTests/
├── harness/
│   ├── runner/run_tests.py
│   ├── runner/test_loader.py
│   ├── runner/report.py
│   └── verifier/judge.py
├── maestro/
├── test-cases/
├── fixtures/
└── docs/
```

## How to run

From `sample_testing/e2e-voice-text-harness` on a Mac:

```bash
pip install -r requirements.txt
python harness/runner/run_tests.py --suite smoke
python harness/runner/run_tests.py --suite regression
```

Environment variables used by the harness:

- `OPENROUTER_API_KEY`
- `OPENROUTER_MODEL`
- `OPENROUTER_BASE_URL`
- `WEBSOCKET_URL`
- `MAESTRO_BIN`
- `IOS_SIMULATOR`
- `IOS_SIMULATOR_UDID`
- `MAX_RETRIES`
- `MAESTRO_TIMEOUT_S`
- `CASE_OUTPUT_TIMEOUT_S`

Reports are written to:

- `reports/report.xml`
- `reports/report.json`

## Test authoring

Cases live in YAML under `test-cases/`.

Text example:

```yaml
- id: my_text_case
  type: text
  input_text: "Hello"
  expected_intent: "Agent greets the user"
  tags: [smoke, text]
```

Voice example:

```yaml
- id: my_voice_case
  type: voice
  input_audio: fixtures/my_audio.wav
  expected_intent: "Agent handles the spoken request"
  tags: [smoke, voice]
```

## Notes for the tech lead

- The design goal is still good: declarative cases, app-side audio injection, semantic verification, and CI-friendly reporting.
- The current blocker is operational, not conceptual: the workflow still needs to be hardened around simulator packaging and first-screen launch stability.
- For the demo, Maestro is the UI driver. Audio behavior is implemented in the app, not through a separate UI-test bridge.
