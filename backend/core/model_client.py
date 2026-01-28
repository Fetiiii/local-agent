import ollama
from typing import List, Dict, Generator, Any, Optional
import json

class ModelClient:
    def __init__(self, model_name: str = "gpt-oss-20b"):
        # Kullanıcı "gpt-oss-20b" dedi ama Ollama'da modelin adı ne olacak?
        # Genelde kullanıcıya "ollama pull <model>" yaptırırız.
        # Şimdilik varsayılan olarak bir model ismi tutuyoruz.
        self.model_name = model_name
        print(f"🤖 Model Client Hazır: {self.model_name}")

    def generate(self, messages: List[Dict[str, str]], stream: bool = True, json_mode: bool = False) -> Generator[str, None, None] | str:
        """
        Ollama Chat API'sini çağırır.
        
        Args:
            messages: [{"role": "user", "content": "..."}] formatında
            stream: True ise generator döner, False ise string.
            json_mode: True ise çıktı JSON'a zorlanır.
        """
        
        options = {
            "temperature": 0.7,
            "num_ctx": 8192, # Context window artırıldı
        }
        
        format_param = "json" if json_mode else None

        try:
            if stream:
                return self._stream_generator(messages, options, format_param)
            else:
                response = ollama.chat(
                    model=self.model_name,
                    messages=messages,
                    options=options,
                    format=format_param,
                    stream=False
                )
                return response['message']['content']
                
        except Exception as e:
            return f"Error communicating with Ollama: {str(e)}"

    def _stream_generator(self, messages, options, format_param):
        stream = ollama.chat(
            model=self.model_name,
            messages=messages,
            options=options,
            format=format_param,
            stream=True
        )
        
        for chunk in stream:
            content = chunk['message']['content']
            if content:
                yield content

    def check_connection(self) -> bool:
        try:
            ollama.list()
            return True
        except:
            return False