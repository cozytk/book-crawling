"""Stage only production API sources; never copy env files or local data."""
import json
import shutil
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / ".deploy" / "api"
target.mkdir(parents=True, exist_ok=True)
for name in ("api", "crawlers", "models", "crawler_logging"):
    shutil.copytree(root / name, target / name, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "Dockerfile", "requirements.txt"))
(target / "app.py").write_text("from api.app import app\n")
shutil.copyfile(root / "api/requirements.txt", target / "requirements.txt")
(target / ".python-version").write_text("3.12\n")
(target / "vercel.json").write_text(json.dumps({
    "$schema": "https://openapi.vercel.sh/vercel.json",
    "framework": "fastapi", "regions": ["icn1"],
    "functions": {"app.py": {"maxDuration": 60}},
}))
print(target)
