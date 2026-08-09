use aes_gcm::{aead::{Aead, Payload}, Aes256Gcm, KeyInit, Nonce};
use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine};
use hmac::{Hmac, Mac};
use pbkdf2::pbkdf2_hmac;
use serde::{Deserialize, Serialize};
use serde_yaml::{Mapping, Value};
use sha2::Sha256;
use std::{fs, fs::OpenOptions, path::PathBuf, process::{Child, Command, Stdio}, sync::Mutex, thread, time::Duration};
use tauri::{menu::{Menu, MenuItem}, tray::TrayIconBuilder, AppHandle, Manager, State, WindowEvent};

#[cfg(windows)]
use std::os::windows::process::CommandExt;
#[cfg(windows)]
use windows_sys::Win32::System::Threading::CREATE_NO_WINDOW;

#[derive(Default)]
struct ServiceProcess(Mutex<Option<Child>>);

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct Settings {
    mqtt_host: String,
    mqtt_port: u16,
    mqtt_username: String,
    mqtt_password: String,
    mqtt_tls: bool,
    discovery_prefix: String,
    ha_url: String,
    ha_token: String,
    poll_interval: f64,
    effects_fps: u32,
    exclusive_access: bool,
    log_level: String,
    profiles_path: String,
    suggested_area: String,
    expose_individual_leds: bool,
}

impl Default for Settings {
    fn default() -> Self { Self {
        mqtt_host: "localhost".into(), mqtt_port: 1883, mqtt_username: String::new(),
        mqtt_password: String::new(), mqtt_tls: false, discovery_prefix: "homeassistant".into(),
        ha_url: "http://homeassistant.local:8123".into(), ha_token: String::new(),
        poll_interval: 2.0, effects_fps: 30, exclusive_access: false,
        log_level: "INFO".into(), profiles_path: String::new(),
        suggested_area: "HomeCue".into(), expose_individual_leds: false,
    }}
}

#[derive(Serialize)]
struct ServiceStatus { running: bool, pid: Option<u32>, message: String }

fn config_path(app: &AppHandle) -> Result<PathBuf, String> {
    app.path().app_config_dir().map(|p| p.join("config.yaml")).map_err(|e| e.to_string())
}

fn inventory_path(app: &AppHandle) -> Result<PathBuf, String> {
    app.path().app_config_dir().map(|p| p.join("inventory.json")).map_err(|e| e.to_string())
}

#[tauri::command]
fn load_inventory(app: AppHandle) -> Result<serde_json::Value, String> {
    let path = inventory_path(&app)?;
    if !path.exists() { return Ok(serde_json::json!({"connected": false, "count": 0, "devices": []})); }
    serde_json::from_str(&fs::read_to_string(path).map_err(|e| e.to_string())?).map_err(|e| e.to_string())
}

fn map_get<'a>(map: &'a Mapping, key: &str) -> Option<&'a Value> { map.get(&Value::String(key.into())) }
fn text(map: &Mapping, key: &str, fallback: &str) -> String { map_get(map, key).and_then(Value::as_str).unwrap_or(fallback).to_owned() }

