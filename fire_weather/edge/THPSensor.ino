/*
  ================================================================================
  PROJECT:        Live Weather Station (AHT20 + BMP280)
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
     Author and Organization at the website listed above.
     
  This software is provided "as is", without warranty of any kind.
  ================================================================================
*/
/*
  ================================================================================
  ULTIMATE NEWBIE-FRIENDLY LIVE WEATHER STATION SKETCH
  ================================================================================
  What this program does:
  It reads environment data from two sensors at once using a 2-wire communication 
  highway called I2C. It reads Air Temperature and Relative Humidity from the AHT20 
  sensor, and Barometric Pressure + Altitude from the BMP280 sensor. 
  
  All of this data is sent over a USB cable back to your computer so you can 
  read it in real-time inside your Arduino IDE's Serial Monitor tool.
  ================================================================================
*/

// --- STEP 1: INCLUDE LIBRARIES (The "Instruction Manuals") ---
// Libraries are pre-written bundles of complex code that teach your Arduino 
// how to talk to specific hardware parts without you needing to program them from scratch.

#include <Wire.h>            
// The Wire library allows your Arduino to use "I2C" communication. 
// Think of I2C like a party line telephone system where multiple chips share 
// the exact same two wires to talk to the Arduino.

#include <Adafruit_BMP280.h> 
// This tells the Arduino how to interpret the raw electrical signals coming 
// from your BMP280 Barometric Pressure & Temperature chip.

#include <Adafruit_AHTX0.h>  
// This tells the Arduino how to interpret the raw signals coming 
// from your AHT20 Humidity & Temperature chip.


// --- STEP 2: CREATE INSTANCES (The "Virtual Objects") ---
// We need to give our physical sensors nicknames inside our code so we can 
// command them later. This is called creating an "object".

Adafruit_BMP280 bmp; 
// We are creating an object named 'bmp'. From now on, whenever we want to 
// talk to the pressure chip, we will use the name 'bmp'.

Adafruit_AHTX0 aht;   
// We are creating an object named 'aht'. From now on, whenever we want to
// talk to the humidity chip, we will use the name 'aht'.


// --- STEP 3: THE SETUP FUNCTION (Runs Exactly ONCE) ---
// The setup() function is where the Arduino initializes its settings. It runs 
// immediately when the board gets power or when you hit the reset button.

void setup() {
  
  // Initialize standard Serial communication at a speed of 115200 baud.
  // "Baud rate" is the speed of data transmission. Think of it like a radio 
  // frequency; both your Arduino and your computer's Serial Monitor must be 
  // set to the exact same speed (115200) otherwise the text will look like gibberish!
  Serial.begin(115200);
  
  // This 'while' loop halts the program and makes the Arduino wait until you 
  // actually click and open the Serial Monitor window on your computer. 
  // This ensures you don't miss the initial setup messages!
  while (!Serial) {
    ; // The semicolon alone means "do nothing, just keep waiting"
  }

  // The 'F()' wrapper around our text strings (like F("Text")) is a trick to save memory. 
  // It forces the text to stay in the Arduino's permanent "Flash" storage rather 
  // than taking up precious space in its temporary RAM memory.
  Serial.println(F("\n========================================"));
  Serial.println(F("   AHT20 + BMP280 Live Weather Station  "));
  Serial.println(F("========================================"));

  // --- CONNECTING TO SENSOR 1: AHT20 ---
  // We use an 'if' statement to try to start up the AHT20 sensor.
  // The '!' symbol means "NOT". So this reads: "If the aht sensor does NOT begin..."
  if (!aht.begin()) {
    Serial.println(F("Error: Could not find AHT20 sensor!"));
    // If it fails, we trap the Arduino in an infinite loop ('while(1)') so it stops completely.
    // This gives you time to check your jumper wires without the code running brokenly.
    while (1); 
  }
  // If the 'if' statement was skipped, it means the sensor woke up perfectly!
  Serial.println(F("-> AHT20 Sensor connected."));

  // --- CONNECTING TO SENSOR 2: BMP280 ---
  // Every device on an I2C highway needs its own unique digital house address. 
  // Your specific BMP280 sensor uses the hex address '0x77'. 
  // Just like before, we check if the sensor does NOT respond at that address.
  if (!bmp.begin(0x77)) {  
    Serial.println(F("Error: Could not find BMP280 sensor at 0x77!"));
    while (1); // Trap the Arduino here if wires are loose or wrong address is targeted
  }
  Serial.println(F("-> BMP280 Sensor connected."));
  Serial.println(F("\nStreaming environmental data:\n"));
}


// --- STEP 4: THE LOOP FUNCTION (Runs Forever) ---
// Once setup() finishes, the loop() function runs over and over again from top 
// to bottom at lightning speed until the board is unplugged.

void loop() {
  
  // To read data from the AHT20 sensor, the library requires special storage containers 
  // called 'sensors_event_t'. 
  // Here, we create two empty containers: one named 'humidity' and one named 'temp'.
  sensors_event_t humidity, temp;
  
  // This command tells the 'aht' object to go grab the latest real-time numbers 
  // from the physical sensor chip and pour that data directly into our empty containers.
  aht.getEvent(&humidity, &temp);

  // --- PRINTING DATA FROM THE AHT20 SENSOR ---
  
  // Print the descriptive text block
  Serial.print(F("Air Temp: "));
  
  // 'temp.temperature' extracts just the numerical temperature value out of our container.
  // The ', 1' inside the parentheses tells the Arduino to round the number to exactly 1 decimal place.
  Serial.print(temp.temperature, 1); 
  Serial.println(F(" *C")); // 'println' moves the cursor to a brand new line for the next text block

  Serial.print(F("Humidity: "));
  // 'humidity.relative_humidity' extracts just the humidity percentage out of our container.
  Serial.print(humidity.relative_humidity, 1);
  Serial.println(F(" %"));


  // --- PRINTING DATA FROM THE BMP280 SENSOR ---
  
  Serial.print(F("Barometric Pressure: "));
  
  // 'bmp.readPressure()' reads raw pressure in units called Pascals. 
  // Because weather stations use a standard unit called Hectopascals (hPa), 
  // we divide the result by 100.0. (The 'F' tells the code to treat it as a decimal fraction).
  Serial.print(bmp.readPressure() / 100.0F); 
  Serial.println(F(" hPa"));

  Serial.print(F("Approx Altitude: "));
  
  // The BMP280 can calculate your height above sea level based on air pressure changes. 
  // However, because weather constantly changes the baseline pressure, we have to pass it 
  // a baseline "Standard Sea Level Pressure" value, which is globally average at 1013.25 hPa.
  Serial.print(bmp.readAltitude(1013.25)); 
  Serial.println(F(" meters"));

  // Print a divider line so the readings are clean and easy to separate in the console window.
  Serial.println(F("----------------------------------------"));
  
  // Pause execution for 3000 milliseconds (which equals 3 full seconds).
  // Without this delay, the Arduino would spam your screen with thousands of calculations per second!
  delay(3000); 
}