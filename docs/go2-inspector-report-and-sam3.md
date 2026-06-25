# Go2-Inspector Report and SAM3 Data Flow

Sources inspected:

- `amberhandal/Go2-Inspector@281ccca`
- `/tmp/go2-inspector/scripts/inspection_node.py`
- `/tmp/go2-inspector/scripts/change_detector.py`
- `/tmp/go2-inspector/scripts/inspection_report.py`
- `/tmp/go2-inspector/scripts/watchdog_run.py`

## What SAM3 Does Here

Go2-Inspector does not segment an exported 3D map directly. `inspection_node.py` runs during ROS operation, subscribes to RGB, aligned depth, and camera info topics, then periodically calls a SAM3 HTTP service.

Default inputs:

- RGB: `/camera/color/image_restamped`
- Depth: `/camera/aligned_depth_to_color/image_restamped`
- Camera info: `/camera/color/camera_info_restamped`
- Prompts: `["fire extinguisher", "exit sign"]`
- SAM3 URL: `http://129.105.69.11:8001`
- Detection interval: `3.0` seconds
- Score threshold: `0.5`

Request shape:

```http
POST {sam3_url}/detect_with_depth
files:
  rgb_image: rgb.jpg
  depth_image: depth.png
form:
  prompts: JSON string list
  score_threshold: float
  include_masks: true|false
  fx, fy, cx, cy: camera intrinsics
```

Expected response fields include `num_objects`, `processing_time_ms`, and `objects`. Each object must include `label`, `score`, `bbox`, and `centroid_3d_base`; optional fields include `mean_depth_m` and `mask_base64`.

## Localization and Deduplication

For each SAM3 object, the node:

1. Takes `centroid_3d_base` in `base_link`.
2. Uses TF to transform it into the `map` frame.
3. Deduplicates detections with the same label within `dedup_distance` meters.
4. Updates max score, running average map position, `last_seen`, and `sightings`.
5. Classifies live change state against a baseline log if one exists.

If the object has no `centroid_3d_base` or TF fails, the detection is skipped.

## Inspection Log Format

Logs are JSON files under `~/inspection_logs`. Core format:

```json
{
  "run_id": "20260624_153000",
  "timestamp": "2026-06-24T15:30:00.000000",
  "prompts": ["fire extinguisher", "exit sign"],
  "num_detections": 2,
  "detections": [
    {
      "id": 0,
      "label": "fire extinguisher",
      "score": 0.91,
      "map_position": [1.23, -0.45, 0.80],
      "centroid_3d_base": [0.72, 0.10, 0.55],
      "mean_depth_m": 1.4,
      "bbox": [120, 88, 64, 180],
      "first_seen": "2026-06-24T15:30:02.000000",
      "last_seen": "2026-06-24T15:30:08.000000",
      "sightings": 3,
      "run_id": "20260624_153000",
      "change_type": "NEW"
    }
  ],
  "changes_summary": {
    "new": 1,
    "moved": 0,
    "unchanged": 1,
    "not_revisited": 0
  }
}
```

`change_type` and `changes_summary` appear when a baseline log is loaded. Live classification uses `NEW`, `MOVED`, and `UNCHANGED`; baseline objects not matched are counted as `not_revisited`.

## Change Reports

`change_detector.py` and `inspection_report.py` compare two JSON logs by matching detections with the same `label` and nearby `map_position`.

Change classes:

- `UNCHANGED`: matched and below the unchanged threshold.
- `MOVED`: matched label but position changed.
- `NEW`: current object has no match in previous run.
- `MISSING`: previous object has no match in current run.

The saved change JSON contains:

```json
{
  "previous_run": "/path/to/previous.json",
  "current_run": "/path/to/current.json",
  "summary": {
    "unchanged": 4,
    "new": 1,
    "missing": 0,
    "moved": 2
  },
  "changes": [
    {
      "type": "MOVED",
      "label": "fire extinguisher",
      "current_position": [1.4, -0.4, 0.8],
      "previous_position": [1.0, -0.4, 0.8],
      "distance": 0.4,
      "current_score": 0.91,
      "previous_score": 0.88
    }
  ]
}
```

The PDF report is a deterministic inspection change report. It includes run IDs, timestamps, object counts, search prompts, summary counts, detailed tables by change type, and recommendations for missing or moved objects.

## Export Bundle

`watchdog_run.py` manages a full run and writes a self-contained folder under:

```text
~/watchdog_runs/run_YYYYMMDD_HHMMSS/
```

On shutdown it attempts to save:

- 2D Nav2 map via `nav2_map_server map_saver_cli`,
- RTAB-Map database copy,
- 3D PLY export via `rtabmap-export`,
- PLY with inspection markers,
- annotated 2D building plan,
- PDF inspection report,
- copied inspection JSON log.

## Implications for Our Plan

If we want segmentation after exploration, we must record RGB/depth/pose evidence during exploration or keep ROS/TF alive and run SAM3 before shutting down. The current repository is live-frame detection plus map localization; it is not an offline semantic reconstruction pipeline by itself.
