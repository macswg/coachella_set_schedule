// Shared utility functions used by both scheduleApp (index.html) and stageApp (stage.html).

function timeToSeconds(timeStr) {
    if (!timeStr) return null;
    const parts = timeStr.split(':');
    const hours = parseInt(parts[0]);
    const mins = parseInt(parts[1]);
    const secs = parts[2] ? parseInt(parts[2]) : 0;
    return hours * 3600 + mins * 60 + secs;
}

function normalizeActTimes(currentSecs, acts) {
    // Walk acts in schedule order. If an act's scheduledStart drops more than
    // 1 hour below the previous act's start, it crossed midnight — add 86400.
    //
    // Load In rows are intentionally earlier than surrounding stage-time slots
    // (they load in before the performance) and can appear later in sheet order.
    // Exclude them from both the bump check and the prevStart baseline so they
    // don't falsely trigger midnight-crossing detection for real acts.
    let prevStart = 0;
    for (const act of acts) {
        if (act.scheduledStart === null) continue;
        if (act.isLoadIn) continue;
        if (act.scheduledStart < prevStart - 3600) {
            act.scheduledStart += 86400;
            if (act.scheduledEnd !== null) act.scheduledEnd += 86400;
            if (act.actualStart !== null) act.actualStart += 86400;
            if (act.actualEnd !== null) act.actualEnd += 86400;
            if (act.screentimeSessionStart != null) act.screentimeSessionStart += 86400;
        }
        // Also fix scheduledEnd wrapping before scheduledStart within the same act
        if (act.scheduledEnd !== null && act.scheduledEnd < act.scheduledStart) {
            act.scheduledEnd += 86400;
        }
        prevStart = act.scheduledStart;
    }
    // If any acts were pushed past midnight and current time looks like early morning
    // (before 6am), treat current time as next day too.
    const maxStart = Math.max(0, ...acts.filter(a => a.scheduledStart !== null).map(a => a.scheduledStart));
    if (maxStart > 86400 && currentSecs < 18000) {
        currentSecs += 86400;
    }
    return currentSecs;
}

function formatCountdown(seconds) {
    const isOver = seconds < 0;
    const absSeconds = Math.abs(seconds);
    const hrs = Math.floor(absSeconds / 3600);
    const mins = Math.floor((absSeconds % 3600) / 60);
    const secs = absSeconds % 60;

    let time;
    if (hrs > 0) {
        time = `${hrs}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    } else {
        time = `${mins}:${secs.toString().padStart(2, '0')}`;
    }

    return isOver ? `+${time}` : time;
}
