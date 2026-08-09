import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { checkForUpdates, installUpdate, pairHomeAssistant, saveSettings, startService } from "./bridge";

vi.mock("./bridge", async (loadOriginal) => {
  const original = await loadOriginal<typeof import("./bridge")>();
  return {
    ...original,
    loadSettings: vi.fn().mockResolvedValue(original.defaults),
    getServiceStatus: vi.fn().mockResolvedValue({ running: false, pid: null, message: "Ready" }),
    loadInventory: vi.fn().mockResolvedValue({ connected: true, count: 1, devices: [{ id: "homecue_1", name: "Commander", model: "Commander", type: "LED Controller", ledCount: 2, capabilities: ["lighting", "individual-leds"] }] }),
    saveSettings: vi.fn().mockResolvedValue(undefined),
    pairHomeAssistant: vi.fn().mockResolvedValue({ ...original.defaults, mqttHost: "homeassistant.local", mqttUsername: "addons", mqttPassword: "paired" }),
    checkForUpdates: vi.fn().mockResolvedValue(null),
    installUpdate: vi.fn().mockResolvedValue(undefined),
    startService: vi.fn().mockResolvedValue({ running: true, pid: 42, message: "Running" }),
    stopService: vi.fn().mockResolvedValue({ running: false, pid: null, message: "Stopped" }),
  };
});

describe("HomeCue control center", () => {
  beforeEach(() => vi.clearAllMocks());

  it("keeps manual connection fields in settings", async () => {
    const user = userEvent.setup();
    render(<App />);
    expect(await screen.findByText("localhost:1883")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Settings" }));
    expect(screen.getByRole("textbox", { name: "Host" })).toHaveValue("localhost");
    expect(screen.getByRole("spinbutton", { name: "Port" })).toHaveValue(1883);
  });

  it("pairs automatically using the companion code", async () => {
    const user = userEvent.setup();
    render(<App />);
    const code = screen.getByRole("textbox", { name: "Pairing code" });
    await user.type(code, "abcdefghjklmnpqr");
    expect(code).toHaveValue("ABCD-EFGH-JKLM-NPQR");
    await user.click(screen.getByRole("button", { name: "Connect and start" }));
    expect(pairHomeAssistant).toHaveBeenCalledWith("http://homeassistant.local:8098", "ABCD-EFGH-JKLM-NPQR");
    expect(startService).toHaveBeenCalledOnce();
    expect(await screen.findByText("HomeCue is paired and running")).toBeVisible();
  });

  it("starts the service and reports its running state", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole("button", { name: "Start" }));
    expect(await screen.findByText("Service online")).toBeVisible();
    expect(screen.getByText("PID 42")).toBeVisible();
  });

  it("offers and installs a signed app update", async () => {
    vi.mocked(checkForUpdates).mockResolvedValueOnce({ version: "0.3.0", notes: "Automatic updates" });
    const user = userEvent.setup();
    render(<App />);
    expect(await screen.findByText("HomeCue 0.3.0 is ready")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Install and restart" }));
    expect(installUpdate).toHaveBeenCalledOnce();
  });

  it("edits and saves connection settings", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole("button", { name: "Settings" }));
    const host = screen.getByRole("textbox", { name: "Host" });
    await user.clear(host);
    await user.type(host, "mqtt.home");
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    expect(saveSettings).toHaveBeenCalledWith(expect.objectContaining({ mqttHost: "mqtt.home" }));
    expect(await screen.findByText("Settings saved")).toBeVisible();
  });

  it("shows the runtime controls with safe defaults", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole("button", { name: "Settings" }));
    expect(screen.getByRole("spinbutton", { name: "Polling interval (seconds)" })).toHaveValue(2);
    expect(screen.getByRole("spinbutton", { name: "Effects frame rate" })).toHaveValue(30);
    expect(screen.getByRole("combobox", { name: "Log level" })).toHaveValue("INFO");
    expect(screen.getByRole("textbox", { name: "Home Assistant area" })).toHaveValue("HomeCue");
    expect(screen.getByRole("checkbox", { name: "Independent LED entities Advanced: create one HA light per physical LED." })).not.toBeChecked();
  });

  it("shows the consolidated iCUE inventory", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole("button", { name: "Devices" }));
    expect(await screen.findByRole("heading", { name: "1 detected device" })).toBeVisible();
    expect(screen.getByText("Commander · LED Controller")).toBeVisible();
    expect(screen.getByText("2 LEDs")).toBeVisible();
  });
});
