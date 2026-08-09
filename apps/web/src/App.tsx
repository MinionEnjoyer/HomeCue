import { useEffect, useState } from "react";
import { Boxes, Check, DownloadCloud, Gauge, Home, Lightbulb, Link, Play, RotateCw, Save, Settings2, Square, Wifi } from "lucide-react";
import { checkForUpdates, defaults, getServiceStatus, installUpdate, loadInventory, loadSettings, pairHomeAssistant, saveSettings, startService, stopService, type AppUpdate, type Inventory, type ServiceStatus, type Settings } from "./bridge";

type Tab = "overview" | "devices" | "settings";

const Field = ({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) => (
  <label className="field"><span>{label}</span>{children}{hint && <small>{hint}</small>}</label>
);

const formatPairingCode = (value: string) => value.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 16).match(/.{1,4}/g)?.join("-") ?? "";

export default function App() {
  const [tab, setTab] = useState<Tab>("overview");
  const [settings, setSettings] = useState<Settings>(defaults);
  const [status, setStatus] = useState<ServiceStatus>({ running: false, pid: null, message: "Checking…" });
  const [inventory, setInventory] = useState<Inventory>({ connected: false, count: 0, devices: [] });
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [companionUrl, setCompanionUrl] = useState("http://homeassistant.local:8098");
  const [pairingCode, setPairingCode] = useState("");
  const [appUpdate, setAppUpdate] = useState<AppUpdate | null>(null);

  useEffect(() => { void Promise.all([loadSettings().then(setSettings), refresh(), checkForUpdates().then(setAppUpdate).catch(() => null)]); }, []);
  useEffect(() => { const id = window.setInterval(() => void refresh(), 4000); return () => clearInterval(id); }, []);
  useEffect(() => { if (!notice) return; const id = window.setTimeout(() => setNotice(""), 3200); return () => window.clearTimeout(id); }, [notice]);
  const refresh = async () => { try { const [nextStatus, nextInventory] = await Promise.all([getServiceStatus(), loadInventory()]); setStatus(nextStatus); setInventory(nextInventory); } catch (e) { setStatus({ running: false, pid: null, message: String(e) }); } };
  const update = <K extends keyof Settings>(key: K, value: Settings[K]) => setSettings(s => ({ ...s, [key]: value }));
  const persist = async () => { setBusy(true); try { await saveSettings(settings); setNotice("Settings saved"); } catch (e) { setNotice(String(e)); } finally { setBusy(false); } };
  const refreshDevices = async () => { setBusy(true); try { await refresh(); setNotice("Device scan refreshed"); } finally { setBusy(false); } };
  const toggleService = async () => { setBusy(true); try { setStatus(status.running ? await stopService() : await startService()); } catch (e) { setNotice(String(e)); } finally { setBusy(false); } };
  const pair = async () => { setBusy(true); try { const next = await pairHomeAssistant(companionUrl, pairingCode); setSettings(next); const started = await startService(); setStatus(started); setPairingCode(""); setNotice("HomeCue is paired and running"); } catch (e) { setNotice(`Setup failed: ${String(e)}`); } finally { setBusy(false); } };
  const checkUpdates = async () => { setBusy(true); setNotice("Checking for updates…"); try { const next = await checkForUpdates(); setAppUpdate(next); setNotice(next ? `HomeCue ${next.version} is available` : "HomeCue is up to date"); } catch (e) { setNotice(`Update check failed: ${String(e)}`); } finally { setBusy(false); } };
  const updateApp = async () => { setBusy(true); setNotice("Downloading the update…"); try { await installUpdate(); } catch (e) { setNotice(String(e)); setBusy(false); } };

  return <div className="shell">
    <aside>
      <div className="brand"><div className="brand-mark"><Lightbulb size={22}/></div><div><strong>HomeCue</strong><span>RGB bridge</span></div></div>
      <nav>
        <button className={tab === "overview" ? "active" : ""} onClick={() => setTab("overview")}><Home size={18}/>Overview</button>
        <button className={tab === "devices" ? "active" : ""} onClick={() => setTab("devices")}><Boxes size={18}/>Devices</button>
        <button className={tab === "settings" ? "active" : ""} onClick={() => setTab("settings")}><Settings2 size={18}/>Settings</button>
      </nav>
      <div className="sidebar-status"><i className={status.running ? "online" : ""}/><div><strong>{status.running ? "Service online" : "Service stopped"}</strong><span>{status.pid ? `PID ${status.pid}` : status.message}</span></div></div>
    </aside>
    <main>
      <header><div><p>DESKTOP CONTROL CENTER</p><h1>{tab === "overview" ? "Your lighting, in sync." : tab === "devices" ? "iCUE devices" : "Settings"}</h1></div>{tab === "settings" && <button className="primary" disabled={busy} onClick={persist}><Save size={17}/>{busy ? "Working…" : "Save changes"}</button>}</header>
      {notice && <div className="notice"><Check size={16}/>{notice}</div>}
      {tab === "overview" && <>
        {appUpdate && <section className="update-card"><div><DownloadCloud size={20}/><div><strong>HomeCue {appUpdate.version} is ready</strong><span>{appUpdate.notes || "A signed Windows update is available."}</span></div></div><button className="primary" disabled={busy} onClick={updateApp}>Install and restart</button></section>}
        {!status.running && <section className="panel quick-setup"><div className="panel-title"><div className="icon cyan"><Link/></div><div><h2>Connect HomeCue</h2><p>Enter the one-time code from the HomeCue Companion in Home Assistant.</p></div></div><div className="code-setup"><Field label="Pairing code"><input className="pairing-code" autoFocus autoComplete="one-time-code" inputMode="text" maxLength={19} placeholder="XXXX-XXXX-XXXX-XXXX" value={pairingCode} onChange={e => setPairingCode(formatPairingCode(e.target.value))}/></Field><button className="primary" disabled={busy || pairingCode.replace(/-/g, "").length !== 16} onClick={pair}><Play size={16}/>{busy ? "Starting…" : "Connect and start"}</button></div><small className="setup-hint">HomeCue configures MQTT and starts automatically. Advanced connection options are in Settings.</small></section>}
        <section className="service-card"><div><span className={`service-dot ${status.running ? "online" : ""}`}/><div><h2>{status.running ? "HomeCue is running" : "HomeCue is stopped"}</h2><p>{status.running ? `Connected process${status.pid ? ` · PID ${status.pid}` : ""}` : status.message}</p></div></div><div className="actions"><button className={status.running ? "danger" : "primary"} onClick={toggleService} disabled={busy}>{status.running ? <><Square size={16}/>Stop</> : <><Play size={16}/>Start</>}</button><button className="secondary" aria-label="Refresh status" onClick={refresh}><RotateCw size={16}/></button></div></section>
        <section className="cards">
          <article><div className="icon cyan"><Wifi/></div><span>MQTT broker</span><strong>{settings.mqttHost}:{settings.mqttPort}</strong><small>{settings.mqttUsername ? `Signed in as ${settings.mqttUsername}` : "Anonymous connection"}</small></article>
          <article><div className="icon violet"><Home/></div><span>Home Assistant</span><strong>{settings.haToken ? "Configured" : "Needs token"}</strong><small>{settings.haUrl}</small></article>
          <article><div className="icon amber"><Gauge/></div><span>Effects engine</span><strong>{settings.effectsFps} FPS</strong><small>Polling every {settings.pollInterval}s</small></article>
        </section>
      </>}
      {tab === "devices" && <section className="panel wide"><div className="panel-title device-title"><div className="icon cyan"><Boxes/></div><div><h2>{inventory.count} detected device{inventory.count === 1 ? "" : "s"}</h2><p>{inventory.connected ? `Grouped in Home Assistant under ${settings.suggestedArea}.` : "Start HomeCue to refresh the iCUE inventory."}</p></div><button className="secondary" disabled={busy} onClick={refreshDevices}><RotateCw size={16}/>{busy ? "Scanning…" : "Scan for devices"}</button></div><div className="device-list">{inventory.devices.length === 0 ? <p className="empty">No devices reported yet. Confirm iCUE is running with SDK access enabled, then scan again.</p> : inventory.devices.map(device => <article key={device.id}><div><strong>{device.name}</strong><small>{device.model} · {device.type}</small></div><div className="device-meta"><span>{device.ledCount} LEDs</span>{device.capabilities.map(capability => <span key={capability}>{capability}</span>)}</div></article>)}</div></section>}
      {tab === "settings" && <><section className="panel update-settings"><div className="panel-title"><div className="icon cyan"><DownloadCloud/></div><div><h2>App updates</h2><p>Check for a signed HomeCue Windows update without restarting the client.</p></div></div><div className="settings-action"><div><strong>{appUpdate ? `HomeCue ${appUpdate.version} is available` : "Keep HomeCue current"}</strong><small>{appUpdate?.notes || "Updates are downloaded only when you choose to install them."}</small></div>{appUpdate ? <button className="primary" disabled={busy} onClick={updateApp}>Install and restart</button> : <button className="secondary" disabled={busy} onClick={checkUpdates}><RotateCw size={16}/>{busy ? "Checking…" : "Check for updates"}</button>}</div></section><section className="panel setup-panel"><div className="panel-title"><div className="icon cyan"><Link/></div><div><h2>Companion address</h2><p>Change this only if Home Assistant is not available at its default local address.</p></div></div><div className="form"><Field label="HomeCue Companion URL"><input type="url" value={companionUrl} onChange={e => setCompanionUrl(e.target.value)}/></Field></div></section><div className="section-label">Manual connection</div><section className="panel-grid">
        <article className="panel"><div className="panel-title"><div className="icon cyan"><Wifi/></div><div><h2>MQTT broker</h2><p>Home Assistant discovery and device state transport.</p></div></div><div className="form two"><Field label="Host"><input value={settings.mqttHost} onChange={e => update("mqttHost", e.target.value)}/></Field><Field label="Port"><input type="number" value={settings.mqttPort} onChange={e => update("mqttPort", Number(e.target.value))}/></Field><Field label="Username"><input autoComplete="username" value={settings.mqttUsername} onChange={e => update("mqttUsername", e.target.value)}/></Field><Field label="Password"><input type="password" autoComplete="current-password" value={settings.mqttPassword} onChange={e => update("mqttPassword", e.target.value)}/></Field><Field label="Discovery prefix"><input value={settings.discoveryPrefix} onChange={e => update("discoveryPrefix", e.target.value)}/></Field></div></article>
        <article className="panel"><div className="panel-title"><div className="icon violet"><Home/></div><div><h2>Home Assistant</h2><p>Optional direct synchronization for associated lights.</p></div></div><div className="form"><Field label="Server URL"><input type="url" value={settings.haUrl} onChange={e => update("haUrl", e.target.value)}/></Field><Field label="Long-lived access token" hint="Stored in your local HomeCue configuration."><input type="password" value={settings.haToken} onChange={e => update("haToken", e.target.value)}/></Field></div></article>
      </section><section className="panel wide runtime-settings"><div className="panel-title"><div className="icon amber"><Settings2/></div><div><h2>Service runtime</h2><p>Tune iCUE discovery and Home Assistant behavior.</p></div></div><div className="form two"><Field label="Home Assistant area"><input value={settings.suggestedArea} onChange={e => update("suggestedArea", e.target.value)}/></Field><Field label="Profiles folder"><input value={settings.profilesPath} placeholder="C:\\ProgramData\\Corsair\\..." onChange={e => update("profilesPath", e.target.value)}/></Field><Field label="Polling interval (seconds)"><input type="number" min="0.1" step="0.1" value={settings.pollInterval} onChange={e => update("pollInterval", Number(e.target.value))}/></Field><Field label="Effects frame rate"><input type="number" min="1" max="120" value={settings.effectsFps} onChange={e => update("effectsFps", Number(e.target.value))}/></Field><Field label="Log level"><select value={settings.logLevel} onChange={e => update("logLevel", e.target.value)}><option>DEBUG</option><option>INFO</option><option>WARNING</option><option>ERROR</option></select></Field><label className="toggle-row"><div><strong>Exclusive SDK access</strong><small>Let HomeCue take direct control of iCUE lighting.</small></div><input type="checkbox" checked={settings.exclusiveAccess} onChange={e => update("exclusiveAccess", e.target.checked)}/><span/></label><label className="toggle-row"><div><strong>Independent LED entities</strong><small>Advanced: create one HA light per physical LED.</small></div><input type="checkbox" checked={settings.exposeIndividualLeds} onChange={e => update("exposeIndividualLeds", e.target.checked)}/><span/></label></div></section></>}
    </main>
  </div>;
}
