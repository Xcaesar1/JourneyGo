# Mobile Live Preview

Use this mode for visual changes. Do not deploy for each CSS adjustment.

1. Connect and authorize the Android phone: `adb devices -l`.
2. Start `npm --prefix frontend run dev:mobile` from the repository root.
3. Run `adb -s <device> reverse tcp:5173 tcp:5173`.
4. Open `http://127.0.0.1:5173` in phone Chrome. Keep the USB connection and
   development server running. Vue/CSS changes update through Vite HMR.
5. Inspect desktop layout at the same URL on the computer.

The amber preview notice identifies local mode. Homepage capabilities/settings
and empty memories are simulated. Other API requests, including generation,
quotes and saves, return an explicit preview error. No API proxy is configured;
saved runtime API endpoints/map keys are ignored in this mode. Do not add real
credentials to the preview. The staging tab remains separate for live testing.

Stop the server with Ctrl+C and remove only this forwarding rule with
`adb -s <device> reverse --remove tcp:5173` when preview is no longer needed.
Do not use `--host 0.0.0.0`; USB forwarding works with the loopback-only server.

Validate mocks with `node --test frontend/dev/mobilePreview.test.mjs`.
Normal `npm --prefix frontend run build` excludes the development banner and
mock middleware. Run tests/build once when the visual batch is approved, then
publish to staging with explicit user approval.
