import { invoke } from "@tauri-apps/api/core";
import { relaunch } from "@tauri-apps/plugin-process";
import { check, type Update } from "@tauri-apps/plugin-updater";

export type Settings = {
  mqttHost: string;
  mqttPort: number;
  mqttUsername: string;
  mqttPassword: string;
  mqttTls: boolean;
  discoveryPrefix: string;
  haUrl: string;
  haToken: string;
  pollInterval: number;
  effectsFps: number;
  exclusiveAccess: boolean;
  logLevel: string;
  profilesPath: string;
  suggestedArea: string;
  exposeIndividualLeds: boolean;
};

export type ServiceStatus = { running: boolean; pid: number | null; message: string };
export type InventoryDevice = { id: string; name: string; model: string; type: string; ledCount: number; capabilities: string[] };
export type Inventory = { connected: boolean; count: number; devices: InventoryDevice[] };
export type AppUpdate = { version: string; notes: string };

let pendingUpdate: Update | null = null;

export const defaults: Settings = {
  mqttHost: "localhost", mqttPort: 1883, mqttUsername: "", mqttPassword: "", mqttTls: false,
  discoveryPrefix: "homeassistant", haUrl: "http://homeassistant.local:8123", haToken: "",
  pollInterval: 2, effectsFps: 30, exclusiveAccess: false, logLevel: "INFO", profilesPath: "",
  suggestedArea: "HomeCue", exposeIndividualLeds: false,
};

const isTauri = () => "__TAURI_INTERNALS__" in window;

export async function loadSettings(): Promise<Settings> {
  if (isTauri()) return invoke<Settings>("load_settings");
  const saved = localStorage.getItem("homecue-preview-settings");
  return saved ? { ...defaults, ...JSON.parse(saved) } : defaults;
}

export async function saveSettings(settings: Settings): Promise<void> {
  if (isTauri()) return invoke("save_settings", { settings });
  localStorage.setItem("homecue-preview-settings", JSON.stringify(settings));
}

export async function pairHomeAssistant(companionUrl: string, pairingCode: string): Promise<Settings> {
  if (isTauri()) return invoke<Settings>("pair_home_assistant", { companionUrl, pairingCode });
  return { ...defaults, mqttHost: new URL(companionUrl.includes("://") ? companionUrl : `http://${companionUrl}`).hostname, mqttUsername: "addons", mqttPassword: "paired" };
}

export async function checkForUpdates(): Promise<AppUpdate | null> {
  if (!isTauri()) return null;
  pendingUpdate = await check({ timeout: 15_000 });
  return pendingUpdate ? { version: pendingUpdate.version, notes: pendingUpdate.body ?? "" } : null;
}

export async function installUpdate(): Promise<void> {
  if (!pendingUpdate) throw new Error("Check for an update first.");
  await pendingUpdate.downloadAndInstall();
  await relaunch();
}

export async function getServiceStatus(): Promise<ServiceStatus> {
  if (isTauri()) return invoke<ServiceStatus>("service_status");
  return { running: false, pid: null, message: "Browser preview" };
}

export async function loadInventory(): Promise<Inventory> {
  if (isTauri()) return invoke<Inventory>("load_inventory");
  return { connected: false, count: 0, devices: [] };
}

export async function startService(): Promise<ServiceStatus> {
  if (isTauri()) return invoke<ServiceStatus>("start_service");
  throw new Error("Service control is available in the desktop app.");
}

export async function stopService(): Promise<ServiceStatus> {
  if (isTauri()) return invoke<ServiceStatus>("stop_service");
  throw new Error("Service control is available in the desktop app.");
}