#[tauri::command]
fn load_settings(app: AppHandle) -> Result<Settings, String> {
    let path = config_path(&app)?;
    if !path.exists() { return Ok(Settings::default()); }
    let root: Mapping = serde_yaml::from_str(&fs::read_to_string(path).map_err(|e| e.to_string())?).map_err(|e| e.to_string())?;
    let mqtt = map_get(&root, "mqtt").and_then(Value::as_mapping).cloned().unwrap_or_default();
    let ha = map_get(&root, "home_assistant").and_then(Value::as_mapping).cloned().unwrap_or_default();
    let d = Settings::default();
    Ok(Settings {
        mqtt_host: text(&mqtt, "host", &d.mqtt_host),
        mqtt_port: map_get(&mqtt, "port").and_then(Value::as_u64).unwrap_or(d.mqtt_port as u64) as u16,
        mqtt_username: text(&mqtt, "username", ""), mqtt_password: text(&mqtt, "password", ""),
        mqtt_tls: map_get(&mqtt, "tls").and_then(Value::as_bool).unwrap_or(false),
        discovery_prefix: text(&mqtt, "discovery_prefix", &d.discovery_prefix),
        ha_url: text(&ha, "url", &d.ha_url), ha_token: text(&ha, "token", ""),
        poll_interval: map_get(&root, "poll_interval").and_then(Value::as_f64).unwrap_or(d.poll_interval),
        effects_fps: map_get(&root, "effects_fps").and_then(Value::as_u64).unwrap_or(d.effects_fps as u64) as u32,
        exclusive_access: map_get(&root, "exclusive_access").and_then(Value::as_bool).unwrap_or(false),
        log_level: text(&root, "log_level", &d.log_level), profiles_path: text(&root, "profiles_path", ""),
        suggested_area: text(&root, "suggested_area", &d.suggested_area),
        expose_individual_leds: map_get(&root, "expose_individual_leds").and_then(Value::as_bool).unwrap_or(false),
    })
}

#[tauri::command]
fn save_settings(app: AppHandle, settings: Settings) -> Result<(), String> {
    if settings.mqtt_host.trim().is_empty() { return Err("MQTT host is required".into()); }
    if settings.effects_fps == 0 || settings.effects_fps > 120 { return Err("Effects FPS must be between 1 and 120".into()); }
    if settings.poll_interval < 0.1 { return Err("Polling interval must be at least 0.1 seconds".into()); }
    let path = config_path(&app)?;
    if let Some(parent) = path.parent() { fs::create_dir_all(parent).map_err(|e| e.to_string())?; }
    let mut mqtt = Mapping::new();
    mqtt.insert("host".into(), settings.mqtt_host.into()); mqtt.insert("port".into(), settings.mqtt_port.into());
    if !settings.mqtt_username.is_empty() { mqtt.insert("username".into(), settings.mqtt_username.into()); }
    if !settings.mqtt_password.is_empty() { mqtt.insert("password".into(), settings.mqtt_password.into()); }
    mqtt.insert("tls".into(), settings.mqtt_tls.into());
    mqtt.insert("discovery_prefix".into(), settings.discovery_prefix.into());
    let mut root = Mapping::new(); root.insert("mqtt".into(), Value::Mapping(mqtt));
    root.insert("poll_interval".into(), settings.poll_interval.into()); root.insert("effects_fps".into(), settings.effects_fps.into());
    root.insert("exclusive_access".into(), settings.exclusive_access.into()); root.insert("log_level".into(), settings.log_level.into());
    root.insert("suggested_area".into(), settings.suggested_area.into()); root.insert("expose_individual_leds".into(), settings.expose_individual_leds.into());
    if !settings.profiles_path.is_empty() { root.insert("profiles_path".into(), settings.profiles_path.into()); }
    if !settings.ha_token.is_empty() { let mut ha = Mapping::new(); ha.insert("url".into(), settings.ha_url.into()); ha.insert("token".into(), settings.ha_token.into()); root.insert("home_assistant".into(), Value::Mapping(ha)); }
    fs::write(path, serde_yaml::to_string(&root).map_err(|e| e.to_string())?).map_err(|e| e.to_string())
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct PairingChallenge { challenge_id: String, salt: String, iterations: u32 }

#[derive(Deserialize)]
struct PairingEnvelope { nonce: String, ciphertext: String }

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct PairingBundle { mqtt_port: u16, mqtt_username: String, mqtt_password: String, mqtt_tls: bool, discovery_prefix: String }

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct PairingProof<'a> { challenge_id: &'a str, proof: String }

fn pairing_base_url(raw: &str) -> Result<url::Url, String> {
    let value = raw.trim().trim_end_matches('/');
    let normalized = if value.contains("://") { value.to_owned() } else { format!("http://{value}") };
    let mut url = url::Url::parse(&normalized).map_err(|_| "Enter a valid Home Assistant address".to_string())?;
    if url.port().is_none() || url.port() == Some(8123) { url.set_port(Some(8098)).map_err(|_| "Invalid pairing port".to_string())?; }
    Ok(url)
}

