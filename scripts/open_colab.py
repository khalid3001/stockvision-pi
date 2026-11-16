"""Open the Colab training notebook in the browser (URL comes from config.yaml)."""
import sys
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_config

url = load_config().get("training", {}).get("colab_url", "https://colab.research.google.com/")
print(f"Opening {url}")
print("If this is the Colab home page: File > Upload notebook > notebooks/train_colab.ipynb")
print("When training finishes, move the downloaded best.pt into the weights/ folder.")
webbrowser.open(url)
