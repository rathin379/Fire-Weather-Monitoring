# Edge and Arduino handoff

This folder is reserved for the Fire Weather project's Arduino sketches and physical sensor evidence.

## Current status

No Arduino sketch or hardware photograph is included in this package yet. This is intentional: the completed internship deliverable is the simulated MQTT, PostgreSQL, dashboard, and ML system. Physical Arduino hardware has not been represented as completed work.

The `images` folder is ready for photographs of the future setup, including the board, connected sensors, wiring, serial monitor, Wi-Fi/MQTT connection, and a running dashboard receiving those measurements.

## What to add later

1. Put every Arduino `.ino` sketch in this `edge` folder.
2. Add a short comment at the top of each sketch identifying its board, libraries, pin assignments, Wi-Fi requirements, MQTT broker/topic, and expected payload.
3. Put hardware photographs in `edge/images` with useful names such as `arduino_r4_wifi_wiring.jpg`.
4. Update the hardware inventory below with the exact models actually used.
5. Update the run instructions below only after the sketch has been tested.

## Hardware inventory

- Arduino board: pending
- Temperature/humidity sensor: pending
- Pressure sensor: pending
- Other sensors or modules: pending

Do not claim Arduino Uno R4 WiFi, Uno R4 Minima, or a particular sensor until that device has actually been connected and tested.

## Future run checklist

1. Install the required board package and sensor/MQTT libraries in Arduino IDE.
2. Open the selected `.ino` file and choose the exact board and port.
3. Configure Wi-Fi and MQTT values without committing private credentials.
4. Compile and upload the sketch.
5. Confirm the raw payload follows `../docs/FIRE_DATA_CONTRACT.md`.
6. Start the backend subscriber and verify the event appears in PostgreSQL and the dashboard.