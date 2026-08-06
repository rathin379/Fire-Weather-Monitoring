/*
  ================================================================================
  PROJECT: Automated Ambient Climate & Humidity Tracker
  AUTHOR:         G Venkat
  ORGANIZATION:   byteSmart
  WEBSITE:        https://bytesmart.info
  DATE:           July 2026
  VERSION:        1.0.0
  
  COPYRIGHT & LICENSE:
  Copyright (c) 2026 G Venkat. All rights reserved.
  
  TERMS OF USE & COMMERCIAL RESTRICTIONS:
  1. Personal & Educational Use: Free to use, modify, and distribute for 
     non-commercial purposes, provided this complete notice remains intact.
  2. Commercial Use & Extensions: ANY commercial use, sale, or derivative 
     extension of this software is strictly prohibited without prior written 
     permission. For commercial licensing inquiries, please contact the 
     Author and Organization at the email address listed above.
     
  This software is provided "as is", without warranty of any kind.
  ================================================================================
  
  WHAT THIS SIGNATURE PROGRAM DOES:
  This program communicates directly with a DHT11 environmental sensor to capture 
  live, real-time atmospheric data. It reads ambient room temperature (in Celsius) 
  and relative humidity percentage. The program streams this information back to 
  your computer screen via a formatted serial terminal interface while automatically 
  checking the data stream for hardware connection errors.
*/

// --- STEP 1: INCLUDE LIBRARIES ---
// The DHT library contains the underlying timing protocols needed to read the 
// specific digital pulses sent out by the DHT series sensors.
#include <DHT.h>

// --- STEP 2: GLOBAL CONFIGURATIONS & CONSTANTS ---
// 'const int' sets up unchangeable numbers. Using explicit names instead of 
// hidden numbers makes the entire code significantly easier to maintain.
const int DATA_PIN = 2;             // The digital hardware pin connected to the sensor's signal wire
const int SENSOR_TYPE = DHT11;      // Setting our specific target hardware model (DHT11)
const unsigned long DELAY_MS = 3000; // Safe data collection interval (3 seconds)

// Initialize the DHT library object using our custom configuration variables
DHT dht(DATA_PIN, SENSOR_TYPE);


// --- STEP 3: THE SETUP FUNCTION (Runs Exactly ONCE) ---

void setup() {
  
  // Initialize the USB Serial data link at a modern high-speed rate of 115200 baud
  Serial.begin(115200);
  
  // Pause code execution completely until the user opens the Serial Monitor console
  while (!Serial) {
    ; // Do nothing, wait for user connection
  }
  
  // Power Stabilization Guard: Give the hardware sensor exactly 1 second 
  // to normalize its internal voltages before asking it for data.
  delay(1000); 
  
  // Command the DHT chip interface to wake up and start its listening state
  dht.begin();
  
  // Print a stylized terminal UI header
  Serial.println(F("\n========================================"));
  Serial.println(F("    DHT11 CLIMATE STATION INITIALIZED   "));
  Serial.println(F("========================================"));
  Serial.print(F("-> Sensor Connection: Digital Pin "));
  Serial.println(DATA_PIN);
  Serial.println(F("-> Telemetry Data Status: Streaming...\n"));
}


// --- STEP 4: THE LOOP FUNCTION (Runs Forever) ---

void loop() {
  
  // Create two decimal-capable fractional containers ('float') to store our data.
  // We call the sensor functions to calculate the latest environment values.
  float humidity = dht.readHumidity();
  float temperature = dht.readTemperature();

  // --- ERROR HANDLING & SYSTEM PROTECTION ---
  // The DHT11 uses a single data wire to send complex bits. If a wire is unplugged, 
  // the calculation will fail. 'isnan()' stands for "Is Not a Number". 
  // This line reads: "If the humidity value is invalid OR the temperature value is invalid..."
  if (isnan(humidity) || isnan(temperature)) {
    
    // Print a warning message to guide the user in troubleshooting their hardware
    Serial.println(F("[ERROR] Telemetry Lost! Check your 5V, GND, and Signal jumper wires."));
    Serial.println(F("----------------------------------------"));
    
  } else {
    
    // If the data is fully valid, print a clean climate readout panel to the screen
    Serial.println(F("========================================"));
    Serial.print(F("[CLIMATE REPORT] "));
    
    Serial.print(F("Temp: "));
    Serial.print(temperature, 1); // Display temperature rounded to 1 decimal place
    Serial.print(F(" °C  |  "));
    
    Serial.print(F("Humidity: "));
    Serial.print(humidity, 1);    // Display humidity percentage rounded to 1 decimal place
    Serial.println(F(" %"));
    
    Serial.println(F("========================================"));
  }

  // Hardware Rest Phase: The physical moisture-absorbing element inside the DHT11 
  // cannot shift fast enough to be read continuously. Pausing for 3 seconds keeps 
  // the data highly accurate and prevents the sensor chip from overheating.
  delay(DELAY_MS);
}