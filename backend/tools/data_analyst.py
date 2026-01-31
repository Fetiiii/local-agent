import io
import sys
import os
import contextlib
import uuid
from typing import Dict, Any

# Matplotlib ayarı: Pencere açma (GUI yok), sadece dosya üret (Agg backend)
import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
import pandas as pd

class DataAnalystTool:
    name = "data_analyst"
    description = "Execute Python code for data analysis. Available libraries: pandas (pd), matplotlib.pyplot (plt)."
    
    OUTPUT_DIR = os.path.join(os.getcwd(), "data", "temp", "plots")

    def __init__(self):
        os.makedirs(self.OUTPUT_DIR, exist_ok=True)
        # Kalıcı Python ortamı
        self.globals = {
            "pd": pd,
            "plt": plt,
            "os": os
        }

    def run(self, code: str, **kwargs) -> str:
        """
        Python kodunu çalıştırır, çıktıyı (stdout) ve oluşturulan grafikleri yakalar.
        """
        # Standart çıktıyı yakalamak için buffer
        stdout_buffer = io.StringIO()
        
        # plt.show()'u etkisiz hale getir (yoksa grafik temizlenir ve kaybolur)
        def dummy_show():
            pass
        
        # Mevcut plt.show fonksiyonunu yedekle (gerekirse) ve ez
        original_show = plt.show
        plt.show = dummy_show
        
        # Önceki çizimleri temizle
        plt.clf()
        plt.close('all')
        
        try:
            # Code execution
            with contextlib.redirect_stdout(stdout_buffer):
                exec(code, self.globals)
            
            output = stdout_buffer.getvalue()
            
            # Grafik kontrolü
            image_path = None
            # get_fignums() aktif figürleri döndürür
            if plt.get_fignums():
                filename = f"plot_{uuid.uuid4().hex}.png"
                file_path = os.path.join(self.OUTPUT_DIR, filename)
                
                # Grafiği kaydet
                plt.savefig(file_path, bbox_inches='tight')
                plt.close('all') # Temizlik
                image_path = file_path
                
            # plt.show'u eski haline getirmek şimdilik gerekmez ama temizlik iyidir
            plt.show = original_show
            
            result = output if output else "Code executed successfully."
            
            if image_path:
                return f"{result}\n[IMAGE_GENERATED]: {image_path}"
            
            return result

        except Exception as e:
            plt.close('all') # Hata durumunda da temizle
            return f"❌ Python Error: {str(e)}"