#[tauri::command]
fn pair_home_assistant(app: AppHandle, companion_url: String, pairing_code: String) -> Result<Settings, String> {
    let base = pairing_base_url(&companion_url)?;
    let client = reqwest::blocking::Client::builder().timeout(std::time::Duration::from_secs(12)).build().map_err(|e| e.to_string())?;
    let challenge: PairingChallenge = client.get(base.join("api/challenge").map_err(|e| e.to_string())?).send()
        .map_err(|_| "Could not reach the HomeCue Companion. Check its address and port 8098.".to_string())?
        .error_for_status().map_err(|e| format!("Companion rejected the request: {e}"))?.json().map_err(|e| e.to_string())?;
    let salt = URL_SAFE_NO_PAD.decode(&challenge.salt).map_err(|_| "Companion returned an invalid challenge".to_string())?;
    let code: String = pairing_code.chars().filter(|c| *c != '-' && !c.is_whitespace()).flat_map(char::to_uppercase).collect();
    let mut key = [0u8; 32];
    pbkdf2_hmac::<Sha256>(code.as_bytes(), &salt, challenge.iterations, &mut key);
    let mut mac = <Hmac<Sha256> as Mac>::new_from_slice(&key).map_err(|e| e.to_string())?;
    mac.update(challenge.challenge_id.as_bytes());
    let proof = hex::encode(mac.finalize().into_bytes());
    let response = client.post(base.join("api/pair").map_err(|e| e.to_string())?)
        .json(&PairingProof { challenge_id: &challenge.challenge_id, proof }).send().map_err(|e| e.to_string())?;
    if !response.status().is_success() { return Err("Pairing failed. Check the one-time code and try again.".into()); }
    let envelope: PairingEnvelope = response.json().map_err(|e| e.to_string())?;
    let nonce = URL_SAFE_NO_PAD.decode(envelope.nonce).map_err(|_| "Invalid pairing response".to_string())?;
    let ciphertext = URL_SAFE_NO_PAD.decode(envelope.ciphertext).map_err(|_| "Invalid pairing response".to_string())?;
    let cipher = Aes256Gcm::new_from_slice(&key).map_err(|e| e.to_string())?;
    let plaintext = cipher.decrypt(Nonce::from_slice(&nonce), Payload { msg: &ciphertext, aad: challenge.challenge_id.as_bytes() })
        .map_err(|_| "The encrypted pairing response could not be verified".to_string())?;
    let bundle: PairingBundle = serde_json::from_slice(&plaintext).map_err(|e| e.to_string())?;
    let host = base.host_str().ok_or("The companion address has no host")?.to_owned();
    let mut settings = load_settings(app.clone())?;
    settings.mqtt_host = host.clone(); settings.mqtt_port = bundle.mqtt_port;
    settings.mqtt_username = bundle.mqtt_username; settings.mqtt_password = bundle.mqtt_password;
    settings.mqtt_tls = bundle.mqtt_tls; settings.discovery_prefix = bundle.discovery_prefix;
    let scheme = if base.scheme() == "https" { "https" } else { "http" };
    settings.ha_url = format!("{scheme}://{host}:8123");
    save_settings(app, settings.clone())?;
    Ok(settings)
}

fn status_from(process: &mut Option<Child>) -> ServiceStatus {
    if let Some(child) = process.as_mut() {
        match child.try_wait() { Ok(None) => return ServiceStatus { running: true, pid: Some(child.id()), message: "HomeCue is running".into() }, Ok(Some(code)) => { *process = None; return ServiceStatus { running: false, pid: None, message: format!("Exited with {code}") }; }, Err(e) => return ServiceStatus { running: false, pid: None, message: e.to_string() } }
    }
    ServiceStatus { running: false, pid: None, message: "Ready to start".into() }
}

#[tauri::command]
fn service_status(state: State<'_, ServiceProcess>) -> Result<ServiceStatus, String> {
    let mut process = state.0.lock().map_err(|_| "Service lock poisoned")?;
    Ok(status_from(&mut process))
}

