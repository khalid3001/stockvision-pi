# StockVision on a Raspberry Pi

Status: written and tested on a laptop with a webcam standing in for the Pi camera. **Not yet run on a real Raspberry Pi.** The Pi camera code path and the setup script are untested until hardware is available.

## What changed

- `src/camera.py` takes a photo with the camera attached to the computer. `camera.backend` in `config.yaml` chooses the camera: `auto` uses the Raspberry Pi camera on a Pi and the webcam anywhere else.
- The dashboard has a new first tab that takes the photo with that camera. Upload and the phone/browser camera still work.
- `scripts/capture.py` takes a photo and verifies it without the dashboard, once or on a timer.
- The model, counting, comparison, database and reports are unchanged.

## Two ways to use it

**Portable.** The Pi runs the dashboard. Someone carries the Pi (on a power bank) to a stack, opens the dashboard on their phone, and presses **Take photo** then **Run verification**. The phone is only the screen; the Pi camera takes the picture.

**Fixed.** The Pi is mounted facing one stack and counts on a timer:

```
.venv/bin/python scripts/capture.py --every 30
```

Each count is saved and appears in the dashboard's History tab. A fixed camera sees one stack from one side; stock elsewhere needs another camera or the portable mode.

## Try it on the laptop (no Pi needed)

```
.\tasks.ps1 dashboard      # first tab is "Webcam": Take photo, then Run verification
.\tasks.ps1 capture        # the same from the command line
```

Close Teams, Zoom or any browser tab using the webcam first, or the photo will fail.

## Setting up the Pi

Suggested hardware: Raspberry Pi 5 (4 GB or 8 GB), Camera Module 3 (it has autofocus), 32 GB microSD card, official power supply or a power bank for portable use.

1. Install Raspberry Pi OS (64-bit) with Raspberry Pi Imager. Connect the camera ribbon cable with the Pi switched off.
2. Check the camera works: `rpicam-still -o test.jpg`
3. Get the code: `git clone https://github.com/khalid3001/stockvision-pi.git` then `cd stockvision-pi`
4. Install: `bash scripts/pi_setup.sh` (takes a while; it downloads PyTorch)
5. Test: `.venv/bin/python scripts/capture.py --photo-only` and open the saved photo.
6. Start the dashboard: `make pi-dashboard`, then on a phone or laptop on the same Wi-Fi open `http://<pi address>:8501` (find the address with `hostname -I`).

## Things to check on the real Pi

- **Speed.** `scripts/capture.py` prints how long each count takes. Dense tube stacks are scanned in tiles and will be the slowest case. If it is too slow, lower `camera.width`/`height`, or export the model to NCNN format, which Ultralytics recommends for Raspberry Pi.
- **numpy.** The system `picamera2` and the pip packages share one numpy. If `import picamera2` fails with a numpy error after setup, run `.venv/bin/pip install "numpy<2"`.
- **Orientation.** If photos come out upside down or sideways, set `camera.rotate`.
- **Retraining.** The current model was trained on phone photos. Collect photos with the Pi camera from its real position (`scripts/capture.py --photo-only`), label them and retrain before judging accuracy.
- **Access.** `make pi-dashboard` opens the dashboard to every device on the same network, with no password.
