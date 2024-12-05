// This version is for the Roomba 600 Series (and all others that have a sleep mode, including Roomba 860)
// ##################### FEATURES  #####################
//  WiFi upgrade to Roomba models with no remote features
//  MQTT Connection to issue commands, read battery information, and read current status
//  Supports Cleaning, Docking, Spot Cleaning, Max Cleaning, Playing Song(s), Halting (Power Off), and Rebooting
//  Added playable songs to indicate startup process and humor
//  Created logic for determining Roomba's current state with the SCI constraints in mind
//  Minimized the time when trying to force Roomba to stay awake (based off battery life)
//  Designed to allow for easy setup on Home Assistant
// ##################### CHANGELOG #####################
// 2023-09-20 Initial implementation of forked code from https://github.com/thehookup/MQTT-Roomba-ESP01/blob/master/Roomba_600_ESP01_CONFIGURE.ino
// 2023-09-21 Added "Docked" status when charging is detected
//            Moved/renamed "Dead Somwhere" -> "Connected" in seperate topic due to TXD/RXD constraints
//            Added additional commands for max clean, spot clean, halting, and playing music
//            Modified "keep awake" behavior based on battery level/charging status
// 2023-09-22 Added startup jingle when ESP8266 finished setup initialization
// 2023-09-27 Added more music and changed the structure due to maximum song limitations
// 2023-11-28 Fix for invalid "Docked" status handling. Innacurate charging value would cause the status
//            to be "Docked" until receiving the next command.
// 2024-12-05 Added 2 Christmas songs

#include <PubSubClient.h>
#include <ESP8266WiFi.h>
#include <ESP8266mDNS.h>
#include <SimpleTimer.h>
#include <Roomba.h>

//////////////////////////////////////////////////////////////
// USER CONFIGURED SECTION START
//////////////////////////////////////////////////////////////
const char* ssid = "YOUR_SSID";
const char* password = "YOUR_PASSWORD";
const char* mqtt_server = "YOUR_MQTT_SERVER_IP";
const int mqtt_port = 1883; // Standard MQTT Port
const char *mqtt_user = "YOUR_MQTT_USERNAME";
const char *mqtt_pass = "YOUR_MQTT_PASSWORD";
const char *mqtt_client_name = "Roomba"; // Client connections can't have the same connection name
const int noSleepPin = 2;
// USER CONFIGURED SECTION END //////////////////////////////

WiFiClient espClient;
PubSubClient client(espClient);
SimpleTimer timer;
Roomba roomba(&Serial, Roomba::Baud115200);

// Variables
bool toggle = true;
bool boot = true;
long battery_Current_mAh = 0;
long battery_Voltage = 0;
long battery_Total_mAh = 0;
long battery_percent = 0;
char battery_percent_send[50];
char battery_Current_mAh_send[50];
uint8_t tempBuf[10];
int timerId[2]; // 0 controls sending information, 1 controls automatic waking
const char* lastTask = "Waiting";
const char* lastStatus = "Waiting";
String current_song = "McDonalds";
bool setupComplete = false; // Flag to track setup completion

// Functions

//////////////////////////////////////////////////////////////
// Wifi and MQTT Initialization
//////////////////////////////////////////////////////////////

void setup_wifi() 
{
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) 
  {
    delay(500);
  }
}

void reconnect() 
{
  // Loop until we're reconnected
  int retries = 0;
  while (!client.connected()) 
  {
    if(retries < 50)
    {
      // Attempt to connect
      if (client.connect(mqtt_client_name, mqtt_user, mqtt_pass, "roomba/connection", 0, 0, "Connected")) 
      {
        // Once connected, publish an announcement...
        if(boot == false)
        {
          client.publish("checkIn/roomba", "Reconnected"); 
        }
        if(boot == true)
        {
          client.publish("checkIn/roomba", "Rebooted");
          boot = false;
        }

        // ... and resubscribe
        client.subscribe("roomba/commands");
      } 
      else 
      {
        retries++;
        // Wait 5 seconds before retrying
        delay(5000);
      }
    }
    if(retries >= 50)
    {
      restartESP();
    }
  }
}

