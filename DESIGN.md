---
name: Roomba Remote
description: A phone remote drawn as the floor plan of the room you are driving in.
colors:
  plan-ink: "#142a45"
  safety-orange: "#ff5a1f"
  mint-paper: "#e4eee8"
  paper-highlight: "#f2f7f4"
  ink-secondary: "#4b6280"
  ink-faint: "#8597ab"
  grid-minor: "rgb(20 42 69 / .07)"
  grid-major: "rgb(20 42 69 / .15)"
  orange-wash: "rgb(255 90 31 / .14)"
  on-orange: "#1b0b02"
  blueprint-paper: "#16467f"
  blueprint-paper-highlight: "#1b5294"
  blueprint-ink: "#f4f8fc"
  blueprint-ink-secondary: "#cadcf0"
  blueprint-ink-faint: "#8fb2d8"
  blueprint-orange: "#ff7d47"
  blueprint-grid-minor: "rgb(235 244 255 / .10)"
  blueprint-grid-major: "rgb(235 244 255 / .22)"
typography:
  display:
    fontFamily: "Overpass, ui-sans-serif, system-ui, sans-serif"
    fontSize: "22px"
    fontWeight: 900
    lineHeight: 1
    letterSpacing: "0.2em"
  headline:
    fontFamily: "Overpass, ui-sans-serif, system-ui, sans-serif"
    fontSize: "17px"
    fontWeight: 700
    lineHeight: 1.25
    letterSpacing: "normal"
    fontFeature: "\"tnum\""
  title:
    fontFamily: "Overpass, ui-sans-serif, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 700
    lineHeight: 1.35
    letterSpacing: "0.06em"
  body:
    fontFamily: "Overpass, ui-sans-serif, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 500
    lineHeight: 1.35
    letterSpacing: "normal"
    fontFeature: "\"tnum\""
  label:
    fontFamily: "Overpass, ui-sans-serif, system-ui, sans-serif"
    fontSize: "11px"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "0.08em"
  caption:
    fontFamily: "Overpass, ui-sans-serif, system-ui, sans-serif"
    fontSize: "11px"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "0.03em"
rounded:
  none: "0px"
  lamp: "50%"
spacing:
  tag-gap: "8px"
  cell: "10px"
  sheet-gap: "14px"
  page: "16px"
  column-gap: "28px"
  grid-minor: "8px"
  grid-major: "40px"
components:
  room-tag:
    backgroundColor: "{colors.paper-highlight}"
    textColor: "{colors.plan-ink}"
    typography: "{typography.title}"
    rounded: "{rounded.none}"
    padding: "7px 6px 6px"
    height: "54px"
  room-tag-hover:
    backgroundColor: "{colors.orange-wash}"
  room-tag-pressed:
    backgroundColor: "{colors.plan-ink}"
    textColor: "{colors.paper-highlight}"
  button-primary:
    backgroundColor: "{colors.safety-orange}"
    textColor: "{colors.on-orange}"
    typography: "{typography.title}"
    rounded: "{rounded.none}"
    padding: "0 16px"
    height: "44px"
  stamp:
    backgroundColor: "{colors.mint-paper}"
    textColor: "{colors.safety-orange}"
    typography: "{typography.display}"
    rounded: "{rounded.none}"
    height: "54px"
  stamp-active:
    backgroundColor: "{colors.safety-orange}"
    textColor: "{colors.on-orange}"
  door-callout:
    backgroundColor: "{colors.paper-highlight}"
    textColor: "{colors.plan-ink}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "1px 10px 0"
    height: "30px"
  door-callout-on:
    backgroundColor: "{colors.safety-orange}"
    textColor: "{colors.on-orange}"
  titleblock-field:
    backgroundColor: "{colors.paper-highlight}"
    textColor: "{colors.plan-ink}"
    typography: "{typography.headline}"
    rounded: "{rounded.none}"
    padding: "6px 10px 7px"
  titleblock-field-alert:
    backgroundColor: "{colors.safety-orange}"
    textColor: "{colors.on-orange}"
  legend-row:
    backgroundColor: "{colors.paper-highlight}"
    textColor: "{colors.plan-ink}"
    rounded: "{rounded.none}"
    padding: "6px 10px"
    height: "44px"
  legend-row-playing:
    backgroundColor: "{colors.safety-orange}"
    textColor: "{colors.on-orange}"
  input-field:
    backgroundColor: "{colors.mint-paper}"
    textColor: "{colors.plan-ink}"
    rounded: "{rounded.none}"
    padding: "10px 10px 8px"
  toast:
    backgroundColor: "{colors.plan-ink}"
    textColor: "{colors.paper-highlight}"
    rounded: "{rounded.none}"
    padding: "8px 14px 7px"
