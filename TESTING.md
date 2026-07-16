# Testing

Run backend tests:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests -q
```

Run frontend checks:

```powershell
Push-Location frontend
npm test
npm run lint
npm run build
Pop-Location
```

Run the generated-video upload smoke test (no external footage or real plates):

```powershell
backend\.venv\Scripts\python.exe scripts\smoke_test.py
```

The automated suite covers polygon/boundary behavior, crossing, direction, dwell time, perspective calibration, scene-distance speed, outlier rejection, OCR normalization/voting, all ten module registrations, congestion scoring, duplicate suppression, health, safe filename handling, upload type rejection, and a React shell smoke render.

## Real upload acceptance test

After the user's authorized footage arrives:

1. Record source/license and copy through the dashboard upload.
2. Confirm metadata, variable-frame-rate status, and corruption handling.
3. Process once without plate OCR, then with explicit local OCR opt-in.
4. Watch WebSocket progress, measured FPS, cancellation, restart recovery, track persistence, and annotated output.
5. Confirm weak/no plate becomes `Unreadable`/`Insufficient confidence`.
6. Add route geometry and a measured/perspective calibration; verify speed against an independent reference.
7. Verify each enabled rule against positive and negative examples, evidence clip boundaries, deduplication, and the human review/PDF flow.
8. Restart through fresh PowerShell sessions using `start.ps1` and `stop.ps1`.

Do not mark the full footage acceptance test complete until real licensed footage and calibration measurements exist.

## Troubleshooting

- **FFmpeg missing after setup:** close and reopen PowerShell; winget updated the user PATH.
- **CUDA false despite NVIDIA GPU:** the installed PyTorch/ONNX build is CPU-only or incompatible. CPU analysis is supported.
- **First analysis appears slow:** pretrained weights may be downloading locally for the first time.
- **Annotated video will not play in browser:** download it or transcode to H.264 with FFmpeg.
- **Port in use:** run `stop.ps1`, inspect `data/*-error.log`, then stop only the confirmed conflicting process.
- **Corrupt upload:** re-export to a standard MP4 and verify with FFprobe. The failed file is removed.