//////////////////////////////////////////////////////////////
// Roomba Callback/MQTT Commands
//////////////////////////////////////////////////////////////

void callback(char* topic, byte* payload, unsigned int length) 
{
  String newTopic = topic;
  payload[length] = '\0';
  String newPayload = String((char *)payload);
  if (newTopic == "roomba/commands") 
  {

    // Ensure Roomba is awake so that it can listen for a command
    if (!timer.isEnabled(timerId[1]))
    {
      wakeUp();
    }
    
    // Execute the appropriate function based off the MQTT message
    // When adding command execution to Home Assistant, these are all
    // the current available commands through MQTT
    if (newPayload == "start")
    {
      startCleaning();
    }
    else if (newPayload == "max_clean")
    {
      startMaxCleaning();
    }
    else if (newPayload == "spot_clean")
    {
      startSpotCleaning();
    }
    else if (newPayload == "stop")
    {
      stopCleaning();
    }
    else if (newPayload == "halt")
    {
      stopNow();
    }
    else if (newPayload == "play_song1")
    {
      playSongMcDonaldsJingle();
    }
    else if (newPayload == "play_song2")
    {
      playSongAmongUs();
    }
    else if (newPayload == "play_song3")
    {
      playSongEvangelion();
    }
    else if (newPayload == "play_song4")
    {
      playSongJingleBellRock();
    }
    else if (newPayload == "play_song5")
    {
      playSongLastChristmas();
    }
    else if (newPayload == "restart")
    {
      restartESP();
    }
  }
}

//////////////////////////////////////////////////////////////
// Roomba Commands
//////////////////////////////////////////////////////////////

// Initiates the standard cleaning cycle
void startCleaning()
{
  Serial.write(128);
  delay(50);
  Serial.write(131);
  delay(50);
  Serial.write(135);
  lastStatus = "Cleaning";
  client.publish("roomba/status", lastStatus);
}

// Will maximize the cleaning time based off battery life
void startMaxCleaning()
{
  Serial.write(128);
  delay(50);
  Serial.write(131);
  delay(50);
  Serial.write(136);
  lastStatus = "Max Cleaning";
  client.publish("roomba/status", lastStatus);
}

// Focuses on specific current area
void startSpotCleaning()
{
  Serial.write(128);
  delay(50);
  Serial.write(131);
  delay(50);
  Serial.write(134);
  lastStatus = "Spot Cleaning";
  client.publish("roomba/status", lastStatus);
}

// Initiates the "seek dock" command
void stopCleaning()
{
  Serial.write(128);
  delay(50);
  Serial.write(131);
  delay(50);
  Serial.write(143);
  if (strcmp(lastStatus, "Docked") != 0)
  {
    lastStatus = "Returning";
    client.publish("roomba/status", lastStatus);
  }
}

// Halts the roomba by turning the power off and on
void stopNow()
{
  Serial.write(128);
  delay(50);
  Serial.write(131);
  delay(50);
  Serial.write(133);
  // Wake the roomba back up after stopping
  wakeUp();
  lastStatus = "Halted";
  client.publish("roomba/status", lastStatus);
}

// Used for resetting the microcontroller
void restartESP()
{
  ESP.restart();
}

// Plays the McDonald's Jingle
void playSongMcDonaldsJingle()
{
  timer.disable(timerId[0]);
  delay(50);
  switchStoredSong("McDonalds");
  delay(50);
  if (strcmp(lastStatus, "Waiting") != 0)
  {
    client.publish("roomba/status", "Playing McDonald's Jingle");
  }
  Serial.write(128);
  delay(50);
  Serial.write(131);
  delay(50);
  Serial.write(141);
  delay(50);
  Serial.write(0);
  timer.enable(timerId[0]);
  timer.restartTimer(timerId[0]);
  client.publish("roomba/status", lastStatus);
  delay(1600); // Duration of song to prevent spamming  
}

