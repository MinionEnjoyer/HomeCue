# HomeCue Companion

The companion gives the HomeCue Windows app one-click access to the MQTT broker already configured in Home Assistant.

1. Install and start the Mosquitto broker app (or another Supervisor MQTT provider).
2. Start HomeCue Companion and open its Web UI.
3. In HomeCue for Windows, open **Connections**, enter your Home Assistant address, and select **Automatic setup**.
4. Enter the one-time code shown in the companion Web UI.

The pairing code expires after ten minutes and rotates immediately after use. Broker credentials are returned in an encrypted response. Port 8098 must be reachable from the Windows computer during pairing.

Home Assistant Container and Core installations do not run Supervisor apps. Use HomeCue's manual MQTT fields for those installations.
