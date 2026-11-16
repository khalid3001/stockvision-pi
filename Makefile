# StockVision task runner. On Windows without `make`, use .\tasks.ps1 <target> instead.
ifeq ($(OS),Windows_NT)
PY := .venv/Scripts/python.exe
SYS_PY ?= python
else
PY := .venv/bin/python
SYS_PY ?= python3
endif

# Image, video or folder to run on:  make infer SRC=path/to/file.jpg
SRC ?= data/samples

.PHONY: install init-db train infer dashboard pi-dashboard capture report demo demo-stub test

install:
	$(SYS_PY) -m venv .venv
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r requirements.txt
	$(PY) scripts/init_db.py

init-db:
	$(PY) scripts/init_db.py

train:
	$(PY) scripts/open_colab.py

infer:
	$(PY) scripts/infer.py $(SRC)

dashboard:
	$(PY) -m streamlit run app/dashboard.py

# Raspberry Pi: reachable from a phone or laptop on the same Wi-Fi at http://<pi address>:8501
pi-dashboard:
	$(PY) -m streamlit run app/dashboard.py --server.address 0.0.0.0 --server.headless true

# Photo from the attached camera, then verify. Fixed camera:  make capture ARGS="--every 30"
capture:
	$(PY) scripts/capture.py $(ARGS)

report:
	$(PY) scripts/make_report.py

demo:
	$(PY) scripts/demo.py

demo-stub:
	$(PY) scripts/demo.py --stub

test:
	$(PY) -m pytest -q
