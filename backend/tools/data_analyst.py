import io
import os
import asyncio
import contextlib
import uuid
from typing import Dict, Any
from concurrent.futures import ThreadPoolExecutor, TimeoutError as PyTimeoutError
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import plotly.io as pio
import seaborn as sns
import matplotlib
matplotlib.use('Agg')  # GUI yok, backend
import matplotlib.pyplot as plt

from backend.core.settings import settings
from backend.tools.sandbox import sandbox, kernel, current_session_id


class DataAnalystTool:
    name = "data_analyst"
    description = (
        "Execute Python code for data analysis (persistent state across calls). "
        "Runs inside the isolated Docker sandbox when available. "
        "Available libraries: pandas (pd), numpy (np), plotly (go/px), "
        "matplotlib.pyplot (plt), seaborn (sns)."
    )

    OUTPUT_DIR = os.path.join(os.getcwd(), "data", "temp", "plots")

    def __init__(self):
        os.makedirs(self.OUTPUT_DIR, exist_ok=True)
        # Kalıcı Python ortamı (yalnızca local/host modunda kullanılır)
        self.globals = {
            "pd": pd, "go": go, "px": px, "plt": plt, "sns": sns, "os": os,
        }

    # ── Public entrypoint (async) ─────────────────────────────────────────────

    async def run(self, code: str, **kwargs) -> Dict[str, Any]:
        """Route to the sandboxed kernel when Docker is available, else run locally."""
        if sandbox.should_use() and await sandbox.is_available():
            return await self._run_sandboxed(code)
        # Host fallback: offload the blocking exec to a thread.
        return await asyncio.to_thread(self._run_local, code)

    # ── Output formatting (shared) ────────────────────────────────────────────

    @staticmethod
    def _format_output(output: str, artifacts: list) -> str:
        if artifacts:
            clean = output
            if len(output) > 500:
                clean = output[:500] + "\n...(Large output truncated, check Sidebar)"
            clean += f"\n\n✅ {len(artifacts)} adet veri görseli/tablosu oluşturuldu (Yan panele bakınız)."
            return clean
        return output if output else "Code executed successfully."

    # ── Sandboxed execution ───────────────────────────────────────────────────

    async def _run_sandboxed(self, code: str) -> Dict[str, Any]:
        resp = await kernel.execute(current_session_id(), code, timeout=60)
        stdout = resp.get("stdout", "") or ""
        error = resp.get("error")

        # Rebuild artifacts from the manifest into sidebar-compatible objects.
        artifacts = []
        for art in resp.get("artifacts", []):
            a_type, path = art.get("type"), art.get("path")
            try:
                if a_type == "image" and path and os.path.exists(path):
                    artifacts.append(path)
                elif a_type == "plotly" and path and os.path.exists(path):
                    with open(path) as f:
                        artifacts.append(pio.from_json(f.read()))
                elif a_type == "dataframe" and path and os.path.exists(path):
                    artifacts.append(pd.read_csv(path))
            except Exception as e:  # noqa: BLE001
                print(f"⚠️ Artifact rebuild error ({a_type}): {e}")

        if error:
            text = (stdout + "\n" if stdout else "") + f"❌ Python Error: {error}"
            return {"text": text, "artifacts": artifacts}

        return {"text": self._format_output(stdout, artifacts), "artifacts": artifacts}

    # ── Local (host) execution — unchanged behaviour ──────────────────────────

    def _run_local(self, code: str) -> Dict[str, Any]:
        stdout_buffer = io.StringIO()
        local_vars = {}

        original_show = plt.show
        plt.show = lambda *a, **k: None
        plt.clf()
        plt.close('all')

        try:
            with contextlib.redirect_stdout(stdout_buffer):
                def run_exec():
                    exec(code, self.globals, local_vars)
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(run_exec)
                    try:
                        future.result(timeout=60)
                    except PyTimeoutError:
                        raise TimeoutError("Code execution timed out after 60 seconds (Possible infinite loop).")

            # State persistence across calls.
            self.globals.update(local_vars)
            output = stdout_buffer.getvalue()

            artifacts = []
            for _, var_val in local_vars.items():
                if isinstance(var_val, go.Figure):
                    artifacts.append(var_val)
            for var_name, var_val in local_vars.items():
                if isinstance(var_val, pd.DataFrame) and not var_name.startswith('_'):
                    artifacts.append(var_val)
            if plt.get_fignums():
                file_path = os.path.join(self.OUTPUT_DIR, f"plot_{uuid.uuid4().hex}.png")
                plt.savefig(file_path, bbox_inches='tight')
                plt.close('all')
                artifacts.append(file_path)

            plt.show = original_show
            return {"text": self._format_output(output, artifacts), "artifacts": artifacts}

        except Exception as e:
            plt.close('all')
            plt.show = original_show
            return {"text": f"❌ Python Error: {str(e)}", "artifacts": []}
