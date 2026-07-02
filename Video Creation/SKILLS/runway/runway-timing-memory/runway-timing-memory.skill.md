---
name: runway-timing-memory
description: Self-learning duration tracker for Runway node generations. Records observed durations per node type, exposes mean/stddev for next-check-in scheduling.
---

# /runway-timing-memory

Self-learning duration tracker. The runway-persistent-driver calls this skill
to decide when to wake itself up after kicking off a Runway node Run.

---

## Storage

`SKILLS/runway/runway-timing-memory/observed_durations.json`

## Schema

```json
{
  "nano-banana-pro_2K": {
    "samples": [38, 42, 51, 35, 48],
    "rolling_mean": 42.8,
    "rolling_stddev": 6.4,
    "last_updated": "2026-05-25T14:32:11Z"
  },
  "gen-4.5_5s_standard": {...},
  "gen-4.5_10s_standard": {...},
  "text-to-sfx_5s": {...},
  "elevenlabs-tts_30s": {...},
  "stitch_6clips": {...},
  "add-audio_master": {...}
}
```

Rolling window: last 20 samples per node type. All durations in seconds.

---

## API

### `record(node_type, model, duration_seconds)`

Append `duration_seconds` to the matching key's `samples` array. Truncate to
the most recent 20 entries. Recompute `rolling_mean` and `rolling_stddev`.
Update `last_updated` to current ISO-8601 timestamp.

### `expected(node_type, model)`

Return `(mean, stddev)`. If fewer than 3 samples exist, return conservative
defaults:

| Key                     | Default mean | Default stddev |
|-------------------------|--------------|----------------|
| nano-banana-pro_2K      | 60           | 20             |
| gen-4.5_5s_standard     | 90           | 30             |
| gen-4.5_10s_standard    | 180          | 60             |
| text-to-sfx_5s          | 25           | 10             |
| elevenlabs-tts_30s      | 12           | 5              |
| stitch_6clips           | 20           | 10             |
| add-audio_master        | 12           | 5              |

### `next_check_at(running_nodes)`

Input: list of `{node_type, model, start_time}` for nodes currently running.

Output: ISO-8601 timestamp for earliest expected completion across all running
nodes, computed as:

```
fireAt = min over all running_nodes of:
  start_time + 1.5 * (mean + stddev)
```

The 1.5x multiplier biases toward checking AFTER expected completion, reducing
"node not yet ready" wake-ups.

---

## Usage inside runway-persistent-driver

1. Before clicking Run on a node, record `start_time` in RUN_STATE.md.
2. On every wake-up:
   - For each completed node since last check: compute
     `actual_duration = completion_time - start_time`, call `record()`.
   - For each still-running node: nothing to record yet.
3. Compute next wake-up via `next_check_at()` on the set of still-running
   nodes, schedule via `mcp__scheduled-tasks__create_scheduled_task`.

---

## Why this exists

A prior 30s build (2026-05-19): Claude estimated 60s per Gen-4.5 clip,
actual was 90-110s. Result: too-frequent wake-ups, rate-limit toasts, wasted
context.

After 5 samples on this account: skill learns Joseph's account runs ~95s mean,
15s stddev. Check-ins scheduled at 165s land in the right window.

---

## Standard deviation calculation

Sample standard deviation, n-1 in denominator:

```
mean = sum(samples) / n
variance = sum((x - mean)^2 for x in samples) / (n - 1)
stddev = sqrt(variance)
```

For n < 2 samples, stddev = the conservative default for that key.

---

## File-write discipline

Always read, mutate, write the entire JSON file. No partial-key patches.
After writing, re-read and confirm `samples.length` increased and timestamps
moved forward. Catch JSON parse errors and abort the write rather than
corrupting the file.

---

## Related skills

- [[runway-persistent-driver]] — the consumer of this timing data.
- [[runway-full-pipeline]] — orchestrates a build end-to-end; calls into
  runway-persistent-driver after kicking off the first Run.
