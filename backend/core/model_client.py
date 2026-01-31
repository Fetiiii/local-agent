import ollama
from typing import List, Dict, AsyncGenerator, Any, Optional, Union
import json
import asyncio

class ModelClient:
    def __init__(self, model_name: str = "glm4.7-flash:latest"):
        self.model_name = model_name
        self.client = ollama.AsyncClient()
        print(f"🤖 Model Client Hazır: {self.model_name}")

    async def generate(self, messages: List[Dict[str, str]], stream: bool = True, json_mode: bool = False) -> Union[AsyncGenerator[str, None], str]:
        """
        Ollama Chat API'sini çağırır (Async).
        
        Args:
            messages: [{"role": "user", "content": "..."}] formatında
            stream: True ise AsyncGenerator döner, False ise string.
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
                response = await self.client.chat(
                    model=self.model_name,
                    messages=messages,
                    options=options,
                    format=format_param,
                    stream=False
                )
                return response['message']['content']
                
        except Exception as e:
            # Ollama JSON parse hatası verirse (model JSON formatına uyamazsa)
            # json_mode olmadan tekrar denemeyi veya hatayı yönetmeyi sağlar.
            if "parsing" in str(e).lower() and json_mode:
                print(f"⚠️ Ollama JSON Parse Hatası: {e}. Raw moda dönülüyor...")
                # Fallback durumunda model_name'i açıkça belirt
                response = await self.client.chat(
                    model=self.model_name,
                    messages=messages,
                    options=options,
                    stream=False
                )
                return response['message']['content']
            
            return f"Error communicating with Ollama: {str(e)}"

    async def _stream_generator(self, messages, options, format_param) -> AsyncGenerator[str, None]:
        stream = await self.client.chat(
            model=self.model_name,
            messages=messages,
            options=options,
            format=format_param,
            stream=True
        )
        
        async for chunk in stream:
            content = chunk['message']['content']
            if content:
                yield content

    async def check_connection(self) -> bool:
        try:
            await self.client.list()
            return True
        except:
            return False