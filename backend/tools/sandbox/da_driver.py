"""
data_analyst driver — runs INSIDE the sandbox container.

Maintains a persistent Python namespace across calls (REPL-like) and
communicates with the host over the shared /workspace volume:

  host writes   /workspace/.da_control/req-<id>.json   {"id","code","timeout"}
  driver writes /workspace/.da_control/resp-<id>.json  {"stdout","artifacts","error"}

Artifacts are saved to /workspace/.da_artifacts/ and referenced by path so the
host can rebuild them (matplotlib -> PNG, plotly -> JSON, DataFrame -> CSV).
No network, no host access — this process only ever sees the mounted workspace.
"""

import io
import os
import json
import time
import uuid
import glob
import contextlib
import threading

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import plotly.io as pio
import seaborn as sns

CONTROL_DIR = "/workspace/.da_control"
ARTIFACT_DIR = "/workspace/.da_artifacts"

# Persistent namespace shared across all executions in this session.
G = {"pd": pd, "np": np, "go": go, "px": px, "plt": plt, "sns": sns, "os": os}


def _save_artifacts(local_vars) -> list:
    artifacts = []
    os.makedirs(ARTIFACT_DIR, exist_ok=True)

    # Plotly figures defined in this call.
    for name, val in local_vars.items():
        if isinstance(val, go.Figure):
            p = os.path.join(ARTIFACT_DIR, f"plotly_{uuid.uuid4().hex}.json")
            with open(p, "w") as f:
                f.write(pio.to_json(val))
            artifacts.append({"type": "plotly", "path": p})

    # DataFrames defined in this call (export head for display).
    for name, val in local_vars.items():
        if isinstance(val, pd.DataFrame) and not name.startswith("_"):
            p = os.path.join(ARTIFACT_DIR, f"df_{uuid.uuid4().hex}.csv")
            val.head(100).to_csv(p, index=False)
            artifacts.append({"type": "dataframe", "path": p,
                              "shape": [int(val.shape[0]), int(val.shape[1])]})

    # Matplotlib figures (drawn via the pyplot state machine).
    if plt.get_fignums():
        p = os.path.join(ARTIFACT_DIR, f"plot_{uuid.uuid4().hex}.png")
        plt.savefig(p, bbox_inches="tight")
        plt.close("all")
        artifacts.append({"type": "image", "path": p})

    return artifacts


def _execute(code: str, timeout: int) -> dict:
    stdout_buffer = io.StringIO()
    local_vars = {}
    result = {"stdout": "", "artifacts": [], "error": None}

    plt.clf()
    plt.close("all")

    exc = {}

    def run_exec():
        try:
            with contextlib.redirect_stdout(stdout_buffer):
                exec(code, G, local_vars)
        except Exception as e:  # noqa: BLE001
            exc["error"] = f"{type(e).__name__}: {e}"

    t = threading.Thread(target=run_exec, daemon=True)
    t.start()
    t.join(timeout)

    if t.is_alive():
        result["error"] = f"Code execution timed out after {timeout}s (possible infinite loop)."
        plt.close("all")
        result["stdout"] = stdout_buffer.getvalue()
        return result

    if exc:
        result["error"] = exc["error"]
        result["stdout"] = stdout_buffer.getvalue()
        plt.close("all")
        return result

    try:
        result["artifacts"] = _save_artifacts(local_vars)
        # Persist newly defined variables for the next call.
        G.update(local_vars)
    except Exception as e:  # noqa: BLE001
        result["error"] = f"Artifact capture error: {e}"

    result["stdout"] = stdout_buffer.getvalue()
    return result


def _write_atomic(path: str, data: dict):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.replace(tmp, path)


def main():
    os.makedirs(CONTROL_DIR, exist_ok=True)
    os.makedirs(ARTIFACT_DIR, exist_ok=True)
    while True:
        reqs = sorted(glob.glob(os.path.join(CONTROL_DIR, "req-*.json")))
        if not reqs:
            time.sleep(0.05)
            continue
        for req_path in reqs:
            try:
                with open(req_path) as f:
                    req = json.load(f)
            except Exception:
                # Partial write; try again next tick.
                continue
            os.remove(req_path)

            rid = req.get("id", uuid.uuid4().hex)
            code = req.get("code", "")
            timeout = int(req.get("timeout", 60))

            try:
                resp = _execute(code, timeout)
            except Exception as e:  # noqa: BLE001
                resp = {"stdout": "", "artifacts": [], "error": f"Driver error: {e}"}

            _write_atomic(os.path.join(CONTROL_DIR, f"resp-{rid}.json"), resp)


if __name__ == "__main__":
    main()
