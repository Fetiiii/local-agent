import io
import sys
import os
import contextlib
import uuid
from typing import Dict, Any, List
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import seaborn as sns
import matplotlib
matplotlib.use('Agg') # GUI yok, backend
import matplotlib.pyplot as plt

class DataAnalystTool:
    name = "data_analyst"
    description = "Execute Python code for data analysis. Available libraries: pandas (pd), plotly.graph_objects (go), plotly.express (px), matplotlib.pyplot (plt)."
    
    OUTPUT_DIR = os.path.join(os.getcwd(), "data", "temp", "plots")

    def __init__(self):
        os.makedirs(self.OUTPUT_DIR, exist_ok=True)
        # Kalıcı Python ortamı
        self.globals = {
            "pd": pd,
            "go": go,
            "px": px,
            "plt": plt,
            "sns": sns,
            "os": os
        }

    def run(self, code: str, **kwargs) -> Dict[str, Any]:
        """
        Python kodunu çalıştırır.
        Çıktı (stdout), Plotly Figürleri, Matplotlib Çıktıları ve DataFrame'leri yakalar.
        """
        stdout_buffer = io.StringIO()
        local_vars = {}

        # plt.show()'u etkisiz hale getir (yoksa grafik temizlenir ve kaybolur)
        def dummy_show():
            pass
        
        original_show = plt.show
        plt.show = dummy_show
        
        # Temizlik - Önceki matplotlib figürlerini temizle
        plt.clf()
        plt.close('all')

        try:
            # Code execution
            with contextlib.redirect_stdout(stdout_buffer):
                # exec içinde local_vars sözlüğünü kullanarak değişkenleri yakalıyoruz
                exec(code, self.globals, local_vars)
            
            # STATE PERSISTENCE: Update globals so variables live across calls
            self.globals.update(local_vars)
            
            output = stdout_buffer.getvalue()
            
            # Yakalanan Artifacts (Ürünler)
            artifacts = []
            
            # 1. Plotly Figürlerini Yakala (Global veya Local scope'ta olabilir)
            # Genelde exec ile local_vars içine düşer.
            for var_name, var_val in local_vars.items():
                if isinstance(var_val, go.Figure):
                    artifacts.append(var_val)
            
            # 2. DataFrame'leri Yakala
            # Karmaşayı önlemek için sadece ismi 'df' olanı veya sonuncuyu alalım.
            # Şimdilik hepsini alalım, sidebar helper filtreler/gösterir.
            for var_name, var_val in local_vars.items():
                if isinstance(var_val, pd.DataFrame) and not var_name.startswith('_'):
                    artifacts.append(var_val)

            # 3. Matplotlib Kontrolü (Fallback)
            # Eğer kullanıcı plt.plot() yaptıysa figür arka planda oluşmuştur
            if plt.get_fignums():
                filename = f"plot_{uuid.uuid4().hex}.png"
                file_path = os.path.join(self.OUTPUT_DIR, filename)
                
                # Grafiği kaydet
                plt.savefig(file_path, bbox_inches='tight')
                plt.close('all') # Temizlik
                artifacts.append(file_path)

            # plt.show'u eski haline getir
            plt.show = original_show
            
            # 4. Çıktı Yönetimi (Clean Output)
            # Eğer artifact varsa (grafik vs), chat ekranını uzun çıktılarla kirletmeyelim.
            clean_output = output
            if artifacts:
                # Eğer çıktı çok uzunsa ve artifact varsa, çıktıyı kısalt.
                if len(output) > 500: 
                    clean_output = output[:500] + "\n...(Large output truncated, check Sidebar)"
                
                clean_output += f"\n\n✅ {len(artifacts)} adet veri görseli/tablosu oluşturuldu (Yan panele bakınız)."
            else:
                clean_output = output if output else "Code executed successfully."
            
            return {
                "text": clean_output,
                "artifacts": artifacts
            }

        except Exception as e:
            plt.close('all') # Hata durumunda da temizle
            return {
                "text": f"❌ Python Error: {str(e)}",
                "artifacts": []
            }
