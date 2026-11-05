---
version: 1
slug: "web-index-html"
primary_target: "web/index.html"
related_targets: []
---

Scope: web/index.html, the Roomba remote. Visitor mode: Operate. Phone-first (standing in the room, thumb on the stick, eyes on the robot); also an HA iframe on desktop; gamepad optional.
Task: drive (drive on, steer, stop), vacuum while driving, clean/spot/max/dock/halt, 5 songs, see link + robot status + battery at a glance. Constraints: one static file + vendored assets, offline LAN, no scrolling needed for stick + core actions on a phone.

## Direction contract
THESIS: The remote is a floor plan of the room you are driving in. Refuses the default dark gadget dashboard with a circular joystick floating in a card.
OWN-WORLD: Pale mint graph paper with a 8px minor / 40px major grid, navy plan ink for every line and label, one safety-orange for the robot, the active state, and danger. Walls are thick ink strokes, door swings are quarter arcs, controls are room tags (rectangles with a thin inner rule) and plan callouts. Architectural lettering, capitals, tabular numerals.
STORY: The visitor sees the robot sitting in its room, knows instantly whether it is live, turns Drive on, and steers by dragging inside the room; the robot rotates and leaves a marker trail. Fixtures around the room hold cleaning and songs.
FIRST VIEWPORT: Title-block strip on top (status, link, battery as plan revision fields). The room (square, thick walls, door gap) fills the width; wheel columns flank it inside the walls; robot top-down in the center. Drive toggle is the door. Below: speed scale bar, then a row of room tags (Clean, Spot, Max, Dock) and HALT as an orange stamp. Songs as a legend table.
SIGNATURE: driving draws a fading marker trail and the robot turns with its heading (dead reckoning from wheel speeds, illustrative only). A changed status flashes orange and holds until tapped (from the gate-board challenger).
RAISES: Labanotation: bilateral law, left wheel column left, right wheel right, length = speed. Variable-font specimen: one input (the stick) drives every readout continuously. Gate board: changed state holds its alert until noticed.
FORM: candidate 7 of 7 (floor plan / cleaning path drawing), seed 628d7da4.
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
