# Architecture

## Data flow

```text
browser upload
  → validated unique local filename
  → FFprobe metadata (OpenCV fallback)
  → SQLite analysis job
  → streaming OpenCV decoder
  → Ultralytics detector + ByteTrack IDs
  → normalized track points and timestamps
  → camera geometry/rule modules
  → selected sharp vehicle crops → FastALPR → multi-frame vote
  → provisional incidents + local evidence + annotated video
  → WebSocket/API progress → React review dashboard
  → human decision → optional draft PDF
```

The pipeline never loads an entire video in memory. It releases capture/writer handles in `finally`, updates progress in throttled batches, checks cancellation between inference frames, and preserves completed outputs. A backend restart marks interrupted jobs failed so the operator can retry without silently claiming completion.

## Interfaces

- `services/pipeline.py`: object detector/tracker orchestration and crop-first OCR.
- `services/geometry.py`: normalized polygons, crossing, direction, perspective mapping.
- `services/speed.py`: timestamped scene distance, smoothing, outlier rejection.
- `services/plates.py`: configurable character set, length/regex validation, voting.
- `services/analysis_modules/`: ten independently keyed feature modules with enable/threshold/model status.
- `services/report.py`: review-only PDF draft.
- `api/routes.py`: validated local API, WebSocket progress, safe file serving.

Detector, tracker, OCR, hazard, and report services are deliberately isolated so later models can replace them without changing database or UI contracts.

## Persistence

SQLite uses foreign keys and WAL mode. Core tables cover camera/source/job/track/track-point/plate/incident/evidence/configuration/zone/lane/stop-line/signal/calibration/settings/log data. Coordinates and bounding boxes are normalized. Disk paths are server-generated; clients cannot request arbitrary file paths.

Real and simulated incidents share a schema but have an immutable `is_simulation` boundary. Real API queries exclude simulated rows unless explicitly requested.

## Failure boundaries

- FFprobe failure falls back to OpenCV; corrupt video returns a useful upload error.
- CUDA is selected only when the installed PyTorch runtime reports availability.
- An OCR exception skips that crop rather than failing general analysis.
- Missing plate evidence becomes `Unreadable`; disagreement becomes `Insufficient confidence`.
- Uncalibrated speed cannot become a confirmed speed finding.
- Missing hazard capability is visible model state, never fabricated support.

