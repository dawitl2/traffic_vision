# Privacy and limitations

Traffic footage and plates can identify people or vehicles. Use only footage you are authorized to process. TrafficVision defaults to localhost, local SQLite, local evidence, disabled plate OCR, and a visible privacy acknowledgement.

Operator responsibilities:

- minimize collection and retain only what the stated purpose needs;
- use the retention setting and delete plate/evidence records when no longer needed;
- restrict Windows account and folder access;
- never place real footage, crops, database files, camera credentials, or reports in a public repository;
- blur faces and plates before publishing portfolio media;
- document every review decision and do not infer an owner/driver from OCR;
- comply with applicable privacy, surveillance, employment, transport, and biometric laws.

This system is not a calibrated legal instrument. Detection, tracking, geometry, OCR, speed, signal state, and incident heuristics all have failure modes. Occlusion, compression, weather, night glare, camera motion, low frame rate, perspective, model domain shift, and adversarial or unusual objects can cause misses, identity switches, or false alerts. Confidence scores are model-specific estimates, not probabilities of guilt.

Simulation records are explicitly labeled and technically excluded from real analytics. Draft PDFs are review aids and contain a permanent educational-prototype disclaimer. TrafficVision does not send reports, charge, fine, punish, or identify a person.

