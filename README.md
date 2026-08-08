# HomeCue

HomeCue bridges Corsair iCUE RGB hardware into Home Assistant as auto-discovered MQTT lights. The project now includes a modern React control center and a Windows Tauri desktop shell alongside the original Python service.

- Configure MQTT, Home Assistant, and runtime settings in the desktop control center.
- Start and stop the bundled HomeCue service from the app or system tray.
- Sync Home Assistant light entities with iCUE settings for an immersive experience.
- See `DOCUMENTATION.md` for service setup instructions and features.

## Modern app development

Requirements: Node.js 22+, Rust stable with the Tauri v2 Windows prerequisites, and Python 3.9+.

```bash
npm install
npm run dev             # React browser preview
npm run desktop:dev     # Tauri app + React dev server
npm test                # React component harness
python -m pytest -q     # Python service harness
```

The React app lives in `apps/web`; the Windows Tauri shell lives in `apps/desktop`. In development the shell runs the Python module from this repository. The Windows GitHub Actions build freezes that service into `homecue-service.exe` with PyInstaller and bundles it into the NSIS installer, so a production user does not need Python installed.

## Continuous integration

- `Quality` runs Python tests, React tests, TypeScript checks, and the production web build on every pull request.
- `Desktop build` creates the frozen Python sidecar and compiles the Windows NSIS package.

The native Windows/iCUE hardware loop still requires a Windows machine with iCUE and SDK access; CI verifies packaging and deterministic code paths, while hardware-in-the-loop validation remains a separate release check.

## If you found this project useful, consider supporting me here: https://buymeacoffee.com/minionenjoyer Thank you!
