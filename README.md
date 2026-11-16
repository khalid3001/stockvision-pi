# StockVision

Computer-vision stock counting pilot for a construction and hardware supplier. This is the Raspberry Pi version.

A photo or short video of a shelf goes in. The system identifies the pilot products, counts them, compares the count with the recorded inventory quantity, and produces a discrepancy report.

```
capture  ->  identify (YOLOv8n)  ->  count  ->  compare with records  ->  discrepancy report
photo/video      src/inference.py              src/comparison.py          src/report.py
                                               src/inventory.py (SQLite)
```

## Setup (once)

Needs Python 3.10 to 3.13 and git. Commands are shown for Windows PowerShell; with `make` installed, use `make <target>` instead of `.\tasks.ps1 <target>`.

```powershell
.\tasks.ps1 install      # creates .venv, installs requirements, loads the inventory CSV
.\tasks.ps1 test         # unit tests (no model needed)
.\tasks.ps1 demo-stub    # whole pipeline with a fake detector (no model needed)
```

If PowerShell refuses to run the script: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

## Train the model (Google Colab, free T4)

1. `.\tasks.ps1 train` opens Colab. Upload `notebooks/train_colab.ipynb` (File > Upload notebook).
2. Runtime > Change runtime type > T4 GPU, then Runtime > Run all. Paste your Roboflow API key when asked.
3. The notebook downloads `best.pt` and `samples.zip`.
4. Move `best.pt` into `weights/`. Unzip `samples.zip` into `data/samples/`.

## Run

| Command | What it does |
|---|---|
| `.\tasks.ps1 demo` | End-to-end smoke test on `data/samples/` with the real model |
| `.\tasks.ps1 dashboard` | Streamlit dashboard at http://localhost:8501 |
| `.\tasks.ps1 infer path\to\file.jpg` | Detection only: prints counts, saves an annotated image |
| `.\tasks.ps1 report` | Discrepancy report for the latest run (`python scripts/make_report.py --all` for every run) |
| `.\tasks.ps1 init-db` | Reload the inventory CSV into SQLite |
| `.\tasks.ps1 capture` | Take a photo with the attached camera (webcam on a laptop, Pi camera on a Raspberry Pi) and verify it |

## Raspberry Pi

This version also runs on a Raspberry Pi with a Raspberry Pi camera. The dashboard's first tab shows a live preview from the camera attached to the computer running StockVision and takes the photo on a button press, and `scripts/capture.py --every 30` counts on a timer for a fixed camera. On a laptop the webcam stands in for the Pi camera, so everything can be developed without the hardware. Setup and status: [docs/raspberry_pi.md](docs/raspberry_pi.md).


Everything the pipeline writes goes to `outputs/`: one `run-<timestamp>/` folder per verification (evidence image, `results.csv`, `run.json`) and `reports/` for the Markdown and PDF reports.

## Swapping in the client's data (Tuesday)

Nothing in the code needs to change. Only these:

1. **Roboflow**: upload the client's images, label the pilot products, generate a dataset version.
2. **Notebook, parameters cell**: set `ROBOFLOW_WORKSPACE`, `ROBOFLOW_PROJECT`, `ROBOFLOW_VERSION`, `CLASSES`. Run all. Put the new `best.pt` in `weights/`.
3. **`config.yaml`, `classes` block**: one entry per product. The key is the Roboflow class name, spelled exactly; `sku` links it to the inventory record.
4. **Inventory**: replace `data/inventory_seed.csv` with the client's recorded quantities (same columns: `sku, item_name, location, recorded_qty, unit, last_counted`), or point `inventory.source_csv` at a new file. Then `.\tasks.ps1 init-db`.
5. **`config.yaml`, `variance`**: agree the thresholds with the client.
6. Replace the files in `data/samples/` with client photos and run `.\tasks.ps1 demo`.

If the class names in `config.yaml` and the model disagree, the pipeline stops with a message listing the names the model knows.

## How counting works

- **Image**: every detection above `model.confidence` counts as one item. A photo larger than about 800 px is also scanned in overlapping 640 px tiles (`model.tiling` in `config.yaml`), so small items in a big shelf photo are not shrunk away; duplicates from neighbouring tiles are merged. A 20-megapixel photo takes about 10 seconds on a laptop CPU.
- **Video, `track` mode** (default): each item is tracked across frames and counted once, so panning along a shelf does not double count. An item must be seen in `min_track_frames` processed frames.
- **Video, `peak` mode**: the count from the single frame with the most detections. Use for a fixed camera.

## Verification status

`variance = detected - recorded`. Thresholds come from `config.yaml`.

| Status | Rule (default thresholds) |
|---|---|
| Verified (match) | within ±2% of the record |
| Minor shortage | short by up to 10% |
| Major shortage | short by more than 10% |
| Stockout | record shows stock, nothing detected |
| Overcount | more detected than recorded, beyond 2% |
| No inventory record | the sku is not in the inventory data |

## Layout

```
config.yaml           everything that changes per client
src/                  config, inventory, inference, comparison, report, pipeline, stub_detector
app/dashboard.py      Streamlit dashboard
scripts/              init_db, infer, make_report, demo, open_colab
notebooks/            Colab training notebook
data/                 inventory seed CSV, sample inputs
tests/                pytest unit tests
docs/                 Raspberry Pi setup guide
```

## Known limits

- Only visible items are counted. Items hidden behind others, or inside closed boxes, are not seen. Choose pilot products and camera angles accordingly.
- The stub detector (`demo-stub`, and the dashboard checkbox shown when no weights exist) produces fake counts. It is for testing the pipeline only.
- Video on CPU is slow: roughly a few frames per second. Keep clips short (10 to 20 seconds).

## Stand-in data

Until client images arrive, training uses the public "Fastener Object Detection" dataset by Automated Disassembly on Roboflow Universe (CC BY 4.0): https://universe.roboflow.com/automated-disassembly/fastener-object-detection
