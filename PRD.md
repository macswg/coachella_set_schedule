# PRD: Festival Schedule Board (Setlist / Schedule Timer)

## Overview
This project provides a “schedule board” for a festival day that tracks each act’s scheduled times and optionally captures actual start/end times during live operation. The key product goal is to help operators understand **what should be happening now**, **how much slack exists before the next fixed start**, and **whether the day is running late**.

## Goals
- Show the authoritative published schedule for a stage/day.
- Track actual start/end and visualize variance vs schedule.
- Model lateness as **slip-only** (lateness can accumulate; earliness becomes more break).
- Provide a clear break-focused view so operators know when to be ready for the next act.

## Non-Goals
- Auto-pulling the next act earlier due to early finishes.
- Automatically editing the published schedule (schedule edits happen upstream).

## Scheduling Policy (Source of Truth)
- The fixed schedule is authoritative: `scheduled_start` / `scheduled_end` do not change (updated via the Google Sheet).
- Early finishes do **not** pull the next act earlier; they extend interstitial/break time.
- Late finishes can compress break to zero and create downstream lateness (“slip”).

## Core Concepts & Definitions
- `scheduled_start`, `scheduled_end`: published times.
- `actual_start`, `actual_end`: recorded times (optional; live input).
- `slip` (seconds, `>= 0`): how late the live timeline is versus the published schedule.
- Projections are “slip-aware” and never pull times earlier than schedule:
  - `projected_start[i] = scheduled_start[i] + slip`
  - `projected_end[i] = projected_start[i] + duration`
  - `slip_next = max(0, projected_end[i] - scheduled_start[i+1])`
- Breaks:
  - `scheduled_break = scheduled_start[i+1] - scheduled_end[i]`
  - `projected_break = max(0, scheduled_start[i+1] - projected_end[i])`

## Primary User Stories
1. As an operator, I can see the current act state (upcoming/running/completed) and the scheduled window.
2. As an operator, I can record `actual_start` and `actual_end` per act.
3. As an operator, I can see start/end variance and whether the day is late (`slip`).
4. As an operator, I can see “break remaining until next scheduled start” (even if the prior act ended early).
5. As a viewer, I can see an estimated end-of-day time that is **never earlier** than the published end.

## Product Requirements
### Per-Act Display
- Show scheduled start/end for every act.
- If actual times exist, show them and compute:
  - start variance: `actual_start - scheduled_start`
  - end variance: `actual_end - scheduled_end` (or live if running)
- Optional indicators (configurable): slip-at-next-start, projected break.

### Break-Focused Display
- Always show the next act’s **scheduled** start time as fixed.
- Show “estimated ready time” (current act projected end).
- Show “break remaining” until the next scheduled start.
- If the current act overlaps the next scheduled start, show “overlapping by X”.

### Headline Summary
- Current time.
- Current act + state.
- Current `slip` (non-negative).
- Published end-of-day and estimated end-of-day (`published + slip` at last act end).

## Acceptance Criteria
- Early finish scenario: when an act ends before its scheduled end, the next act’s displayed scheduled start does not move earlier, `slip` returns to 0, and projected break increases.
- Late finish scenario: when an act ends after its scheduled end and overlaps the next scheduled start, `slip > 0`, projected break goes to 0, and estimated end-of-day can move later.
- No projection or UI element ever presents a start time earlier than `scheduled_start`.

## Success Metrics (Lightweight)
- Operators can identify "break remaining" and "late by" within 5 seconds on the main view.
- During live use, recorded actual start/end times match operator intent (no accidental schedule edits).

## Technical Architecture

### Platform & Stack
| Component | Decision |
|-----------|----------|
| Server | Python + FastAPI (single process serves everything) |
| Templates | Jinja2 (server-rendered HTML) |
| Interactivity | HTMX (server interactions, WebSocket) + Alpine.js (client-side reactivity) |
| Data source | Google Sheets API (Service Account auth) |
| Local storage | Browser localStorage for offline viewing |
| Hosting | Local machine (LAN access only) |

No Node.js or build step required. Run with single command: `uvicorn main:app`

### Data Flow
1. **Page load**: FastAPI fetches schedule from Google Sheets, renders via Jinja2 template.
2. **Real-time sync**: HTMX WebSocket (`hx-ws`) connects browser to FastAPI for live updates.
3. **Record time**: Operator clicks "Now" button → HTMX sends to FastAPI → FastAPI writes to Google Sheets → broadcasts updated HTML to all connected clients.
4. **Client-side**: Alpine.js handles live clock display and slip calculations without server round-trips.
5. **Offline**: Browser localStorage caches schedule for read-only viewing if connection lost.

### Sync & Connectivity
| Aspect | Decision |
|--------|----------|
| Multi-operator sync | Real-time via HTMX WebSocket (`hx-ws`) |
| Offline behavior | Read-only mode (can view cached schedule, cannot record times until reconnected) |
| Timezone | Festival local time only (PDT for Coachella) |
| Conflict resolution | Last-write-wins with timestamp; operators see updates in real-time |

## UI/UX Specifications

### Layout & Theme
| Aspect | Decision |
|--------|----------|
| Stage view | Single stage (no multi-stage support for MVP) |
| Primary layout | Vertical timeline (acts stacked top-to-bottom, current act highlighted) |
| Theme | Dark mode by default (optimized for outdoor/bright sunlight use) |
| Time-of-day (TOD) | **Prominently displayed** and always visible (large header clock) |
| Highlight color | **Green** for primary text highlights (e.g., current act emphasis) |

### Per-Act Display
- **Act name** prominently displayed
- Scheduled start/end times
- Actual start/end times (if recorded)
- Variance indicators (early/late)

### Alerts & Warnings
- **Slip threshold**: Visual warning appears when slip exceeds **5 minutes**
- Warning style: UI color change and/or banner notification
- No audio/haptic alerts (visual only)

## Operator Interactions

### Recording Times
- **Primary method**: "Now" button to record current timestamp with one tap
- **Secondary method**: Manual time edit if operator missed the moment or needs to correct
- **Undo/edit**: Any recorded actual time can be edited or cleared

### Access Model
- Multiple operators can view and record simultaneously
- All operators see the same shared state via WebSocket sync
- No authentication required (single shared session per stage)

## Resolved Questions
| Question | Resolution |
|----------|------------|
| Google Sheets schema | See schema below |
| Google Sheets authentication | Service Account |
| Deployment/hosting | Local machine (LAN access only) |
| Artist photos | Skip for MVP |
| Multi-stage support | Single stage only |
| Timezone handling | Festival local time only (PDT) |
| Data sync | Google Sheets API (live sync) |

## Google Sheet Schema
| Column | Description |
|--------|-------------|
| `act_name` | Artist/act name |
| `scheduled_start` | Published start time (e.g., `14:30`) |
| `scheduled_end` | Published end time |
| `actual_start` | Recorded start time (filled by app during live operation) |
| `actual_end` | Recorded end time (filled by app during live operation) |
| `notes` | Optional notes field |
