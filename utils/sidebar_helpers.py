import chainlit as cl
import plotly.graph_objects as go
import pandas as pd
from typing import List, Any
import os

async def set_sidebar_elements(title: str, artifacts: List[Any]):
    """
    Artifacts listesini alır, tipine göre Chainlit elementine dönüştürür
    ve Sidebar'a EKLER (Append).
    
    Artifact Tipleri:
    - plotly.graph_objects.Figure -> cl.Plotly
    - pandas.DataFrame -> cl.Dataframe
    - str (path) -> cl.File veya cl.Image (uzantıya göre)
    - list[dict] (web search results) -> cl.Text (Markdown listesi)
    - str (html/text) -> cl.Text
    """
    new_elements = []
    
    # Session'dan mevcut sidebar geçmişini al
    history = cl.user_session.get("sidebar_history", [])
    
    # Counter for unique names if needed
    base_count = len(history)

    for i, item in enumerate(artifacts):
        try:
            # 1. Plotly Figure
            if isinstance(item, go.Figure):
                new_elements.append(
                    cl.Plotly(figure=item, name=f"Grafik-{base_count + i + 1}", display="side")
                )
            
            # 2. Pandas DataFrame
            elif isinstance(item, pd.DataFrame):
                name = f"Tablo ({item.shape[0]}x{item.shape[1]})"
                new_elements.append(
                    cl.Dataframe(data=item, name=name, display="side")
                )
            
            # 3. Dosya Yolu (String)
            elif isinstance(item, str) and os.path.exists(item):
                ext = os.path.splitext(item)[1].lower()
                filename = os.path.basename(item)
                
                if ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']:
                    new_elements.append(
                        cl.Image(path=item, name=filename, display="side")
                    )
                else:
                    new_elements.append(
                        cl.File(path=item, name=filename, display="side")
                    )
            
            # 4. Web Search Sonuçları (Liste)
            elif isinstance(item, list) and item and isinstance(item[0], dict):
                md_lines = []
                for res in item:
                    title_txt = res.get('title', 'No Title')
                    url = res.get('link', '#')
                    snippet = res.get('snippet', '')
                    md_lines.append(f"### [{title_txt}]({url})\n{snippet}\n")
                
                content = "\n".join(md_lines)
                new_elements.append(
                    cl.Text(content=content, name="Arama Sonuçları", display="side")
                )

            # 5. Düz Metin / HTML (Fallback)
            elif isinstance(item, str):
                new_elements.append(
                    cl.Text(content=item, name="Metin Çıktısı", display="side")
                )
                
        except Exception as e:
            print(f"⚠️ Sidebar Element Error: {item} -> {e}")
            continue

    if new_elements:
        # Geçmişe ekle
        history.extend(new_elements)
        cl.user_session.set("sidebar_history", history)
        
        # Sidebar başlığını ve içeriğini güncelle
        # Not: Title her seferinde güncellenir, son tool'un adı görünür.
        await cl.ElementSidebar.set_title(title)
        await cl.ElementSidebar.set_elements(history)
        print(f"✅ Sidebar güncellendi: {len(new_elements)} yeni, toplam {len(history)} element.")
    else:
        print("⚠️ Sidebar için uygun element bulunamadı.")
