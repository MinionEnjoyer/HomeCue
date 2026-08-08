import { invoke } from "@tauri-apps/api/core";

export type Settings = {
  mqttHost: string;
  mqttPort: number;
  mqttUsername: string;
  mqttPassword: string;
  discoveryPrefix: string;
  haUrl: string;
  haToken: string;
  pollInterval: number;
  effectsFps: number;
  exclusiveAccess: boolean;
  logLevel: string;
  profilesPath: string;
};

export type ServiceStatus = { running: boolean; pid: number | null; message: string };

export const defaults: Settings = {
  mqttHost: "localhost", mqttPort: 1883, mqttUsername: "", mqttPassword: "",
  discoveryPrefix: "homeassistant", haUrl: "http://homeassistant.local:8123", haToken: "",
  pollInterval: 2, effectsFps: 30, exclusiveAccess: false, logLevel: "INFO", profilesPath: "",
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

export async function getServiceStatus(): Promise<ServiceStatus> {
  if (isTauri()) return invoke<ServiceStatus>("service_status");
  return { running: false, pid: null, message: "Browser preview" };
}

export async function startService(): Promise<ServiceStatus> {
  if (isTauri()) return invoke<ServiceStatus>("start_service");
  throw new Error("Service control is available in the desktop app.");
}

export async function stopService(): Promise<ServiceStatus> {
  if (isTauri()) return invoke<ServiceStatus>("stop_service");
  throw new Error("Service control is available in the desktop app.");
}