// Plays the Among Us Song
void playSongAmongUs()
{
  timer.disable(timerId[0]);
  delay(50);
  switchStoredSong("Among Us");
  delay(50);
  client.publish("roomba/status", "Playing Among Drip");
  Serial.write(128);
  delay(50);
  Serial.write(131);
  delay(50);
  Serial.write(141);
  delay(50);
  Serial.write(1);
  delay(50);
  delay(4800); // Duration of part 1 and two quarter note rests minus delays
  Serial.write(128);
  delay(50);
  Serial.write(131);
  delay(50);
  Serial.write(141);
  delay(50);
  Serial.write(2);
  delay(3300); // Prevent spamming the song
  timer.enable(timerId[0]);
  timer.restartTimer(timerId[0]);
  client.publish("roomba/status", lastStatus);
  delay(50);  
}

// Plays A Cruel Angel's (Thesis) Roomba
void playSongEvangelion()
{
  timer.disable(timerId[0]);
  delay(50);
  switchStoredSong("Evangelion");
  delay(50);
  client.publish("roomba/status", "Playing A Cruel Angel's Thesis");
  Serial.write(128);
  delay(50);
  Serial.write(131);
  delay(50);
  Serial.write(141);
  delay(50);
  Serial.write(0);
  delay(50);
  delay(3300); // Duration of part 1 minus delays
  Serial.write(128);
  delay(50);
  Serial.write(131);
  delay(50);
  Serial.write(141);
  delay(50);
  Serial.write(1);
  delay(3409); // Duration of part 2 minus delays plus sixteenth note rest
  Serial.write(128);
  delay(50);
  Serial.write(131);
  delay(50);
  Serial.write(141);
  delay(50);
  Serial.write(0);
  delay(50);
  delay(3300); // Duration of part 3 minus delays
  Serial.write(128);
  delay(50);
  Serial.write(131);
  delay(50);
  Serial.write(141);
  delay(50);
  Serial.write(2);
  delay(3300); // Duration of part 4 minus delays; Prevents spamming the song
  timer.enable(timerId[0]);
  timer.restartTimer(timerId[0]);
  client.publish("roomba/status", lastStatus);
  delay(50);
}

// Plays Jingle Bell Rock
void playSongJingleBellRock()
{
  timer.disable(timerId[0]);
  delay(50);
  switchStoredSong("Jingle Bell Rock");
  delay(50);
  client.publish("roomba/status", "Playing Jingle Bell Rock");
  Serial.write(128);
  delay(50);
  Serial.write(131);
  delay(50);
  Serial.write(141);
  delay(50);
  Serial.write(0);
  delay(50);
  delay(3501); // Duration of part 1 minus delays + 1
  Serial.write(128);
  delay(50);
  Serial.write(131);
  delay(50);
  Serial.write(141);
  delay(50);
  Serial.write(1);
  delay(4001); // Duration of part 2 minus delays
  Serial.write(128);
  delay(50);
  Serial.write(131);
  delay(50);
  Serial.write(141);
  delay(50);
  Serial.write(2);
  delay(50);
  delay(4001); // Duration of part 3 minus delays
  Serial.write(128);
  delay(50);
  Serial.write(131);
  delay(50);
  Serial.write(141);
  delay(50);
  Serial.write(3);
  delay(3251); // Duration of part 4 minus delays; Prevents spamming the song
  timer.enable(timerId[0]);
  timer.restartTimer(timerId[0]);
  client.publish("roomba/status", lastStatus);
  delay(50);
}

