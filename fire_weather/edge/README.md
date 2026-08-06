# Edge and Arduino handoff

This folder is reserved for the Fire Weather project's Arduino sketches and physical sensor evidence.

## Current status

This folder includes three sensor sketches used during the internship:

- `dht11temp.ino` reads temperature and humidity from a DHT11 sensor.
- `THPSensor.ino` reads temperature and humidity from an AHT20 and pressure/altitude from a BMP280.
- `temp_humidity-first.ino` reads temperature and humidity from a DHT11 sensor.

These sketches print readings to the Arduino Serial Monitor. They are separate from the project's simulated MQTT, PostgreSQL, dashboard, and ML pipeline.

The `images` folder is ready for photographs of the setup, including the board, connected sensors, wiring, serial monitor, Wi-Fi/MQTT connection, and a running dashboard receiving measurements.

## If more hardware files are added later

1. Put each additional Arduino `.ino` sketch in this `edge` folder.
2. Keep the library names, pin assignments, and board requirements documented in the sketch comments.
3. Put hardware photographs in `edge/images` with useful names such as `arduino_r4_wifi_wiring.jpg`.
4. Update the hardware inventory below with the exact models actually used.
5. Update the run instructions below only after a new sketch has been tested.

## Hardware inventory

- Arduino board: verify the board used with each sketch before uploading
- Temperature/humidity sensors: DHT11 and AHT20
- Pressure sensor: BMP280
- Other sensors or modules: none documented here

Do not claim a particular Arduino board until that device has actually been connected and tested.

## Run checklist

1. Install the required board package and sensor libraries in Arduino IDE.
2. Open the selected `.ino` file and choose the exact board and port.
3. Connect the sensor using the pins described in the sketch comments.
4. Compile and upload the sketch.
5. Open Serial Monitor at the baud rate used by that sketch and confirm readings appear.

These sketches currently output serial readings only; they do not publish MQTT payloads.