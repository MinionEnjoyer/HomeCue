import { useEffect, useState } from "react";
import { Activity, Cable, Check, Gauge, Home, Lightbulb, Play, Power, RotateCw, Save, Settings2, Square, Wifi } from "lucide-react";
import { defaults, getServiceStatus, loadSettings, saveSettings, startService, stopService, type ServiceStatus, type Settings } from "./bridge";

type Tab = "overview" | "connections" | "runtime";

const Field = ({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) => (
  <label className="field"><span>{label}</span>{children}{hint && <small>{hint}</small>}</label>
);

export default function App() {
  const [tab, setTab] = useState<Tab>("overview");
  const [settings, setSettings] = useState<Settings>(defaults);
  const [status, setStatus] = useState<ServiceStatus>({ running: false, pid: null, message: "Checking…" });
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => { void Promise.all([loadSettings().then(setSettings), refresh()]); }, []);
  useEffect(() => { const id = window.setInterval(() => void refresh(), 4000); return () => clearInterval(id); }, []);
  const refresh = async () => { try { setStatus(await getServiceStatus()); } catch (e) { setStatus({ running: false, pid: null, message: String(e) }); } };
  const update = <K extends keyof Settings>(key: K, value: Settings[K]) => setSettings(s => ({ ...s, [key]: value }));
  const persist = async () => { setBusy(true); try { await saveSettings(settings); setNotice("Settings saved"); setTimeout(() => setNotice(""), 2500); } catch (e) { setNotice(String(e)); } finally { setBusy(false); } };
  const toggleService = async () => { setBusy(true); try { setStatus(status.running ? await stopService() : await startService()); } catch (e) { setNotice(String(e)); } finally { setBusy(false); } };

  return <div className="shell">
    <aside>
      <div className="brand"><div className="brand-mark"><Lightbulb size={22}/></div><div><strong>HomeCue</strong><span>RGB bridge</span></div></div>
      <nav>
        <button className={tab === "overview" ? "active" : ""} onClick={() => setTab("overview")}><Home size={18}/>Overview</button>
        <button className={tab === "connections" ? "active" : ""} onClick={() => setTab("connections")}><Cable size={18}/>Connections</button>
        <button className={tab === "runtime" ? "active" : ""} onClick={() => setTab("runtime")}><Settings2 size={18}/>Runtime</button>
      </nav>
      <div className="sidebar-status"><i className={status.running ? "online" : ""}/><div><strong>{status.running ? "Service online" : "Service stopped"}</strong><span>{status.pid ? `PID ${status.pid}` : status.message}</span></div></div>
    </aside>
    <main>
      <header><div><p>DESKTOP CONTROL CENTER</p><h1>{tab === "overview" ? "Your lighting, in sync." : tab === "connections" ? "Connections" : "Runtime"}</h1></div><button className="primary" disabled={busy} onClick={persist}><Save size={17}/>{busy ? "Working…" : "Save changes"}</button></header>
      {notice && <div className="notice"><Check size={16}/>{notice}</div>}
      {tab === "overview" && <>
        <section className="hero"><div><span className="eyebrow"><Activity size={14}/> HOME ASSISTANT + iCUE</span><h2>One bridge.<br/><em>Every color.</em></h2><p>Control Corsair lighting from Home Assistant while HomeCue handles discovery, effects, and state sync in the background.</p><div className="actions"><button className={status.running ? "danger" : "primary"} onClick={toggleService} disabled={busy}>{status.running ? <><Square size={16}/>Stop service</> : <><Play size={16}/>Start service</>}</button><button className="secondary" onClick={refresh}><RotateCw size={16}/>Refresh</button></div></div><div className="orb"><span/><span/><Lightbulb size={52}/></div></section>
        <section className="cards">
          <article><div className="icon cyan"><Wifi/></div><span>MQTT broker</span><strong>{settings.mqttHost}:{settings.mqttPort}</strong><small>{settings.mqttUsername ? `Signed in as ${settings.mqttUsername}` : "Anonymous connection"}</small></article>
          <article><div className="icon violet"><Home/></div><span>Home Assistant</span><strong>{settings.haToken ? "Configured" : "Needs token"}</strong><small>{settings.haUrl}</small></article>
          <article><div className="icon amber"><Gauge/></div><span>Effects engine</span><strong>{settings.effectsFps} FPS</strong><small>Polling every {settings.pollInterval}s</small></article>
        </section>
      </>}
      {tab === "connections" && <section className="panel-grid">
        <article className="panel"><div className="panel-title"><div className="icon cyan"><Wifi/></div><div><h2>MQTT broker</h2><p>Home Assistant discovery and device state transport.</p></div></div><div className="form two"><Field label="Host"><input value={settings.mqttHost} onChange={e => update("mqttHost", e.target.value)}/></Field><Field label="Port"><input type="number" value={settings.mqttPort} onChange={e => update("mqttPort", Number(e.target.value))}/></Field><Field label="Username"><input autoComplete="username" value={settings.mqttUsername} onChange={e => update("mqttUsername", e.target.value)}/></Field><Field label="Password"><input type="password" autoComplete="current-password" value={settings.mqttPassword} onChange={e => update("mqttPassword", e.target.value)}/></Field><Field label="Discovery prefix"><input value={settings.discoveryPrefix} onChange={e => update("discoveryPrefix", e.target.value)}/></Field></div></article>
        <article className="panel"><div className="panel-title"><div className="icon violet"><Home/></div><div><h2>Home Assistant</h2><p>Optional direct synchronization for associated lights.</p></div></div><div className="form"><Field label="Server URL"><input type="url" value={settings.haUrl} onChange={e => update("haUrl", e.target.value)}/></Field><Field label="Long-lived access token" hint="Stored in your local HomeCue configuration."><input type="password" value={settings.haToken} onChange={e => update("haToken", e.target.value)}/></Field></div></article>
      </section>}
      {tab === "runtime" && <section className="panel wide"><div className="panel-title"><div className="icon amber"><Settings2/></div><div><h2>Service runtime</h2><p>Tune responsiveness and iCUE integration behavior.</p></div></div><div className="form two"><Field label="Polling interval (seconds)"><input type="number" min="0.1" step="0.1" value={settings.pollInterval} onChange={e => update("pollInterval", Number(e.target.value))}/></Field><Field label="Effects frame rate"><input type="number" min="1" max="120" value={settings.effectsFps} onChange={e => update("effectsFps", Number(e.target.value))}/></Field><Field label="Log level"><select value={settings.logLevel} onChange={e => update("logLevel", e.target.value)}><option>DEBUG</option><option>INFO</option><option>WARNING</option><option>ERROR</option></select></Field><Field label="Profiles folder"><input value={settings.profilesPath} placeholder="C:\\Users\\you\\Documents\\iCUE" onChange={e => update("profilesPath", e.target.value)}/></Field><label className="toggle-row"><div><strong>Exclusive SDK access</strong><small>Let HomeCue take direct control of iCUE lighting.</small></div><input type="checkbox" checked={settings.exclusiveAccess} onChange={e => update("exclusiveAccess", e.target.checked)}/><span/></label></div></section>}
    </main>
  </div>;
}