// Plays Last Christmas
void playSongLastChristmas()
{
  timer.disable(timerId[0]);
  delay(50);
  switchStoredSong("Last Christmas");
  delay(50);
  client.publish("roomba/status", "Playing Last Christmas");
  Serial.write(128);
  delay(50);
  Serial.write(131);
  delay(50);
  Serial.write(141);
  delay(50);
  Serial.write(0);
  delay(50);
  delay(3657); // Duration of part 1 minus delays + 1
  Serial.write(128);
  delay(50);
  Serial.write(131);
  delay(50);
  Serial.write(141);
  delay(50);
  Serial.write(1);
  delay(5062); // Duration of part 2 minus delays
  Serial.write(128);
  delay(50);
  Serial.write(131);
  delay(50);
  Serial.write(141);
  delay(50);
  Serial.write(2);
  delay(50);
  delay(3313); // Duration of part 3 minus delays
  Serial.write(128);
  delay(50);
  Serial.write(131);
  delay(50);
  Serial.write(141);
  delay(50);
  Serial.write(3);
  delay(4782); // Duration of part 4 minus delays; Prevents spamming the song
  timer.enable(timerId[0]);
  timer.restartTimer(timerId[0]);
  client.publish("roomba/status", lastStatus);
  delay(50);
}

// Plays the McDonald's Jingle
// This is used at startup only
void playStartupSong()
{
  delay(50);
  Serial.write(128);
  delay(50);
  Serial.write(131);
  delay(50);
  Serial.write(141);
  delay(50);
  Serial.write(0);
  delay(1600); // Duration of song to prevent spamming  
}

//////////////////////////////////////////////////////////////
// Song Creation
//////////////////////////////////////////////////////////////

