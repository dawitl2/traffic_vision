# Model notes

## General objects

The CPU and balanced profiles use the lightweight Ultralytics `yolo11n.pt` COCO model with ByteTrack. GPU Accuracy uses the more accurate `yolo11s.pt`, processes every frame at 960 pixels, and uses a recall-oriented confidence floor for fast or oblique vehicles. Both can recognize common cars, motorcycles, buses, trucks, bicycles, people, and several animals. They are not traffic-law classifiers.

Ultralytics software and pretrained weights are subject to Ultralytics licensing (AGPL-3.0 and/or enterprise terms). Review those terms before deployment, distribution, or commercial use.

## Plates

FastALPR is configured with `yolo-v9-t-384-license-plate-end2end` plus `cct-xs-v2-global-model`. OCR is invoked only inside useful vehicle crops and is aggregated across frames. The application does not assume an Ethiopian format or correct output to a preferred value.

For a custom detector/OCR:

1. Record its source, model-card license, training data, intended geography, version/hash, and validation results in `THIRD_PARTY_ASSETS.md`.
2. Store large weights in `models/`, not in source folders.
3. Implement the same detector/OCR result contract.
4. Validate against consented local footage, including unreadable and negative examples.
5. Calibrate confidence thresholds; never copy scores between unrelated models.

## Hazards

The COCO model can support a stopped vehicle and broad road-user obstruction heuristics. It does **not** establish reliable support for debris, smoke, fire, flood, standing water, potholes, or fallen objects. Those UI rows remain “custom model required.” Suitable work needs licensed, camera-representative positive and hard-negative data, careful class definitions, spatial labels, adverse weather/night cases, and an evaluation that emphasizes false alerts.

## Compute

The compact ONNX plate detector and OCR are pinned to `CPUExecutionProvider`; this avoids requiring a second system-wide CUDA/cuDNN ABI in addition to PyTorch's bundled runtime. The heavier Ultralytics vehicle detector/tracker uses the NVIDIA GPU for GPU profiles and falls back to CPU after an out-of-memory error. A 4 GB GPU favors nano/small models and moderate input sizes. GPU Accuracy uses YOLO11s and can exhaust memory on long/high-resolution sources; the CPU profile remains valid.
