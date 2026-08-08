# HomeCue Desktop

Tauri v2 desktop shell for the React control center in `../web`.

The native layer owns local YAML configuration, service process lifecycle, single-instance behavior, close-to-tray, and the Windows NSIS bundle. During development it launches `python -m homecue`. The Windows CI workflow builds and bundles the `homecue-service.exe` sidecar first.

```bash
npm install
npm run desktop:dev
npm run desktop:build
```

The production build is Windows-first because Corsair's SDK is Windows-only. Run the `Desktop build` GitHub Action to produce and validate the installer on `windows-latest`.