void switchStoredSong(String song_name) {
  if (song_name.equalsIgnoreCase(current_song)) 
  {
    // The song_name matches the current song (case-insensitive).
    return;
  }

  // Prevent sending roomba data from overlapping with song creation
  if (setupComplete) 
  {
   if (timer.isEnabled(timerId[0]))
    {
    timer.disable(timerId[0]);
    }
  }

  // Start SCI
  Serial.write(128);
  // Enter "Safe" Mode
  Serial.write(131);
  // Define the song data based on the selected song
  if (song_name.equalsIgnoreCase("Evangelion")) 
  {
    // Code to play the "Evangelion" song
    // Replace this comment with your actual code
    current_song = "Evangelion"; // Update the current song name
    byte songData[] = {
    140, 0, 12, // A Cruel Angel's Roomba (part 1 and 3)
    72, 28,
    75, 28,
    77, 21,
    75, 21,
    77, 14,
    77, 14,
    77, 14,
    82, 14,
    80, 14,
    79, 7,
    77, 14,
    79, 31, // Changed from 35 to 31 to have a 50+ ms delay
    140, 1, 12, // A Cruel Angel's Roomba (part 2)
    79, 28,
    82, 28,
    84, 21,
    77, 21,
    75, 14,
    74, 14,
    74, 14,
    72, 14,
    74, 14,
    77, 7,
    75, 14, 
    75, 28, // Sixteenth note rest after this (need to add a delay)
    140, 2, 11, // A Cruel Angel's Roomba (part 4)
    79, 28,
    82, 28,
    84, 21,
    79, 21,
    77, 14,
    82, 14,
    82, 14,
    79, 14,
    82, 14,
    82, 21,
    84, 35
    };
    // Send the song data to the Roomba
    for (int i = 0; i < sizeof(songData); i++) {
      Serial.write(songData[i]);
      delay(50); // Delay between sending bytes (adjust as needed)
    }
  }
  else if (song_name.equalsIgnoreCase("Among Us")) 
  {
    // Code to play the "Among Us" song
    current_song = "Among Us"; // Update the current song name

    byte songData[] = {
      140, 1, 10, // Among Us Drip (part 1)
      60, 20,
      63, 20,
      65, 20,
      66, 20,
      65, 20,
      63, 20,
      60, 60,
      58, 10,
      62, 10,
      60, 40,
      140, 2, 14, // Among Us Drip (part 2)
      60, 20,
      63, 20,
      65, 20,
      66, 20,
      65, 20,
      63, 20,
      66, 80,
      66, 13,
      65, 13,
      63, 13,
      66, 13,
      65, 13,
      63, 13,
      60, 40,
    };
    // Send the song data to the Roomba
    for (int i = 0; i < sizeof(songData); i++) {
      Serial.write(songData[i]);
      delay(50); // Delay between sending bytes (adjust as needed)
    }
  }
  // Rewrites McDonald's Jingle at song 0
  else if (song_name.equalsIgnoreCase("McDonalds"))
  {
    // Code to play the "McDonalds" song
    current_song = "McDonalds"; // Update the current song name

    byte songData[] = {
    140, 0, 5, // McDonald's Jingle (for rebooting)
    60, 10,
    62, 20,
    64, 20,
    69, 20,
    67, 30
    };
    // Send the song data to the Roomba
    for (int i = 0; i < sizeof(songData); i++) {
      Serial.write(songData[i]);
      delay(50); // Delay between sending bytes (adjust as needed)
    }
  }
  else if (song_name.equalsIgnoreCase("Jingle Bell Rock")) 
  {
    // Code to play the "Jingle Bell Rock" song
    // Replace this comment with your actual code
    current_song = "Jingle Bell Rock"; // Update the current song name
    byte songData[] = {
    140, 0, 10, // Jingle Bell Rock (part 1)
    72, 16, // C4 eighth
    72, 16, // C4 eighth
    72, 32, // C4 quarter
    71, 16, // B3 eighth
    71, 16, // B3 eighth
    71, 32, // B3 quarter
    69, 16, // A3 eighth
    71, 16, // B3 eighth
    69, 16, // A3 eighth
    64, 44, // E3 eighth + quarter (Changed from 48 to 44 to have a 50+ ms delay)
    140, 1, 10, // Jingle Bell Rock (part 2)
    69, 16, // A3 eighth
    71, 16, // B3 eighth
    69, 16, // A3 eighth
    64, 48, // E3 eighth + quarter
    67, 32, // G3 quarter
    69, 16, // A3 eighth
    71, 16, // B3 eighth
    69, 16, // A3 eighth
    65, 48, // F3 eighth + quarter
    0, 28,  // quarter rest (Changed from 32 to 28 to have a 50+ ms delay)
    140, 2, 10, // Jingle Bell Rock (part 3)
    62, 16, // D3 eighth
    64, 32, // E3 quarter
    65, 16, // F3 eighth
    67, 16, // G3 eighth
    69, 32, // A3 quarter
    67, 16, // G3 eighth
    62, 16, // D3 eighth
    64, 16, // E3 eighth
    65, 16, // F3 eighth
    67, 76, // G3 eighth + half (Changed from 80 to 76 to have a 50+ ms delay)
    140, 3, 6, // Jingle Bell Rock (part 4)
    0, 16,  // eighth rest
    69, 32, // A3 quarter
    69, 16, // A3 eighth
    71, 32, // B3 quarter
    67, 16, // G3 eighth
    72, 96 // C4 quarter + half
    };
    // Send the song data to the Roomba
    for (int i = 0; i < sizeof(songData); i++) {
      Serial.write(songData[i]);
      delay(50); // Delay between sending bytes (adjust as needed)
    }
  }
  else if (song_name.equalsIgnoreCase("Last Christmas")) 
  {
    // Code to play the "Last Christmas" song
    // Replace this comment with your actual code
    current_song = "Last Christmas"; // Update the current song name
    byte songData[] = {
    140, 0, 8, // Last Christmas (part 1)
    64, 54, // E3 dotted quarter
    64, 36, // E3 eighth+eighth
    62, 36, // D3 quarter
    62, 18, // D3 eighth
    64, 18, // E3 eighth
    64, 18, // E3 eighth
    66, 18, // F#3 eighth
    62, 32, // D3 eighth + eighth (Changed from 36 to 32 to have a 50+ ms delay)
    140, 1, 11, // Last Christmas (part 2)
    59, 18, // B2 eighth
    59, 18, // B2 eighth
    64, 18, // E3 eighth
    64, 18, // E3 eighth
    66, 36, // F#3 quarter
    62, 54, // D3 dotted quarter
    59, 18, // B2 eighth
    61, 18, // C#3 eighth
    62, 18, // D3 eighth
    61, 18, // C#3 eighth 
    59, 86, // B2 eighth + half (-4)
    140, 2, 7, // Last Christmas (part 3)
    66, 36, // F#3 quarter
    64, 54, // E3 eighth + dotted quarter
    64, 18, // E3 eighth
    66, 18, // F#3 eighth
    67, 18, // G3 eighth
    66, 18, // F#3 eighth
    64, 50, // E3 eighth + dotted quarter (-4)
    140, 3, 8, // Last Christmas (part 4)
    62, 18, // D3 eighth
    61, 18, // C#3 eighth
    61, 18, // C#3 eighth
    62, 18, // D3 eighth
    61, 36, // C#3 eighth + eighth
    62, 36, // D3 quarter
    61, 36, // C#3 eighth + eighth
    57, 122 // A2 dotted quarter + half (-4)
    };
    // Send the song data to the Roomba
    for (int i = 0; i < sizeof(songData); i++) {
      Serial.write(songData[i]);
      delay(50); // Delay between sending bytes (adjust as needed)
    }
  }
  else 
  {
    // Code to handle other cases
    return;
  }

  // Re-enable sending data
  if (setupComplete) 
  {
    if (!timer.isEnabled(timerId[0]))
    {
    timer.enable(timerId[0]);
    timer.restartTimer(timerId[0]);
    }
  }
}