---

# Design System: Roomba Remote

## Overview

**Creative North Star: "The Floor Plan You Drive In"**

The remote is an architectural drawing, not a gadget. Every surface is drafting paper with an 8px minor and 40px major grid; every line, label and frame is plan ink; the controls are the things a plan already contains. The drive surface is a square room with thick walls, the drive toggle is a door that swings open, commands are room tags, the songs are a legend table, status sits in a title block, and HALT is a rubber stamp. The robot is drawn top-down in the middle of the room and leaves a fading marker trail as it turns.

Density is that of a drawing sheet: thin 1.5px rules everywhere, one heavy 7px stroke reserved for walls, capitals with open tracking for every label, tabular numerals for every reading. Colour is two-ink. Navy plan ink does all structural work and a single safety orange marks the robot, the active state, alerts and danger. The world has two native forms: mint drafting paper in light mode and a blueprint (navy paper, white ink) in dark mode; both are the same drawing, never a separate theme.

The playful-toy brand lives in the details of the drawing (the door leaf swinging on Drive, the stamp tilted off-square, the trail, small line icons for songs), never in decoration added on top of it.

**Key Characteristics:**
- Drafting-paper ground with an 8px / 40px grid on both the page and the room floor.
- Square corners everywhere; the only circles are the robot and the link lamp.
- Two inks: navy for structure, safety orange for robot, active, alert and danger.
- Light mode is mint drafting paper; dark mode is a blueprint of the same plan.
- Capitals with open tracking for labels, tabular numerals for every reading.
- Flat drawing; depth is line weight and inner rules, not shadow.

## Colors

A two-ink drawing on tinted paper: navy plan ink for everything structural, one safety orange for everything that is live or dangerous.

### Primary
- **Plan Ink** (plan-ink): every frame, rule, wall, label and line icon; also the fill of a pressed toggle tag and of the toast. In blueprint form it becomes Blueprint White (blueprint-ink).

### Secondary
- **Safety Orange** (safety-orange; blueprint-orange in dark): the robot shell while driving, the open door leaf, the "Drive on" callout, the wheel-speed bars, the speed-scale thumb, a playing song row, the alert flash on the status field, the focus ring, text selection and the HALT stamp. Anything orange is either live or dangerous. Text set on orange uses Burnt Umber (on-orange).
- **Orange Wash** (orange-wash): the hover fill for every pressable surface (tags, legend rows, callout, setup cell, stamp).

### Neutral
- **Mint Drafting Paper** (mint-paper): page ground, room floor, stamp ground, input wells. Blueprint form: Blueprint Navy (blueprint-paper).
- **Paper Highlight** (paper-highlight): raised drawing elements: title block, room tags, legend, callouts, wheel columns, robot shell at rest, dialog. Blueprint form: blueprint-paper-highlight.
- **Secondary Ink** (ink-secondary): field labels, wheel readouts, tag sub-lines, scale numbers, notes copy. Passes 5.2:1 on paper.
- **Faint Ink** (ink-faint): non-text drafting marks only: tag inner rule, door swing arc, wheel tick marks, scrollbar thumb. It fails text contrast (2.5:1) and is never used for words.
- **Grid Minor / Grid Major** (grid-minor, grid-major): the 8px and 40px paper grid; grid-major also divides legend rows.

### Named Rules
**The Two Inks Rule.** Structure is plan ink; state is orange. A new element picks one of the two by asking "is this live or dangerous?" No third hue, no gradients, no tinted greys.

**The Orange Means Something Rule.** Orange appears only on the robot, an active or playing state, an alert, focus, or HALT. It is never decoration, never a brand stripe, never a section accent.

**The Same Drawing Rule.** Dark mode is the blueprint of the plan: paper becomes navy, ink becomes white, orange lightens to blueprint-orange. Layout, line weights and components do not change between modes.

