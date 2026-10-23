"""Download tau2-bench airline trajectories (one model per family) -> data/raw/ + SHA256SUMS"""

import hashlib
import pathlib
import urllib.request

BUCKET = "https://sierra-tau-bench-public.s3.amazonaws.com/submissions"

FILES = {
    "claude-sonnet-4-5": "claude-sonnet-4-5_sierra_2026-02-26/trajectories/claude-sonnet-4-5_enabled_airline_gpt-5.2_4trials.json",
    "gpt-5-2": "gpt-5-2_sierra_2026-02-26/trajectories/gpt-5.2_high_airline_gpt-5.2_4trials.json",
    "qwen3-5-397b": "qwen3.5-397b-a17b-think_sierra_2026-03-02/trajectories/qwen3.5-397b-a17b_enabled_airline_gpt-5.2_4trials.json",
    "glm-5": "glm-5-think_sierra_2026-03-02/trajectories/glm-5_enabled_airline_gpt-5.2_4trials.json",
    "gemini-3-flash": "gemini-3-flash_sierra_2026-03-02/trajectories/geminiflash-airline.json",
}

RAW = pathlib.Path(__file__).resolve().parent.parent / "data" / "raw"


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    sums = []
    for model, key in FILES.items():
        out = RAW / f"{model}_airline.json"
        if not out.exists():
            print(f"downloading {model} ...")
            urllib.request.urlretrieve(f"{BUCKET}/{key}", out)
        digest = hashlib.sha256(out.read_bytes()).hexdigest()
        sums.append(f"{digest}  {out.name}  ({key})")
        print(f"{model}: {out.stat().st_size / 1e6:.1f} MB")
    (RAW / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
