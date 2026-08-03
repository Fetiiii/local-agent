# Frontend Session — Başlangıç Prompt'u

> Boş bir sohbette, `local-agent` dizininde aç ve aşağıdaki bloğu yapıştır.
> Böylece CLAUDE.md + hafıza + `docs/frontend-api.md` otomatik yüklenir.

---

Bu projenin frontend'ini sıfırdan modern bir stack'le yeniden yazacağız. Önce
KOD YAZMADAN plan çıkar ve bana onaylat (EnterPlanMode kullan). Backend hazır,
dokunma; sen sadece yeni frontend'i kur ve mevcut WS/REST sözleşmesine bağla.

## 0) İLK İŞ — bunları oku
- `docs/frontend-api.md` — REST uçları + WebSocket event protokolü + artifact
  descriptor'ları. Sözleşme bu. Buna göre bağlayacaksın.
- `frontend/index.html` — mevcut vanilla UI. Referans/çöp: davranışı buradan
  öğren (hangi event neyi tetikliyor), sonra tamamen değiştir.
- `backend/core/agent.py` içindeki `_serialize_artifacts` — artifact üretimi.
  Yeni bir artifact tipi (HTML/Excel/PDF preview) gerekirse burayı ADDITIVE
  genişlet, protokolü bozma.

## 1) Proje bağlamı / kuzey yıldızı
- Yerel LLM agent (llama.cpp/Ollama, OpenAI-uyumlu). Amaç: frontier OLMAYAN
  yerel modellerden (8B–200B) iskele (tool + memory + RAG + iyi UI) ile
  MAKSİMUM verim. Model tek başına "çıplak"; değeri iskele katıyor.
- Bu proje herkese açık + portfolyo. İnsanlar kurup kullanabilsin. UI'nın
  "vay be" dedirtmesi önemli.
- Günlük kullanım senaryoları (UI bunlara göre tasarlanacak):
  1. Hafif kodlama (çok ağır değil).
  2. Araştırma + **DeepSearch** modu (yetenekli modeller için; 4B için değil).
  3. Dosya/sistem işleri — gerçek bilgisayarda iş yaptırma (aşağıda terminal).

## 2) Stack
- **React + Vite + TypeScript + Tailwind + shadcn/ui.** (shadcn = anında şık,
  tutarlı bileşenler.) Alternatif tartışılabilir ama önerim bu.
- Build çıktısı statik klasöre gitsin; FastAPI (`server.py`) serve etsin
  (mount ya da `/`). Geliştirmede Vite dev-server `/ws` + `/api`'yi :8000'e
  proxy'leyebilir.
- Her şey OFFLINE çalışmalı → 3. parti JS/CSS'i (marked, highlight.js,
  DOMPurify, plotly, vs.) yerel vendor'la; CDN yok.
- Koyu/açık tema (adaptive), responsive.

## 3) Sohbet / mesaj render
- `final` ve akan `token`'ları **Markdown** olarak render et: başlıklar,
  listeler, tablolar, linkler.
- **Kod blokları**: syntax highlight + "kopyala" butonu + dil etiketi.
- Model çıktısını sanitize et (marked + highlight.js + DOMPurify).
- **Streaming hissi anlık olsun** — eski UI'da final-cevap öncesi "dead-air"
  (boş bekleme) şikâyeti vardı; ilk token gelene kadar bir "yazıyor/düşünüyor"
  göstergesi olsun, token gelince akıcı yazsın.

## 4) Ajan sürecinin GÖRÜNÜRLÜĞÜ (bu bölüm çok önemli)
Kullanıcı ajanın ne yaptığını Claude Code'daki gibi CANLI görmek istiyor:

