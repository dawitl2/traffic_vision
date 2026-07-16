# Speed calibration guide

Speed is derived from a tracked road-contact point (normally bottom-center of the vehicle box), video/decoder timestamps, and real-world road-plane distance. A license plate identifies a track; it is never part of the speed calculation.

## Before calibrating

- Use a fixed camera. Stabilize or reject moving/zooming footage.
- Work in the speed-measurement region where vehicle contact points are visible.
- Confirm timestamps/frame rate with a reference recording.
- Record route name, location, speed limit, measurement date, operator, and units.

## Method 1: measured reference

Mark two road points or parallel crossing lines visible in the image. Measure the actual road distance in metres along the vehicle path. Enter the distance and restrict measurement to nearby travel with similar perspective. A single scale is unsafe across a deep perspective view; use a short region or perspective calibration instead.

## Method 2: perspective/homography

Mark four non-collinear points on the same road plane and enter their corresponding real coordinates in metres. Use a surveyed rectangle/trapezoid with good image coverage. TrafficVision rejects degenerate point sets and maps track points through the homography before calculating distance.

## Validation

Run several vehicles at independently known speeds through the whole region. Compare direction, timestamps, pixel contact point, mapped path, smoothed segment speeds, and final speed. Record calibration confidence and error. Recalibrate after camera movement, lens/zoom change, resolution/crop change, or road-layout change.

Until this validation is complete, results must remain **Uncalibrated / approximate** and cannot support a confirmed speeding record.

For each later video/route, provide: route/camera name, fixed/moving camera status, known distance or four world points, speed limit, and where the measurement region begins/ends.

