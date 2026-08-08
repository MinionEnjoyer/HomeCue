# HomeCue

HomeCue bridges Corsair iCUE RGB hardware into Home Assistant as auto-discovered MQTT lights. The project now includes a modern React control center and a Windows Tauri desktop shell alongside the original Python service.

- Configure MQTT, Home Assistant, and runtime settings in the desktop control center.
- Start and stop the bundled HomeCue service from the app or system tray.
- Sync Home Assistant light entities with iCUE settings for an immersive experience.
- See `DOCUMENTATION.md` for service setup instructions and features.

## One-click Home Assistant setup

Home Assistant OS and Supervised users can install the repository's **HomeCue Companion** app. The companion reads the active Supervisor MQTT service and pairs it with HomeCue for Windows without copying broker credentials by hand.

1. Add `https://github.com/MinionEnjoyer/HomeCue` as a Home Assistant app repository.
2. Install and start **HomeCue Companion**, then open its Web UI.
3. In HomeCue for Windows, open **Connections**, enter the Home Assistant address, and use the displayed one-time code.

The code expires after ten minutes, rotates after use, and the credential response is encrypted. Home Assistant Container/Core and external MQTT installations can continue to use the manual connection fields.

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

- `Quality` runs Python tests (including the encrypted pairing protocol), React tests, TypeScript checks, and the production web build on every push and pull request.
- `Desktop build` creates the frozen Python sidecar and compiles the Windows NSIS package.

The native Windows/iCUE hardware loop still requires a Windows machine with iCUE and SDK access; CI verifies packaging and deterministic code paths, while hardware-in-the-loop validation remains a separate release check.

## Signed Windows updates

Installed Windows clients check the latest GitHub release for a signed update. A `desktop-vX.Y.Z` tag matching the version in `apps/desktop/src-tauri/tauri.conf.json` builds a draft GitHub release, its NSIS updater bundle, signature, and `latest.json`. Publishing that draft makes the update available in HomeCue. The private updater key is stored only as the `TAURI_SIGNING_PRIVATE_KEY` GitHub Actions secret; its public verification key is embedded in the app.

## If you found this project useful, consider supporting me here: https://buymeacoffee.com/minionenjoyer Thank you!
