<p align="center">
  <img src="apps/desktop/src-tauri/icons/icon.png" alt="HomeCue" width="120" height="120" />
</p>

# HomeCue

A Windows bridge and control center for bringing Corsair iCUE lighting into Home Assistant. HomeCue
discovers supported Corsair hardware through the iCUE SDK, publishes native Home Assistant entities
through MQTT discovery, and keeps device state, colors, effects, and profiles synchronized from one
desktop application.

The project includes a React control center, a Tauri v2 Windows client, a bundled Python service,
and a Home Assistant companion app for encrypted one-time MQTT provisioning.

<p align="center">
  <strong><a href="https://github.com/MinionEnjoyer/HomeCue/releases/latest">Download the HomeCue Windows client</a></strong>
</p>

> **Current release:** desktop and service **0.3.17**. The Windows installer is available from the
> [latest release](https://github.com/MinionEnjoyer/HomeCue/releases/latest). Versioned
> `desktop-vX.Y.Z` releases include signed in-app updates so users only need to run the installer once.

## Support

If HomeCue is useful to you, project support is available through
[Buy Me a Coffee](https://buymeacoffee.com/minionenjoyer).

## Features

- **Automatic iCUE discovery** — detects Corsair devices managed by iCUE and maintains a consolidated
  hardware inventory in the desktop control center.
- **Home Assistant MQTT discovery** — creates native light, profile, status, and inventory entities
  without hand-writing Home Assistant YAML.
- **Unified device organization** — groups discovered Corsair hardware under a configurable suggested
  Home Assistant area.
- **Lighting control** — supports color, brightness, effects, availability, and direct command handling
  from Home Assistant.
- **Independent LED control** — optionally exposes each physical LED as a separate Home Assistant light
  for advanced installations.
- **Profile synchronization** — discovers exported iCUE profiles and makes profile selection available
  through Home Assistant.
- **Associated light synchronization** — maps Corsair devices to existing Home Assistant lights or light
  groups so both ecosystems can follow the same color state.
- **Windows control center** — provides a focused React interface for connections, detected devices,
  runtime tuning, and service lifecycle management.
- **System tray operation** — keeps HomeCue available in the Windows tray while the main window is hidden.
- **One-click Home Assistant setup** — pairs with the companion app using a short-lived code and imports
  the Supervisor-managed MQTT connection without manually copying credentials.
- **Signed automatic updates** — checks GitHub Releases for verified Windows updates, installs them in-app,
  and restarts HomeCue.

## Architecture

```text
Home Assistant
  HomeCue Companion app
    Supervisor MQTT service discovery
    Encrypted one-time pairing
             |
             | Local network / MQTT
             v
Windows PC
  HomeCue Tauri client
    React control center
    Bundled Python service
      iCUE SDK bridge
      MQTT discovery and state
      Effects and profile engine
             |
             v
  Corsair iCUE and connected hardware
```

HomeCue runs on the same Windows machine as iCUE. The desktop client owns configuration and service
lifecycle, while the bundled Python process communicates with the iCUE SDK and the MQTT broker. The
Home Assistant companion app is only needed for automatic provisioning; manual MQTT configuration
remains available for Home Assistant Container/Core and external brokers.

## Tech stack

- **Desktop:** Tauri v2 and Rust, packaged as a Windows NSIS installer.
- **Frontend:** React 18, TypeScript, Vite, and Lucide icons.
- **Service:** Python 3.9+, `cuesdk`, Paho MQTT, and PyYAML; frozen with PyInstaller for releases.
- **Home Assistant:** Supervisor companion app, MQTT service discovery, MQTT entity discovery, and
  optional REST synchronization.
- **Automation:** GitHub Actions for Python, React, TypeScript, Windows packaging, release signing, and
  updater metadata.

## Repository layout

```text
apps/web                    React and Vite control center
apps/desktop                Tauri v2 Windows shell and installer configuration
homecue                     Python iCUE, MQTT, effects, profiles, and synchronization service
homecue-addon               Home Assistant companion app and encrypted pairing server
tests                       Python service and companion protocol harness
.github/workflows           Quality, Windows build, and signed release pipelines
config.example.yaml         Manual service configuration reference
DOCUMENTATION.md            Detailed setup, protocol, and troubleshooting guide
repository.yaml             Home Assistant app repository metadata
```

## Windows installation

The intended user installation is the NSIS package produced by GitHub Actions. It includes the React
interface, Tauri runtime, and frozen Python service; Python and Node.js are not required on the user's
machine.

Requirements:

- Windows 10 or Windows 11.
- Corsair iCUE 4.31 or later, running with SDK access enabled.
- Network access to Home Assistant or an MQTT broker.
- HomeCue and iCUE running at the same Windows privilege level.

Development branch installers can be downloaded from the latest successful **Desktop build** workflow.
Published releases and the recommended installer are available from the
[HomeCue Windows client download](https://github.com/MinionEnjoyer/HomeCue/releases/latest).

## One-click Home Assistant setup

Home Assistant OS and Supervised installations can provide HomeCue with the active Supervisor MQTT
service automatically.

1. Add `https://github.com/MinionEnjoyer/HomeCue` as a Home Assistant app repository.
2. Install and start **HomeCue Companion**. An MQTT provider such as the Mosquitto broker app must
   already be configured.
3. Open the companion Web UI in Home Assistant and leave the one-time code visible.
4. In HomeCue for Windows, open **Connections**, enter the Home Assistant address, and select
   **Connect automatically**.
5. Enter the displayed code. HomeCue verifies and decrypts the connection bundle, saves the settings,
   and is ready to start.

The pairing code expires after ten minutes, is limited to five failed attempts per challenge, and
rotates immediately after successful use. The pairing API uses port `8098`; that port must be reachable
from the Windows computer. The code itself is only displayed through authenticated Home Assistant
ingress.

Home Assistant Container/Core installations do not support Supervisor apps. Configure the MQTT host,
port, username, and password manually from the HomeCue **Connections** screen or with
`config.example.yaml`.

## Local development

Requirements: Node.js 22+, Python 3.9+, and Rust stable with the Tauri v2 Windows prerequisites.

```bash
npm install
npm run dev
npm run desktop:dev
```

The browser preview supports interface development without Tauri or iCUE. Native service control,
tray behavior, automatic updates, and iCUE hardware access require the desktop client.

## Testing

The repository keeps service, provisioning, UI, type, and packaging checks in one harness:

```bash
python -m pytest -q
npm test
npm run typecheck
npm run build
```

The Python suite covers configuration, devices, discovery payloads, effects, inventory, CLI behavior,
the encrypted companion pairing protocol, and a hardware-free iCUE SDK contract. React tests cover
navigation, configuration, service control, consolidated inventory, automatic pairing, and the
signed-update interface. Rust unit tests cover pairing URL normalization, service status, log handling,
and safe desktop defaults.

GitHub Actions runs:

- **Quality** on every push and pull request: Python tests, React tests, TypeScript, and production web
  build.
- **Desktop build** on every branch push: frozen Python sidecar, Rust/Tauri tests, Tauri compilation,
  NSIS packaging, and a downloadable Windows installer artifact.
- **Windows release** on `desktop-vX.Y.Z` tags: signed updater artifacts, a draft GitHub Release, and
  `latest.json` for installed clients.

The native iCUE hardware loop requires a Windows machine with physical Corsair hardware and remains a
release validation step outside hosted CI.

## Signed Windows updates

HomeCue checks the latest GitHub Release at startup. When a newer signed build is available, the overview
screen offers **Install and restart**. Update bundles are verified against the public key embedded in the
client before installation.

To create a release, update the version in `apps/desktop/src-tauri/tauri.conf.json` and tag the same commit
as `desktop-vX.Y.Z`. GitHub Actions builds a draft release containing the NSIS installer, updater signature,
and metadata. Publishing the draft makes that version available to installed clients. The private signing
key exists only in the encrypted `TAURI_SIGNING_PRIVATE_KEY` repository secret.

## Documentation

Detailed configuration, MQTT topics, profile handling, effects, system tray usage, supported devices, and
troubleshooting are maintained in [DOCUMENTATION.md](DOCUMENTATION.md).