## Typography

**Display Font:** Overpass (variable, 400 to 900, self-hosted; falls back to ui-sans-serif, system-ui)
**Body Font:** Overpass
**Label/Mono Font:** Overpass with tabular numerals

**Character:** One architectural sans, derived from highway signage lettering, does every job. Hierarchy comes from weight and tracking, not from a second family.

### Hierarchy
- **Display** (900, 22px, tracking 0.2em, capitals): the HALT stamp only.
- **Headline** (700 to 800, 17px, 1.25): title-block field values (status, link, battery). Single line, ellipsis on overflow.
- **Title** (700, 14px, tracking 0.06em, capitals): room-tag names; legend song names use 600 at 14px in sentence case.
- **Body** (500, 15px, 1.35, tabular numerals): base text and the speed readout (700).
- **Label** (700 to 800, 11 to 12px, tracking 0.08em to 0.12em, capitals): title-block field labels, door callout, section heads (Songs, Notes, Connection), the room name, form labels, toast (13px).
- **Caption** (600, 11px, tracking 0.03em): tag sub-lines, scale numbers, wheel readouts (700, 0.04em). Notes copy is 12px at 1.45.

### Named Rules
**The Lettering Rule.** Labels on the drawing are capitals with open tracking (0.04em to 0.2em); sentence case is reserved for content the user reads as language (song names, tag sub-lines, notes).

**The Tabular Rule.** Every number on the sheet (battery, speed, wheel mm/s, vector length) is set in tabular numerals so readings do not jitter while driving.

## Layout

Phone first. A single column sheet (max 520px, 14px gaps, 16px side padding, safe-area aware) stacks title block, room, speed scale, tags, legend and notes. The room is a square that fills the width but is capped at `100svh - 260px` (minimum 280px) so the room, scale and the command tags fit without scrolling on a phone.

At 900px and up the sheet becomes a drawing with a side panel: title block spans the top, the room (up to 640px square) on the left, a 380px column of scale, tags, legend and notes on the right, 28px column gap. The title block gains a Project field at that width.

Spacing follows the drawing rather than a numeric scale: 8px between tags (the minor grid), 10px cell padding inside framed fields, 14px between sheet sections, 28px between desktop columns. Command tags sit in a 4-column grid; Vacuum and HALT each span two columns. The legend is a 2-column table; an odd last row spans both.

## Elevation & Depth

The system is flat. Depth is drawn, not lit: a heavier stroke (7px wall vs 1.5px rule), a paper-highlight fill against the paper, or an inset double rule. The page and the room floor share the same grid so the room reads as drawn on the sheet, not floating above it.

### Shadow Vocabulary
- **Inner rule** (`box-shadow: inset 0 0 0 3px paper-highlight, inset 0 0 0 4px ink-faint`): the thin inner line that makes a rectangle a room tag. Not a shadow; a drafting mark.
- **Stamp double rule** (`box-shadow: inset 0 0 0 2px paper, inset 0 0 0 4px orange` inside a 3px orange border): the HALT stamp frame.
- **Modal lift** (`box-shadow: 0 18px 40px rgb(0 0 0 / .28)`): the connection dialog only, over a navy backdrop (`rgb(10 25 45 / .5)`). The one true shadow in the system.

### Named Rules
**The Drawn Depth Rule.** Nothing on the sheet casts a shadow. Hierarchy is line weight, fill and inner rules; the only lift is the modal dialog, which sits off the drawing.

## Shapes

Rectangles with square corners (0px) throughout: title block, tags, legend, callouts, inputs, dialog, toast, wheel columns. Circles are reserved for the robot and the link lamp (9px). Line weights carry meaning: 7px walls (the room), 4px door leaf, 3px stamp border, 2.5px robot outline, 1.5px rules for every frame and divider, 1px grid lines. Plan conventions are the form vocabulary: a door gap with jamb ticks and a dashed quarter-arc swing, callouts joined by a 10px leader line, the steering vector drawn as a dimension line with end ticks and a haloed measurement, the speed control drawn as an alternating scale bar with a pentagonal pointer.

## Components