- **To-do / plan gösterimi:** `step` event'i `thought` + `plan[]` taşıyor.
  Bunu yaşayan bir **plan/to-do checklist**'i olarak göster: adımlar
  ilerledikçe güncellensin, tool tamamlandıkça ilgili madde "yapıldı" olsun.
  (Claude Code'daki todo takibi gibi.) İstersen üstte/sağda ayrı bir "Plan"
  bölümü.
- **Reasoning / düşünce:** `step.thought` collapsible bir "düşünüyor" kutusunda.
  Açılıp kapanabilsin, varsayılan sade dursun.
- **Tool adımları:** her `tool_start`/`tool_end` collapsible bir kart —
  tool adı, argümanlar, sonuç. Çalışırken spinner, bitince durum.
- **TERMİNAL GÖRÜNÜMÜ (host işlemleri):** `shell_executor` (özellikle HOST
  modunda; ajan gerçek bilgisayarda iş yapıyor — "masaüstünde görsel klasörü
  aç, görselleri oraya taşı" gibi) çalıştığında komutu ve çıktısını
  **terminal benzeri** bir blokta göster. Kullanıcı ne komut çalıştı, ne
  çıktı geldi CANLI görsün — tıpkı benim (Claude Code) terminalde çalışmam gibi.
- **HITL onay kartları:** `approval_request` gelince (dosya düzenleme +
  host shell komutları) net bir onay kartı: başlık + detay (markdown) +
  Onayla/Reddet. Cevap `approval_response` ile döner. Onay tur ortasında
  gelebilir; socket açık kalmalı (ajan arka plan task'ında koşuyor).

## 5) Sağ ARTIFACT PANELİ (Claude uygulamasındaki gibi)
3 kolon: **sohbet geçmişi | sohbet | artifact paneli**.
`tool_end.artifacts[]`'ı inline değil bu panele yönlendir:
- `plotly` → interaktif grafik (`Plotly.newPlot`, responsive).
- `table` → render'lı tablo (DataFrame.head).
- `image` → `<img>` (matplotlib base64 PNG).
- `links` → **web-search kaynakları listesi**: hangi sitelere/URL'lere
  gidildiği (başlık + link + snippet) görünsün.
- **HTML üretimi** → sandbox'lı `<iframe>`'de RENDER + kodunu göster.
  Sekme/tab: **Kod / Önizleme** (Claude-artifacts tarzı).
- **Excel / PDF / Markdown üretimi** → hem kaynak/kod hem RENDER'lı hali.
  (Bunun için backend'de `_serialize_artifacts`'a `file` tipi + preview
  desteği eklemen gerekebilir — additive yap.)
- Birden fazla artifact olabilir; panelde geçmiş/sekme mantığı kur, hangi
  tool'dan geldiği belli olsun.

## 6) Modlar & kontroller
- **DeepSearch toggle (🔎):** açıkken `user_message`'a deep_research bayrağı
  gider (mevcut protokolde var). Bu, çok adımlı derin araştırma modu —
  yetenekli modele yönelik. UI'da net bir aç/kapa.
- **Model seçici:** `/api/models`'tan doldur (provider'a göre listelenir).
- **Dosya upload (📎):** `/api/upload` (multipart, `session_id` WS `session`
  event'inden). Doküman → RAG'e ingest; görsel → analiz bağlamı.
- **Sol sidebar sohbet geçmişi:** `/api/conversations` (liste), tıkla →
  `resume`, yeni sohbet → `new`, sil → DELETE. Resume'de `history` event'i
  gelir, geçmişi render et.

## 7) Yöntem
- Tasarım/renk/tipografi kararlarında `artifact-design` skill'ini; grafik/
  görselleştirme kararlarında `dataviz` skill'ini kullan.
- ÖNCE plan (EnterPlanMode): dosya yapısı, bileşen ağacı, build entegrasyonu
  (FastAPI serve), protokol→UI eşlemesi, hangi artifact tipleri hangi
  bileşene gidiyor, terminal + to-do + onay bileşenlerinin yeri. Onaydan
  sonra kod.
- Backend'i bozma; artifact için backend desteği gerekirse additive genişlet
  ve `docs/frontend-api.md`'yi güncelle.
- Bitince: build + `.venv/bin/uvicorn server:app --port 8000` ile test.
  (Model backend'i ben açarım — llama-server :8080.)

## 8) Başlamadan bana SOR
Nasıl bir "his" istiyorum:
- Renk paleti / marka rengi var mı?
- Yoğun-teknik mi, ferah-minimal mi?
- Claude uygulamasına benzesin mi, yoksa kendine özgü bir kimlik mi?
- Varsayılan tema (koyu/açık)?