#[tauri::command]
fn start_service(app: AppHandle, state: State<'_, ServiceProcess>) -> Result<ServiceStatus, String> {
    let mut process = state.0.lock().map_err(|_| "Service lock poisoned")?;
    if status_from(&mut process).running { return Ok(status_from(&mut process)); }
    let cfg = config_path(&app)?;
    if !cfg.exists() { save_settings(app.clone(), Settings::default())?; }
    let sidecar = std::env::current_exe().ok().and_then(|p| p.parent().map(|d| d.join(if cfg!(windows) { "homecue-service.exe" } else { "homecue-service" })));
    let mut command = if let Some(binary) = sidecar.filter(|p| p.exists()) {
        Command::new(binary)
    } else {
        let mut cmd = Command::new(if cfg!(windows) { "pythonw" } else { "python3" });
        cmd.args(["-m", "homecue"]);
        cmd.current_dir(PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../.."));
        cmd
    };
    #[cfg(windows)]
    command.creation_flags(CREATE_NO_WINDOW);
    let inventory = inventory_path(&app)?;
    let log_path = cfg.with_file_name("homecue-service.log");
    let log = OpenOptions::new().create(true).append(true).open(&log_path)
        .map_err(|e| format!("Could not open the HomeCue service log: {e}"))?;
    let log_err = log.try_clone().map_err(|e| e.to_string())?;
    let mut child = command.args(["--config"]).arg(&cfg).arg("--status-file").arg(&inventory).arg("--no-pause")
        .stdin(Stdio::null()).stdout(Stdio::from(log)).stderr(Stdio::from(log_err)).spawn()
        .map_err(|e| format!("Could not start the HomeCue service: {e}"))?;
    thread::sleep(Duration::from_millis(500));
    if let Some(code) = child.try_wait().map_err(|e| e.to_string())? {
        let details = fs::read_to_string(&log_path).unwrap_or_default();
        let tail = details.lines().rev().take(8).collect::<Vec<_>>().into_iter().rev().collect::<Vec<_>>().join("\n");
        return Err(if tail.is_empty() { format!("HomeCue exited during startup with {code}") } else { format!("HomeCue could not start:\n{tail}") });
    }
    let pid = child.id(); *process = Some(child);
    Ok(ServiceStatus { running: true, pid: Some(pid), message: "HomeCue is running".into() })
}

#[tauri::command]
fn stop_service(state: State<'_, ServiceProcess>) -> Result<ServiceStatus, String> {
    let mut process = state.0.lock().map_err(|_| "Service lock poisoned")?;
    if let Some(child) = process.as_mut() { child.kill().map_err(|e| e.to_string())?; let _ = child.wait(); }
    *process = None; Ok(ServiceStatus { running: false, pid: None, message: "Stopped".into() })
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _, _| { if let Some(w) = app.get_webview_window("main") { let _ = w.show(); let _ = w.set_focus(); } }))
        .plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .manage(ServiceProcess::default())
        .invoke_handler(tauri::generate_handler![load_settings, save_settings, pair_home_assistant, load_inventory, service_status, start_service, stop_service])
        .setup(|app| {
            let open = MenuItem::with_id(app, "open", "Open HomeCue", true, None::<&str>)?;
            let quit = MenuItem::with_id(app, "quit", "Quit HomeCue", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&open, &quit])?;
            TrayIconBuilder::new().icon(app.default_window_icon().unwrap().clone()).tooltip("HomeCue").menu(&menu)
                .on_menu_event(|app, event| match event.id.as_ref() { "open" => if let Some(w) = app.get_webview_window("main") { let _ = w.show(); let _ = w.set_focus(); }, "quit" => app.exit(0), _ => {} }).build(app)?;
            Ok(())
        })
        .on_window_event(|window, event| if let WindowEvent::CloseRequested { api, .. } = event { api.prevent_close(); let _ = window.hide(); })
        .run(tauri::generate_context!()).expect("error while running HomeCue");
}
