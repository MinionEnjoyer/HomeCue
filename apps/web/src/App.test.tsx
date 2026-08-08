import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { saveSettings } from "./bridge";

vi.mock("./bridge", async (loadOriginal) => {
  const original = await loadOriginal<typeof import("./bridge")>();
  return {
    ...original,
    loadSettings: vi.fn().mockResolvedValue(original.defaults),
    getServiceStatus: vi.fn().mockResolvedValue({ running: false, pid: null, message: "Ready" }),
    saveSettings: vi.fn().mockResolvedValue(undefined),
    startService: vi.fn().mockResolvedValue({ running: true, pid: 42, message: "Running" }),
    stopService: vi.fn().mockResolvedValue({ running: false, pid: null, message: "Stopped" }),
  };
});

describe("HomeCue control center", () => {
  beforeEach(() => vi.clearAllMocks());

  it("shows connection defaults and navigates to editable connection settings", async () => {
    const user = userEvent.setup();
    render(<App />);
    expect(await screen.findByText("localhost:1883")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Connections" }));
    expect(screen.getByRole("textbox", { name: "Host" })).toHaveValue("localhost");
    expect(screen.getByRole("spinbutton", { name: "Port" })).toHaveValue(1883);
  });

  it("starts the service and reports its running state", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole("button", { name: "Start" }));
    expect(await screen.findByText("Service online")).toBeVisible();
    expect(screen.getByText("PID 42")).toBeVisible();
  });

  it("edits and saves connection settings", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole("button", { name: "Connections" }));
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
    await user.click(screen.getByRole("button", { name: "Runtime" }));
    expect(screen.getByRole("spinbutton", { name: "Polling interval (seconds)" })).toHaveValue(2);
    expect(screen.getByRole("spinbutton", { name: "Effects frame rate" })).toHaveValue(30);
    expect(screen.getByRole("combobox", { name: "Log level" })).toHaveValue("INFO");
  });
});
