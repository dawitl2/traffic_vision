# Third-party assets and licenses

Inventory date: 2026-07-16. This is a dependency/asset record, not legal advice. Exact resolved versions are in `backend/requirements.txt` and `frontend/package-lock.json`; installed distributions include their license metadata/files.

## System tool

| Asset | Source | License | Use |
|---|---|---|---|
| FFmpeg 8.1.2 full build by Gyan Doshi | `winget` package `Gyan.FFmpeg`; upstream ffmpeg.org | GPL build; individual bundled libraries retain their licenses | Probe, future clipping/transcoding |

## Python direct dependencies

| Package | License | Use |
|---|---|---|
| FastAPI | MIT | Local typed API |
| Uvicorn | BSD-3-Clause | ASGI server |
| SQLAlchemy | MIT | SQLite ORM |
| Pydantic / pydantic-settings | MIT | Validation and local configuration |
| python-multipart | Apache-2.0 | Streaming uploads |
| aiofiles | Apache-2.0 | Async file support |
| OpenCV Python | Apache-2.0 | Decode, geometry, annotations |
| NumPy | BSD-3-Clause | Numerical processing |
| Shapely | BSD-3-Clause | Zones, polygons, intersections |
| Ultralytics | AGPL-3.0 by default or separate Ultralytics commercial terms | YOLO detection and ByteTrack integration |
| PyTorch / Torchvision CUDA runtime | BSD-3-Clause | GPU-accelerated Ultralytics inference with CPU fallback |
| FastALPR | MIT | Plate detector/OCR orchestration |
| ONNX Runtime | MIT | Local plate-model inference |
| ReportLab | BSD | Draft PDF reports |
| psutil | BSD-3-Clause | Local health metrics |
| pytest / pytest-asyncio | MIT / Apache-2.0 | Tests |
| HTTPX | BSD-3-Clause | API tests |

Ultralytics states that its trained models are AGPL-3.0 by default and that proprietary/commercial uses may require an Enterprise license. This educational portfolio does not modify or override those terms. Review <https://www.ultralytics.com/license> before publishing, distributing, or commercializing.

## Frontend direct dependencies

| Package | License | Use |
|---|---|---|
| React / React DOM | MIT | UI runtime |
| React Router | MIT | Page routing |
| TanStack Query | MIT | API state |
| Zustand | MIT | Lightweight UI state |
| Recharts | MIT | Analytics charts |
| Lucide React | ISC | Interface icons |
| Vite and React plugin | MIT | Build/dev server |
| Tailwind CSS and Vite plugin | MIT | Styling toolchain |
| TypeScript | Apache-2.0 | Type checking |
| Vitest / Testing Library / jsdom | MIT | Frontend tests |
| Oxlint | MIT | Static checks |

## Pretrained models

The configured weights were downloaded from their loaders' official registries on 2026-07-16 for local verification. The YOLO weight is stored in `models/`; the two plate weights remain in the user's standard model caches and are not duplicated into the project.

| Model | Provider/source | SHA-256 | License/status | Scenario |
|---|---|---|---|---|
| `yolo11n.pt` | Ultralytics official release assets | `0EBBC80D4A7680D14987A577CD21342B65ECFD94632BD9A8DA63AE6417644EE1` | AGPL-3.0 by default / Ultralytics terms | General object detection |
| `yolo11s.pt` | Ultralytics official release assets | `85A76FE86DD8AFE384648546B56A7A78580C7CB7B404FC595F97969322D502D5` | AGPL-3.0 by default / Ultralytics terms | Higher-recall GPU Accuracy detection |
| `yolo-v9-t-384-license-plate-end2end` | `open-image-models` registry | `888397B96D761C89DB40BC9C305838E8652660F5E282C2CADEBBE8D2951A77A8` | Repository MIT; verify weight/data terms before redistribution | Plate detection inside vehicle crops |
| `cct-xs-v2-global-model` | `fast-plate-ocr` registry | `8031AFB5FDC6B4D80462C9D542F1284EBD2CFDDF5DBACD62609848D7E2855F44` | Repository/package MIT; verify weight/training-data terms before redistribution | Plate text recognition |

Do not assume that a permissively licensed loader proves every training source can be redistributed. Re-check the model cards and upstream terms before publishing cached weights.

## Videos and datasets

No external video or dataset was downloaded. The only current test clip was generated locally from simple geometric shapes and contains no real people, vehicles, or plates. The user will provide authorized footage later. When a file is added, record source, creator, original filename, license/permission, acquisition date, intended scenario, and whether public display is allowed. Do not treat "freely viewable" as permission to redistribute.
