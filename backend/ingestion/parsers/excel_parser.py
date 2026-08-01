from pathlib import Path
import re

class ExcelParser:
    def __init__(self):
        # MarkItDown lazily created on first use (see _engine).
        self._md = None

    def _engine(self):
        if self._md is None:
            from markitdown import MarkItDown
            self._md = MarkItDown()
        return self._md

    def parse(self, file_path: Path) -> str:
        """
        Excel dosyasını Microsoft MarkItDown kullanarak Markdown'a çevirir
        ve ardından oluşan kirlilikleri (NaN, Unnamed vb.) temizler.
        """
        try:
            print(f"📊 Excel İşleniyor (MarkItDown): {file_path.name}")

            # 1. Dönüştürme
            result = self._engine().convert(str(file_path))
            raw_text = result.text_content
            
            # 2. Temizlik (Post-Processing)
            cleaned_text = self._clean_artifacts(raw_text)
            
            return cleaned_text
            
        except Exception as e:
            return f"Error processing Excel with MarkItDown: {e}"

    def _clean_artifacts(self, text: str) -> str:
        """Markdown metnindeki Excel artıklarını temizler."""
        
        # 1. 'Unnamed: 0', 'Unnamed: 1' gibi başlıkları sil
        text = re.sub(r'Unnamed:\s*\d+', ' ', text)
        
        # 2. 'NaN' veya 'nan' ifadelerini sil
        text = re.sub(r'\bNaN\b', ' ', text)
        text = re.sub(r'\bnan\b', ' ', text)
        
        # 3. Metin içinde görünen literal '\n' kaçış karakterlerini boşluk yap
        text = text.replace('\\n', ' ')
        
        return text
