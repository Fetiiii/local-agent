import chainlit as cl
from typing import List, Dict

class MemoryManager:
    def __init__(self, max_recent_messages: int = 10):
        """
        max_recent_messages: Modele her seferinde gönderilecek en fazla mesaj sayısı.
        Bu sayede bağlam penceresi (context window) şişmez.
        """
        self.max_recent_messages = max_recent_messages

    async def get_formatted_history(self, thread_id: str = None) -> List[Dict]:
        """
        Chainlit session'dan veya veritabanından geçmişi alır
        """
        # Önce mevcut session'daki hafızaya bakıyoruz
        history = cl.user_session.get("history") or []
        
        # Eğer hafıza çok uzunsa son 'max_recent_messages' kadarını alıyoruz
        if len(history) > self.max_recent_messages:
            history = history[-self.max_recent_messages:]
            
        return history

    def add_message(self, role: str, content: str):
        """
        Yeni bir mesajı hafızaya ekler.
        """
        history = cl.user_session.get("history") or []
        history.append({"role": role, "content": content})
        cl.user_session.set("history", history)

    def clear_memory(self):
        """Hafızayı sıfırlar."""
        cl.user_session.set("history", [])

    @staticmethod
    def convert_thread_to_history(thread_steps: List[Dict]) -> List[Dict]:
        """
        Veritabanından gelen 'thread steps' yapısını
        """
        formatted_history = []
        for step in thread_steps:
            # Sadece mesaj içeriklerini alıyoruz, tool call'lar kafa karıştırmasın diye filtrelenebilir
            if step.get("type") == "user_message":
                formatted_history.append({"role": "user", "content": step.get("output", "")})
            elif step.get("type") == "assistant_message":
                formatted_history.append({"role": "assistant", "content": step.get("output", "")})
        return formatted_history