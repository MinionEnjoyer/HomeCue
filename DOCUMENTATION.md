# HomeCue Documentation

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Home Assistant Integration](#home-assistant-integration)
- [MQTT Protocol Reference](#mqtt-protocol-reference)
- [Effects](#effects)
- [Profile Switching](#profile-switching)
- [Supported Devices](#supported-devices)
- [Troubleshooting](#troubleshooting)
- [Development](#development)
- [API Reference](#api-reference)

---

## Overview

HomeCue is a Python service that bridges Corsair iCUE RGB lighting to Home Assistant via MQTT. It runs on your Windows PC alongside iCUE, discovers all Corsair RGB devices through the official iCUE SDK, and exposes them as native Home Assistant light entities through MQTT auto-discovery.

### What It Does

- Discovers all Corsair RGB devices managed by iCUE (fans, keyboards, mice, RAM, coolers, LED strips, etc.)
- Publishes each device as a Home Assistant light entity with full color, brightness, and effect support
- Receives commands from Home Assistant and applies them to your hardware in real time
- Runs animated lighting effects (breathing, rainbow, color cycle) directly on the hardware
- Coexists with iCUE — your fan curves, pump settings, and other iCUE features remain unaffected

### How It Works

```
┌──────────────────────────────────────────────┐
│               Windows PC                      │
│                                               │
│  iCUE (running normally)                      │
│    ↕ (iCUE SDK - shared memory)               │
│  HomeCue Service (Python)                     │
│    • Discovers devices via cuesdk             │
│    • Publishes to HA via MQTT auto-discovery  │
│    • Receives commands, sets LED colors       │
│    • Runs animated effects                    │
└──────────────┬────────────────────────────────┘
               │ Local Network
┌──────────────▼────────────────────────────────┐
│         Home Assistant (HAOS)                  │
│  • Auto-discovers light entities via MQTT     │
│  • Full color picker, brightness, effects     │
│  • Automations, scenes, dashboards            │
│  • Voice control via Alexa/Google/Siri        │
└───────────────────────────────────────────────┘
```

---

## Architecture

HomeCue is composed of five main components:

### Component Diagram

```
__main__.py (CLI entry point)
    └── HomeCueService (core.py) — orchestrator
            ├── IcueBridge (icue/bridge.py) — iCUE SDK wrapper
            │       └── CorsairDevice (icue/devices.py) — device data model
            ├── MqttClient (mqtt/client.py) — MQTT connection manager
            │       └── HaDiscovery (mqtt/discovery.py) — HA auto-discovery
            └── EffectsEngine (effects/engine.py) — animated effects
```

### Threading Model

HomeCue uses four threads:

| Thread | Owner | Purpose |
|--------|-------|---------|
| Main | `HomeCueService.run()` | Main loop: periodic state publishing, signal handling |
| MQTT | `paho-mqtt loop_start()` | Network I/O, incoming command callbacks |
| Effects | `EffectsEngine._run_loop()` | Animate lighting effects at configurable FPS |
| SDK | `cuesdk` internal | iCUE connection state and device event callbacks |

Thread safety is managed through `threading.Lock` on shared device state.

### Data Flow

**Command flow (HA to hardware):**
```
HA Dashboard → MQTT → MqttClient → HomeCueService._handle_command()
    → CorsairDevice.update_from_command()
    → EffectsEngine.set_effect() or IcueBridge.set_device_color()
    → cuesdk → Corsair hardware
```

**State flow (hardware to HA):**
```
HomeCueService main loop (every 5s)
    → HaDiscovery.publish_state()
    → MQTT (retained)
    → HA UI updates
```

---

## Requirements

### Windows PC (where HomeCue runs)

- **Python 3.9 or later**
- **Corsair iCUE 4.31 or later** — must be running
- **iCUE SDK enabled** — Settings > General > Enable SDK
- **Visual C++ Redistributable** (usually already installed)
- **Network access** to your MQTT broker / Home Assistant

### Home Assistant

- **MQTT integration** configured and connected to a broker
- **Mosquitto broker** (or any MQTT broker) running and reachable from the Windows PC

### Important Notes

- HomeCue and iCUE must run at the **same privilege level** (both as a regular user or both as admin)
- The iCUE SDK only works **locally** — HomeCue must run on the same machine as iCUE
- Remote Desktop (RDP) or Win+L may temporarily disconnect the SDK session; it will auto-reconnect

---

## Installation

### Automated Setup (Recommended)

The easiest way to install on Windows is the included setup script:

```powershell
# Clone the repository
git clone https://github.com/MinionEnjoyer/HomeCue.git
cd HomeCue

# Run the setup script
powershell -ExecutionPolicy Bypass -File setup.ps1
```

The setup script will:

1. **Verify Python 3.9+** is installed and on PATH
2. **Check that iCUE is running** (with a warning if not)
3. **Create a virtual environment** and install HomeCue + dependencies
4. **Walk you through configuration** — prompts for MQTT broker IP, port, credentials, and preferences, then generates `config.yaml`
5. **Optionally register a startup task** so HomeCue runs automatically when you log into Windows (via Task Scheduler)

### Manual Installation

If you prefer to set things up manually:

```bash
# Clone the repository
git clone https://github.com/MinionEnjoyer/HomeCue.git
cd HomeCue

# Install in a virtual environment (recommended)
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate  # macOS/Linux (for development only)

# Install HomeCue and its dependencies
pip install -e .

# Create your config
cp config.example.yaml config.yaml
# Edit config.yaml with your MQTT broker details
```

### Dependencies

Installed automatically by pip:

| Package | Purpose |
|---------|---------|
| `cuesdk` | Official Corsair iCUE SDK Python bindings |
| `paho-mqtt` | MQTT client library |
| `pyyaml` | Configuration file parsing |

---

## Configuration

HomeCue uses a YAML configuration file. Copy the example and edit it:

```bash
cp config.example.yaml config.yaml
```

### Full Configuration Reference

```yaml
# MQTT broker connection settings
mqtt:
  host: "192.168.1.100"          # IP/hostname of your MQTT broker
  port: 1883                      # MQTT port (default: 1883)
  username: "mqtt_user"           # Optional: MQTT username
  password: "mqtt_password"       # Optional: MQTT password
  discovery_prefix: "homeassistant"  # HA MQTT discovery prefix
  client_id: "homecue"           # MQTT client ID

# State publishing interval in seconds
poll_interval: 5.0

# Effects animation frame rate (higher = smoother, more CPU)
effects_fps: 30

# Request exclusive lighting control from iCUE.
#   false (default): HomeCue coexists with iCUE lighting profiles.
#                     iCUE's profiles will still show unless HomeCue
#                     actively sets colors.
#   true:            HomeCue takes full control of lighting.
#                     iCUE profiles are suppressed while HomeCue runs.
exclusive_access: false

# Logging level: DEBUG, INFO, WARNING, ERROR
log_level: "INFO"

# Override device names as they appear in Home Assistant.
# Keys are the iCUE device model names (as shown in iCUE),
# values are your preferred display names.
device_names:
  "CORSAIR iCUE LINK QX RGB Fan": "Top Case Fan"
  "CORSAIR K70 RGB PRO": "Gaming Keyboard"
```

### Minimal Configuration

At minimum, you need to configure the MQTT broker host:

```yaml
mqtt:
  host: "192.168.1.100"
```

Everything else has sensible defaults.

---

## Usage

### Running HomeCue

```bash
# Using the installed command
homecue

# Or as a Python module
python -m homecue

# With a custom config path
homecue --config /path/to/config.yaml

# Check version
homecue --version
```

### What Happens on Startup

1. Loads configuration from `config.yaml` (or defaults)
2. Connects to iCUE via the SDK
3. Connects to the MQTT broker
4. Starts the effects animation engine
5. Discovers all Corsair RGB devices
6. Publishes MQTT discovery configs (HA auto-creates light entities)
7. Subscribes to command topics for each device
8. Enters the main loop (publishes state every `poll_interval` seconds)

### Stopping HomeCue

Press `Ctrl+C` or send `SIGTERM`. HomeCue will:

1. Stop the effects engine
2. Remove all HA discovery entries (entities disappear from HA)
3. Publish "offline" availability
4. Disconnect from MQTT and iCUE

### Running at Startup (Windows)

To run HomeCue automatically when Windows starts:

1. **Task Scheduler (recommended):**
   - Open Task Scheduler
   - Create a new task
   - Trigger: "At log on"
   - Action: Start a program
     - Program: `C:\path\to\venv\Scripts\homecue.exe`
     - Start in: `C:\path\to\HomeCue\`
   - Conditions: uncheck "Start only if on AC power"

2. **Startup folder (simple):**
   - Create a shortcut to `homecue.exe` or a batch file
   - Place it in `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup`

---

## Home Assistant Integration

### Prerequisites

1. **MQTT broker** running (e.g., Mosquitto add-on in HAOS)
2. **MQTT integration** configured in HA (Settings > Devices & Services > MQTT)

### How Discovery Works

When HomeCue starts, it publishes MQTT discovery messages that Home Assistant automatically picks up. Each Corsair device appears as a **light entity** with:

- **On/Off** control
- **Brightness** slider (0-255)
- **RGB color** picker
- **Effects** dropdown (Static, Breathing, Rainbow, Color Cycle)

### Entity Naming

Entities appear in HA as `light.homecue_<hash>` where `<hash>` is derived from the iCUE device ID. The friendly name comes from iCUE's device model name (or your `device_names` override in config).

### Using in Automations

```yaml
# Example: Turn PC lights red when security alarm triggers
automation:
  - alias: "PC lights red on alarm"
    trigger:
      - platform: state
        entity_id: alarm_control_panel.home
        to: "triggered"
    action:
      - service: light.turn_on
        target:
          entity_id: light.homecue_a1b2c3d4
        data:
          rgb_color: [255, 0, 0]
          brightness: 255
          effect: "Breathing"
```

```yaml
# Example: Rainbow effect when someone comes home
automation:
  - alias: "Welcome home lights"
    trigger:
      - platform: state
        entity_id: person.john
        to: "home"
    action:
      - service: light.turn_on
        target:
          entity_id:
            - light.homecue_a1b2c3d4
            - light.homecue_e5f6g7h8
        data:
          effect: "Rainbow"
          brightness: 200
```

### Using in Scenes

```yaml
scene:
  - name: "Gaming Mode"
    entities:
      light.homecue_a1b2c3d4:
        state: "on"
        brightness: 255
        rgb_color: [255, 0, 128]
        effect: "Static"
      light.homecue_e5f6g7h8:
        state: "on"
        brightness: 200
        effect: "Color Cycle"
```

### Device Grouping

All HomeCue devices appear under the "Corsair" manufacturer in the HA device registry. You can create HA light groups to control multiple devices together:

```yaml
# configuration.yaml
light:
  - platform: group
    name: "All PC Lights"
    entities:
      - light.homecue_a1b2c3d4
      - light.homecue_e5f6g7h8
```

---

## MQTT Protocol Reference

### Topic Structure

| Purpose | Topic Pattern | Direction |
|---------|--------------|-----------|
| Discovery config | `homeassistant/light/{unique_id}/config` | HomeCue → Broker |
| Service availability | `homecue/availability` | HomeCue → Broker |
| Device state | `homecue/{unique_id}/state` | HomeCue → Broker |
| Device commands | `homecue/{unique_id}/set` | Broker → HomeCue |

### Discovery Config Payload

Published once per device on startup (retained, QoS 1):

```json
{
  "name": "CORSAIR K70 RGB PRO",
  "unique_id": "homecue_a1b2c3d4",
  "schema": "json",
  "command_topic": "homecue/homecue_a1b2c3d4/set",
  "state_topic": "homecue/homecue_a1b2c3d4/state",
  "availability": {
    "topic": "homecue/availability",
    "payload_available": "online",
    "payload_not_available": "offline"
  },
  "supported_color_modes": ["rgb"],
  "brightness": true,
  "brightness_scale": 255,
  "effect": true,
  "effect_list": ["Static", "Breathing", "Rainbow", "Color Cycle"],
  "device": {
    "identifiers": ["homecue_a1b2c3d4"],
    "name": "CORSAIR K70 RGB PRO",
    "manufacturer": "Corsair",
    "model": "Keyboard (104 LEDs)",
    "sw_version": "0.1.0",
    "via_device": "homecue"
  }
}
```

### State Payload

Published periodically and after every command (retained):

```json
{
  "state": "ON",
  "brightness": 255,
  "color_mode": "rgb",
  "color": {
    "r": 255,
    "g": 0,
    "b": 128
  },
  "effect": "Static"
}
```

### Command Payload

Sent by Home Assistant (QoS 1). Only changed fields are included:

```json
{
  "state": "ON",
  "brightness": 200,
  "color": {
    "r": 0,
    "g": 255,
    "b": 0
  },
  "effect": "Rainbow"
}
```

### Availability

- **Last Will and Testament (LWT):** If HomeCue disconnects unexpectedly, the broker automatically publishes `"offline"` to `homecue/availability`
- **On connect:** HomeCue publishes `"online"` to the same topic
- **On clean shutdown:** HomeCue publishes `"offline"` before disconnecting

---

## Effects

HomeCue includes built-in lighting effects that run locally on the Windows PC:

| Effect | Description | Behavior |
|--------|-------------|----------|
| **Static** | Solid color | Sets the chosen color immediately. No animation thread. |
| **Breathing** | Pulsing intensity | Sinusoidal brightness curve over a 4-second cycle using the current color. |
| **Rainbow** | Full spectrum rotation | Cycles through HSV hue space over a 5-second period. Ignores the set color. |
| **Color Cycle** | Step through preset colors | Transitions between red, orange, yellow, green, blue, and purple. 2 seconds per step. |

### How Effects Interact with Color and Brightness

- **Static:** Uses the exact RGB color and brightness you set
- **Breathing:** Uses your chosen color, modulates brightness sinusoidally
- **Rainbow:** Ignores your chosen color, uses brightness to scale the rainbow
- **Color Cycle:** Ignores your chosen color, uses brightness to scale preset colors

### Effects FPS

The `effects_fps` config controls animation smoothness. Default is 30 FPS, which provides smooth animation without excessive CPU usage. Lower values (15) save CPU; higher values (60) give smoother transitions.

---

## Profile Switching

HomeCue can switch between iCUE lighting profiles from Home Assistant using the Corsair Game Integration SDK (CgSDK). Profiles appear as a **select** entity (dropdown) in HA.

### How It Works

1. You create lighting profiles in iCUE as normal
2. Export them as `.cueprofile` files (Lighting Effects only)
3. Place them in the GameSdkEffects directory
4. HomeCue detects them and publishes a dropdown to HA
5. Selecting a profile in HA activates it via the CgSDK, which overlays it on top of iCUE's default profile

### Setup

1. **Enable in config** — set `profiles_path` in your `config.yaml`:

```yaml
profiles_path: "C:\\ProgramData\\Corsair\\CUE5\\GameSdkEffects\\HomeCue"
```

2. **Create the directory** (the setup script does this for you, or create it manually)

3. **Export profiles from iCUE:**
   - Open iCUE and create or select a lighting profile
   - Right-click the profile > Export
   - Select **"Lighting Effects" only** (not hardware settings)
   - Save the `.cueprofile` file to the profiles directory
   - **Important:** Use only letters, numbers, and underscores in filenames (e.g., `Gaming_Red.cueprofile`, `Cool_Blue.cueprofile`)

4. **Restart HomeCue** — it will scan the directory and publish the profiles to HA

### Using Profiles in Home Assistant

Once published, a **"iCUE Profile"** select entity appears in HA under the HomeCue device. The dropdown includes:

- **None (iCUE Default)** — deactivates any HomeCue profile, returning to iCUE's default lighting
- Each exported `.cueprofile` by name

#### In Automations

```yaml
automation:
  - alias: "Gaming mode lights"
    trigger:
      - platform: state
        entity_id: binary_sensor.gaming_pc_active
        to: "on"
    action:
      - service: select.select_option
        target:
          entity_id: select.icue_profile
        data:
          option: "Gaming_Red"
```

#### In Scenes

```yaml
scene:
  - name: "Movie Mode"
    entities:
      select.icue_profile:
        state: "Ambient_Blue"
```

### How the CgSDK Priority System Works

iCUE uses a priority-based layer system for lighting:

- iCUE's own profiles run at priority **127** (default)
- HomeCue's profiles are set to priority **128+** (displayed on top)
- When a HomeCue profile is active, it overlays iCUE's default
- When deactivated ("None"), iCUE's own profile shows through again

This means your iCUE profiles continue to exist and work — HomeCue simply layers on top when active.

### Limitations

- **Lighting only** — profile switching controls lighting effects, not fan curves or pump speeds
- **Pre-exported profiles** — profiles must be exported from iCUE and placed in the directory ahead of time
- **Profile names** — must use only `a-z`, `A-Z`, `0-9`, and `_` (no spaces or special characters)
- **CgSDK DLL required** — the `CGSDK.x64_2015.dll` must be findable (ships with iCUE, HomeCue searches common install paths)

---

## Supported Devices

HomeCue supports any RGB device that iCUE can see through its SDK. This includes:

| Category | Example Devices |
|----------|----------------|
| **Keyboards** | K70, K95, K100, STRAFE |
| **Mice** | Dark Core, Scimitar, M65, Nightsword |
| **Mousepads** | MM700, MM800 |
| **Headsets** | Void, Virtuoso (limited LED zones) |
| **Headset Stands** | ST100 |
| **Fans** | LL, QL, SP, ML, iCUE LINK QX |
| **Fan Controllers** | Commander Core, Commander Pro, iCUE LINK System Hub |
| **LED Controllers** | Lighting Node Pro, Lighting Node Core |
| **LED Strips** | Internal RGB strips |
| **Memory** | Dominator, Vengeance RGB |
| **Coolers** | H100i, H150i, iCUE LINK Titan |
| **Motherboards** | Supported ASUS/MSI boards (via iCUE plugin) |
| **GPUs** | Supported models |

### iCUE LINK

iCUE LINK devices (QX fans, Titan coolers, RX fans) are supported through the iCUE SDK. They appear as individual devices if iCUE exposes them that way, or as part of the System Hub controller.

### Per-Device vs Per-LED Control

HomeCue controls each device as a **single light entity** — all LEDs on a device share the same color. Individual LED control is not exposed to Home Assistant, as this would create hundreds of entities per device and isn't practical for smart home use.

---

## Troubleshooting

### HomeCue Can't Connect to iCUE

```
ERROR: Failed to initiate iCUE connection
ERROR: iCUE refused connection
```

**Solutions:**
1. Ensure iCUE is running
2. Enable SDK: iCUE > Settings > General > **Enable SDK**
3. Run HomeCue at the same privilege level as iCUE (both normal user or both admin)
4. Update iCUE to version 4.31 or later

### No Devices Found

```
WARNING: No Corsair devices found
```

**Solutions:**
1. Check that devices appear in iCUE's device list
2. Ensure USB connections are solid
3. For iCUE LINK: verify the System Hub is detected in iCUE
4. Try restarting iCUE

### MQTT Connection Fails

```
ERROR: Could not connect to MQTT broker
```

**Solutions:**
1. Verify your broker IP and port in `config.yaml`
2. Check that the MQTT broker is running
3. Verify credentials if using authentication
4. Ensure your Windows firewall allows outbound connections on port 1883
5. Test with: `mosquitto_pub -h <broker_ip> -t test -m hello`

### Devices Don't Appear in Home Assistant

**Solutions:**
1. Verify MQTT integration is set up in HA (Settings > Devices & Services > MQTT)
2. Check that the broker is the same one HomeCue connects to
3. Look at MQTT messages: use MQTT Explorer or HA's MQTT integration "Listen to a topic" with `homeassistant/light/#`
4. Check HomeCue logs for discovery publish confirmations

### Lights Don't Respond to HA Commands

**Solutions:**
1. Check HomeCue logs for incoming command messages (set `log_level: DEBUG`)
2. Verify the command topic format in MQTT Explorer
3. If using `exclusive_access: false`, iCUE's own profile may be overriding HomeCue's colors. Try `exclusive_access: true`

### iCUE Connection Drops

```
WARNING: iCUE connection lost, will auto-reconnect
```

This can happen when:
- iCUE restarts or updates
- You lock the screen (Win+L) or use Remote Desktop
- iCUE crashes

HomeCue will automatically reconnect when iCUE is available again.

---

## Development

### Project Structure

```
HomeCue/
├── pyproject.toml              # Build config and dependencies
├── LICENSE                     # MIT License
├── DOCUMENTATION.md            # This file
├── config.example.yaml         # Example configuration
├── homecue/
│   ├── __init__.py             # Package version
│   ├── __main__.py             # CLI entry point
│   ├── const.py                # Constants (topics, defaults, effect names)
│   ├── config.py               # YAML config loading
│   ├── core.py                 # Service orchestrator
│   ├── icue/
│   │   ├── __init__.py
│   │   ├── bridge.py           # iCUE SDK wrapper
│   │   └── devices.py          # Device data model
│   ├── mqtt/
│   │   ├── __init__.py
│   │   ├── client.py           # MQTT client with LWT
│   │   └── discovery.py        # HA MQTT auto-discovery
│   └── effects/
│       ├── __init__.py
│       └── engine.py           # Animated effects engine
```

### Setting Up for Development

```bash
git clone https://github.com/your-username/HomeCue.git
cd HomeCue
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -e .
```

### Key Design Decisions

- **No asyncio:** The iCUE SDK is synchronous/callback-based. Mixing with asyncio adds complexity for no benefit. Standard threading is used instead.
- **paho-mqtt v2 API:** Uses the modern callback signatures with `reason_code` and `properties`.
- **Shared access by default:** Lets iCUE profiles continue working. Users can opt into exclusive control.
- **One entity per device:** Individual LED control would create hundreds of entities — impractical for smart home use.
- **Brightness as RGB multiplier:** Standard HA pattern where brightness proportionally dims the chosen color.
- **Decoupled effects engine:** The effects engine knows nothing about the iCUE SDK. It receives a color-setter callback, making it testable and reusable.

---

## API Reference

### `homecue.config`

#### `load_config(path: str | Path) -> HomeCueConfig`

Load configuration from a YAML file. Returns defaults for any missing values.

#### `HomeCueConfig`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `mqtt` | `MqttConfig` | see below | MQTT broker settings |
| `poll_interval` | `float` | `5.0` | Seconds between state publishes |
| `effects_fps` | `int` | `30` | Effects animation frame rate |
| `exclusive_access` | `bool` | `False` | Request exclusive iCUE control |
| `log_level` | `str` | `"INFO"` | Logging level |
| `device_names` | `dict[str, str]` | `{}` | Model name to display name overrides |
| `profiles_path` | `str \| None` | `None` | Path to GameSdkEffects profile directory |

#### `MqttConfig`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `host` | `str` | `"localhost"` | MQTT broker hostname/IP |
| `port` | `int` | `1883` | MQTT broker port |
| `username` | `str \| None` | `None` | MQTT username |
| `password` | `str \| None` | `None` | MQTT password |
| `discovery_prefix` | `str` | `"homeassistant"` | HA discovery topic prefix |
| `client_id` | `str` | `"homecue"` | MQTT client identifier |

### `homecue.icue.devices`

#### `CorsairDevice`

Represents a Corsair RGB device.

| Property/Method | Description |
|----------------|-------------|
| `unique_id` | Stable unique ID for MQTT topics (SHA256 hash of device_id) |
| `effective_color` | RGB tuple scaled by brightness; (0,0,0) when off |
| `update_from_command(payload)` | Apply an HA JSON command to device state |
| `to_state_payload()` | Build HA JSON state dict |

### `homecue.icue.bridge`

#### `IcueBridge`

| Method | Description |
|--------|-------------|
| `connect(timeout=10.0)` | Connect to iCUE SDK. Returns `True` on success. |
| `disconnect()` | Release control and disconnect. |
| `discover_devices()` | Return list of `CorsairDevice` from iCUE. |
| `set_device_color(device_id, r, g, b)` | Set all LEDs on a device to one color. |

### `homecue.icue.profiles`

#### `ProfileManager`

| Method/Property | Description |
|----------------|-------------|
| `initialize()` | Load CgSDK DLL and register with iCUE. Returns `True` on success. |
| `available_profiles()` | List of profile names from `.cueprofile` files in the profiles directory. |
| `activate(profile_name)` | Activate a profile by name. Deactivates the current one first. |
| `deactivate()` | Deactivate the current profile, returning to iCUE's default. |
| `active_profile` | The currently active profile name, or `None`. |
| `is_initialized` | Whether the CgSDK was loaded successfully. |

### `homecue.mqtt.client`

#### `MqttClient`

| Method | Description |
|--------|-------------|
| `connect()` | Connect to broker and start network loop. |
| `disconnect()` | Publish offline and disconnect cleanly. |
| `publish(topic, payload, retain, qos)` | Publish a message (dicts auto-serialized to JSON). |
| `subscribe(topic, callback)` | Subscribe with a `(topic, payload)` callback. |

### `homecue.mqtt.discovery`

#### `HaDiscovery`

| Method | Description |
|--------|-------------|
| `publish_discovery(device)` | Publish HA auto-discovery config for a device. |
| `remove_discovery(device)` | Remove a device from HA (empty retained message). |
| `publish_state(device)` | Publish current device state to HA. |
| `subscribe_commands(device, callback)` | Subscribe to HA commands for a device. |
| `publish_profile_select(profiles)` | Publish HA select entity for profile switching. |
| `remove_profile_select()` | Remove the profile select entity from HA. |
| `publish_profile_state(active_profile)` | Publish the currently active profile name. |
| `subscribe_profile_commands(callback)` | Subscribe to profile selection commands. |

### `homecue.effects.engine`

#### `EffectsEngine`

| Method | Description |
|--------|-------------|
| `start()` | Start the background animation thread. |
| `stop()` | Stop the animation thread. |
| `set_effect(device_id, effect_name, r, g, b, brightness)` | Set or change the active effect on a device. |
| `stop_effect(device_id)` | Stop effects on a device and set to black. |
| `has_active_effect(device_id)` | Check if a device has a running animated effect. |

### `homecue.core`

#### `HomeCueService`

| Method | Description |
|--------|-------------|
| `run()` | Start all components and enter the main loop. Blocks until shutdown. |
| `shutdown()` | Gracefully stop all components, remove HA entities, disconnect. |