// This is primarily only to be used for setup() since timer methods
// seem to not behave correctly when still in the setup (i.e. not loop)
// stage.
void initializeStartingMusic()
{
  // Start SCI
  Serial.write(128);
  // Enter "Safe" Mode
  Serial.write(131);
  // Define the song data
  byte songData[] = {
    140, 0, 5, // McDonald's Jingle (for rebooting)
    60, 10,
    62, 20,
    64, 20,
    69, 20,
    67, 30,
  };

  // Send the song data to the Roomba
  for (int i = 0; i < sizeof(songData); i++) {
    Serial.write(songData[i]);
    delay(50); // Delay between sending bytes (adjust as needed)
  }
}

//////////////////////////////////////////////////////////////
// Sensor Data
//////////////////////////////////////////////////////////////

void sendInfoRoomba() {
  roomba.start();
  // Charging State
  roomba.getSensors(21, tempBuf, 1);
  battery_Voltage = tempBuf[0];
  delay(50);
  // Battery Charge
  roomba.getSensors(25, tempBuf, 2);
  battery_Current_mAh = tempBuf[1]+256*tempBuf[0];
  delay(50);
  // Battery Capacity
  roomba.getSensors(26, tempBuf, 2);
  battery_Total_mAh = tempBuf[1]+256*tempBuf[0];

  int nBatPcent = 100; // This helps control the no-sleep timer enabling
  if(battery_Total_mAh != 0)
  {
    nBatPcent = 100*battery_Current_mAh/battery_Total_mAh;
    String temp_str2 = String(nBatPcent);
    temp_str2.toCharArray(battery_percent_send, temp_str2.length() + 1); // Packaging up the data to publish to mqtt
    client.publish("roomba/battery", battery_percent_send); // Even when sitting on dock with 100 battery, it appears to return 92 brefly 1-2 times an hour
  }
  if(battery_Total_mAh == 0)
  {  
    client.publish("roomba/battery", "NO DATA");
  }
  String temp_str = String(battery_Voltage);
  temp_str.toCharArray(battery_Current_mAh_send, temp_str.length() + 1); // Packaging up the data to publish to mqtt
  client.publish("roomba/charging", battery_Current_mAh_send);

  // Code Charging State
  // 0 Not Charging
  // 1 Charging Recovery
  // 2 Charging
  // 3 Trickle Charging
  // 4 Waiting
  // 5 Charging Error

  // Communication with the roomba can be iffy with values such as 8 or 200 appearing incorrectly.
  // If an unexpected value appears, no new message is published
  if (battery_Voltage > 0 && battery_Voltage <= 5)
  {
    // Save the current non-Docked status before changing it to "Docked" in case we need to revert back
    if (strcmp(lastStatus, "Docked") != 0)
    {
      lastTask = lastStatus;
    }
    lastStatus = "Docked";
    client.publish("roomba/status", lastStatus);
  }
  // A detected bug with the particular Roomba I test on is a charging value showing as 2. I've previosuly
  // had issues with "bad" charging values being returned hence the (0,5] range in the previous if check
  // That "2" while cleaning causes status to change to "Docked" and my Home Asssitant then triggers a "stop"
  // command so that the Roomba HA switch appears as off. To quick fix this, we'll focus on "correcting"
  // the status using a logically impossible state where the Roomba is "Docked" but not charging. lastTask
  // essentially follows the contents of lastStatus exept for "Docked". Home Assistant will have to wait
  // and see if the status comes back multiple times as "Docked" before executing a "stop" command to update
  // the Roomba switch.
  // So far, this will not cause an issue when physically Docked because no charging value of "0" has been
  // improperly detected when truely Docked.
  else if (battery_Voltage == 0 && strcmp(lastStatus, "Docked") == 0)
  {
    lastStatus = lastTask;
    client.publish("roomba/status", lastStatus);
  }
  
  // Turn on the no-sleep timer while actively charging/battery is not 100% so that we can monitor it's progress
  if (nBatPcent < 100 && !timer.isEnabled(timerId[1]) && (strcmp(lastStatus, "Docked") == 0))
  {
    timer.enable(timerId[1]);
    timer.restartTimer(timerId[1]);
  }
  // Once it's 100%, we can stop forcing it awake until it's used again
  else if (nBatPcent == 100)
  {
    timer.disable(timerId[1]);
  }

}

