# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users
The owner (and household) of a Roomba 600/800 series retrofitted with an ESP8266. Primary scene: standing in a room, phone in one hand, eyes mostly on the robot, thumb on the joystick, driving it like an RC car. Secondary: the same page embedded as an iframe card in a Home Assistant dashboard on desktop, and a gamepad paired to the phone/PC.

## Product Purpose
Real-time remote control of an old non-WiFi Roomba over MQTT: drive it, toggle vacuum while driving, start/stop cleaning cycles, dock, halt, and play the custom songs. Success is a remote that feels immediate and fun in the hand and always shows whether the link and the robot are live.

## Positioning
A homemade RC conversion of a vacuum robot, not a vendor app. It exists because the owner built the hardware, the firmware, and the songs themselves.

## Operating Context
- Served by Home Assistant's /local and through nginx at a private HTTPS domain; also usable on plain LAN HTTP.
- Talks MQTT over WebSockets (wss://<host>/mqtt or ws://<lan-ip>:9001) with a limited `roomba_web` account.
- Firmware stops the wheels 600 ms after the last drive message; the page repeats drive messages every 100 ms while input is held.
- Drive mode must be turned on (about a 3 s wake) before steering works.

## Capabilities and Constraints
- Topics: roomba/commands (start, stop, spot_clean, max_clean, halt, drive_on, drive_off, vacuum_on, vacuum_off, play_song1..5), roomba/drive ("left,right" mm/s, ±500), roomba/status, roomba/battery, roomba/drive/state.
- Songs: 1 McDonald's jingle, 2 Among Us, 3 A Cruel Angel's Thesis, 4 Jingle Bell Rock, 5 Last Christmas.
- Single static HTML file plus vendored mqtt.js; no build step; must work offline on the LAN (fonts self-hosted or system).
- Settings come from the URL hash or localStorage.

## Brand Commitments
Tone confirmed by the owner: playful toy. The project already has a sense of humor (meme songs, startup jingle).

## Evidence on Hand
Real photos of the retrofitted Roomba in docs/ (Roomba_01-03.JPEG). No logo or brand assets exist.

## Product Principles
- The robot's safety and the link state are always visible; stopping is never more than one tap away.
- Thumb-first: the stick and the most-used actions sit within reach on a phone without scrolling.
- Fun is in the details, never at the cost of control.
