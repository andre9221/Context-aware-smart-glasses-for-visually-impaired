# Module 2 — Dual-Stage AI Vision & TTC Pipeline
# Owner: Dhivyashree G J. (24BCE1516)
#
# Place your files here:
#   tof_gate.py         - Stage 1 depth threshold & ROI bounding box calculator
#   camera_driver.py    - Camera capture wrapper (Pi Camera CSI / OpenCV USB)
#   yolo_engine.py      - YOLOv8n inference on cropped ROI
#   ttc_engine.py       - Rolling approach rate & TTC computation
#   class_map.py        - Class filtering & severity weighting
#   sim_vision.py       - Laptop webcam mock vision testbed
#   main_vision.py      - Process entry: Queue A -> AI/TTC -> Queue B