### Room Tags (command buttons)
Rectangles with a thin inner rule, like room labels on a plan.
- **Shape:** square corners, 1.5px ink border, 3px paper gap then a 1px faint-ink inner rule; min height 54px.
- **Content:** capital name (Title) over a sentence-case sub-line (Caption, secondary ink). Under 370px the sub-line hides and the name drops to 12px.
- **Hover:** orange-wash fill, inner rule kept. **Active:** nudges down 1px. **Sent:** flashes orange and fades to paper over 0.5s.
- **Pressed toggle** (aria-pressed): inverts to plan-ink fill with paper text and a paper inner rule.
- **Primary variant** (dialog Save): solid orange fill, on-orange text and border, no inner rule.
- **Disabled:** 45% opacity.

### HALT Stamp
A rubber stamp: orange 3px border with an inset second orange rule, Display lettering, tilted -1.5deg, spanning two tag columns at the same 54px height. Hover adds orange wash; press scales to 0.97 and fills solid orange with on-orange text. It is the only element set off-square. It uses the `--stamp` token rather than `--orange`: #d23c08 on light paper (about 3.9:1, clearing the 3:1 large-text floor) and #ff7d47 on the blueprint (3.73:1). Other orange-framed elements put their text on orange, not in it.

### Door (Drive toggle)
A gap in the top wall with jamb ticks; the door leaf rotates 90deg into the room (0.55s, `cubic-bezier(.16, 1, .3, 1)`) and turns orange when Drive is on, revealing a dashed swing arc. While waking (aria-busy) the leaf rocks ajar. A 30px callout tag on a leader line names the state ("Drive off" / "Drive on") and fills orange when on. Focus ring sits on the callout.

### Title Block
The plan's title strip: a framed row of fields divided by 1.5px rules on paper-highlight. Each field is a capital Label over a Headline value. Status is a button: a changed status flashes orange twice (1.1s) and holds orange until tapped. The Link field carries a 9px lamp: filled ink when live, half-filled while connecting, orange on error.

### Room (drive surface)
Square, 7px plan-ink walls, the floor grid repeated inside. Wheel columns (14px wide, tick-marked) flank the room inside the walls, each with a centre zero line and an orange bar whose length is that wheel's speed, readouts at the bottom corners. The robot is a top-down line drawing (shell, bumper, caster, ring, heading wedge) that rotates with its heading, outlines dashed when offline and fills orange when live. The trail is a round-capped orange stroke at 28% opacity fading out over 7s.

### Legend (songs)
A framed table: capital Label header with a sentence-case hint on the right, rows divided by grid-major lines, each row a 44px minimum button with an 18px stroked line icon (1.8px, ink) and the song name. Hover adds orange wash; the playing row fills orange.

### Inputs / Fields
Square, 1.5px ink border, mint-paper well inside the paper-highlight dialog, 600 15px text, orange focus ring at 1px offset. Labels are capital Label style above the field.

### Toast
Plan-ink bar with paper capital lettering (800, 13px), fixed at the bottom centre, rising 12px into place.

### Focus
Every focusable element takes a 2px orange outline at 3px offset.

## Do's and Don'ts

### Do:
- **Do** draw new controls as plan elements (room tags, callouts with leader lines, legend rows, dimension lines, title-block fields) before inventing a new widget.
- **Do** keep every frame and divider at the 1.5px rule weight and reserve the 7px stroke for walls.
- **Do** use orange only for live, active, alert, focus or danger, and set any text on orange in on-orange.
- **Do** set labels in Overpass capitals with 0.04em to 0.2em tracking and every number in tabular numerals.
- **Do** build both forms from the same tokens: mint paper with navy ink, and the blueprint with white ink.
- **Do** keep a changed status orange until the user acknowledges it.
- **Do** give every pressable surface the orange-wash hover and the 2px orange focus ring.

### Don't:
- **Don't** round corners; the only circles are the robot and the link lamp.
- **Don't** add drop shadows or glows to anything on the sheet; only the modal dialog lifts.
- **Don't** introduce a third hue, gradients or a second typeface.
- **Don't** set words in faint ink (ink-faint is 2.5:1 on paper); it is for drafting marks only.
- **Don't** set small or regular-weight text in orange on light paper; orange is a fill and stroke colour, and text belongs on it, not in it.
- **Don't** draw the drive surface as a circular joystick in a card; steering happens inside the room.
