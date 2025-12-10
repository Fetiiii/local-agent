# Local GPT Agent

Yerel çalışacak, llama.cpp + GPT-OSS 20B destekli, masaüstü ajan uygulaması.

## Özellikler
- GPT-OSS 20B + llama.cpp backend
- Chat / Coder / Analyst / Agent modları
- Araçlar: file_loader, web_search, memory, python_exec, sql_query, image_analysis, shell_exec, planning/reflection
- Sohbet geçmişi SQLite
- Masaüstü UI

## Kurulum (taslak)
1) Python 3.11 kurulu olmalı
2) `python -m venv .venv && .venv\Scripts\activate`
3) `pip install -r requirements.txt`
4) `./llama/scripts/run_server.ps1` (llama.cpp server placeholder)

## Klasörler
- backend/: çekirdek ajan, araçlar, modlar, DB, utils
- ui/: Uygulama Arayüzü
- llama/: model ve server scriptleri
- data/: yüklenen dosyalar, temp ve exportlar


### Hala Geliştiriyorum şuan bitmiş bir proje değildir. ###
