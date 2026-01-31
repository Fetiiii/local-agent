import ollama
import base64
import os
from typing import Any, Dict

class ImageAnalysisTool:
    name = "image_analysis"
    description = "Analyze images using a vision model. Provide the image path and a specific prompt/question about the image."

    def __init__(self, model_name: str = "qwen3-vl:2b"):
        self.model_name = model_name
        self.client = ollama.Client()

    def _encode_image(self, image_path: str) -> str:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def run(self, image_path: str = None, prompt: str = "Describe this image in detail.", **kwargs: Any) -> str:
        # image_path hem positional hem de kwargs içinden gelebilir, kontrol et
        img_path = image_path or kwargs.get("image_path") or kwargs.get("path")
        
        if not img_path:
            return "❌ Error: No image path provided. Please specify the 'image_path'."

        if not os.path.exists(img_path):
            return f"❌ Error: Image file not found at {img_path}"

        try:
            print(f"👁️ Visual Analysis Başlıyor ({self.model_name})...")
            
            # Resmi encode et
            base64_image = self._encode_image(image_path)
            
            # Ollama Vision API çağrısı
            # keep_alive: 0 -> İşlem bitince modeli VRAM'den hemen temizle
            response = self.client.generate(
                model=self.model_name,
                prompt=prompt,
                images=[base64_image],
                keep_alive=0 
            )
            
            result = response.get('response', 'No analysis generated.')
            return f"--- IMAGE ANALYSIS RESULT ---\n{result}\n-----------------------------"

        except Exception as e:
            return f"❌ Error during image analysis: {str(e)}"