//////////////////////////////////////////////////////////////
// Keep Awake DD
//////////////////////////////////////////////////////////////

// Part of the stay-awake timer
void stayAwakeLow()
{
  digitalWrite(noSleepPin, LOW);
  timer.setTimeout(1000, stayAwakeHigh);
}

void stayAwakeHigh()
{
  digitalWrite(noSleepPin, HIGH);
}

// Used as a single one-time wake up
void wakeUp()
{
  delay(100);
  digitalWrite(noSleepPin, HIGH);
  delay(100);
  digitalWrite(noSleepPin, LOW);
  delay(500);
  digitalWrite(noSleepPin, HIGH);
  delay(2000);
}

//////////////////////////////////////////////////////////////
// Setup and Loop
//////////////////////////////////////////////////////////////

void setup() 
{
  // Wake-up roomba
  pinMode(noSleepPin, OUTPUT);
  digitalWrite(noSleepPin, HIGH);
  // Change Baud rate
  Serial.begin(115200);
  Serial.write(129);
  delay(50);
  Serial.write(11);
  delay(50);

  // Setup WiFi and MQTT Connections
  setup_wifi();
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback);

  delay(50);

  initializeStartingMusic();

  // Create the info-sending and stay-awake timer
  timerId[0] = timer.setInterval(5000, sendInfoRoomba);
  timerId[1] = timer.setInterval(60000, stayAwakeLow);
  timer.disable(timerId[1]);

  client.publish("roomba/status", lastStatus); // Publishes "Waiting" on startup

  playStartupSong(); // Play jingle to indicate setup completion

  setupComplete = true; // Set the setup flag to true
}

void loop() 
{
  if (!client.connected()) 
  {
    reconnect();
  }
  client.loop();
  timer.run();
}
