# MakeUrChoice — Sözleşme (T-001)

Amaç: Kullanıcı bir konuda (karar) birden fazla seçenek girer; her seçenekte **kazanacakları (gains)**, **kaybedecekleri (losses)**, **riskler (risks)** yazılır. Sonunda bir seçenek seçilir ve nedeni kaydedilir. Geçmiş kararlar SQLite'ta saklanır.

## Yığın
- Python 3 (yalnızca standart kütüphane: `http.server`, `sqlite3`, `json`) — pip paketi YOK.
- Frontend: tek sayfa, vanilla HTML/CSS/JS, `app/static/` altında. CDN/harici bağımlılık YOK.
- Port: **8767** (konteyner içinde de 8767). Veritabanı: `DB_PATH` env, varsayılan `/data/choices.db` (konteynerde volume).

## Dizin düzeni
```
Dockerfile
run.sh                 # çalıştırılabilir başlatıcı
README.md
app/server.py          # HTTP sunucu + API + statik dosya servisi
app/db.py              # sqlite şema + CRUD fonksiyonları
app/static/index.html, app.js, style.css
tests/test_api.py      # unittest, sunucuyu geçici DB ile başlatır
```

## Veri modeli (SQLite)
```sql
CREATE TABLE decisions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,                 -- konu, örn. "Hangi laptop?"
  notes TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'open', -- 'open' | 'decided'
  chosen_option_id INTEGER,            -- decided ise options.id
  decision_reason TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,            -- ISO8601 UTC
  decided_at TEXT
);
CREATE TABLE options (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  decision_id INTEGER NOT NULL REFERENCES decisions(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  gains TEXT NOT NULL DEFAULT '',      -- ne kazanırım
  losses TEXT NOT NULL DEFAULT '',     -- ne kaybederim
  risks TEXT NOT NULL DEFAULT '',      -- riskler
  position INTEGER NOT NULL DEFAULT 0
);
```
`PRAGMA foreign_keys=ON` kullanılmalı.

## API (JSON, UTF-8, hata: `{"error":"mesaj"}` + uygun 4xx)
Option nesnesi: `{id, decision_id, name, gains, losses, risks, position}`
Decision nesnesi: `{id, title, notes, status, chosen_option_id, decision_reason, created_at, decided_at, options:[Option...]}`

| Metot Yol | Gövde | Yanıt |
|---|---|---|
| GET /api/decisions | – | 200 `[Decision]` (yeniden eskiye; listede `options` dahil) |
| POST /api/decisions | `{title, notes?}` | 201 Decision (options boş). title boşsa 400 |
| GET /api/decisions/{id} | – | 200 Decision / 404 |
| PUT /api/decisions/{id} | `{title?, notes?}` | 200 Decision |
| DELETE /api/decisions/{id} | – | 204 |
| POST /api/decisions/{id}/options | `{name, gains?, losses?, risks?}` | 201 Option (name boşsa 400) |
| PUT /api/options/{id} | `{name?, gains?, losses?, risks?}` | 200 Option |
| DELETE /api/options/{id} | – | 204 (seçili seçenek silinirse karar `open`a döner) |
| POST /api/decisions/{id}/decide | `{option_id, reason?}` | 200 Decision (status=decided; option_id o karara ait değilse 400) |
| POST /api/decisions/{id}/reopen | – | 200 Decision (status=open, chosen alanları temizlenir) |

Statik: `GET /` → `app/static/index.html`; `/static/<dosya>` → dosya (path traversal engellenmeli).
`GET /healthz` → 200 `ok`.

## UI davranışı
- Sol: karar listesi (açık/verilmiş rozetli, "Yeni karar" butonu). Sağ: seçili kararın detayı.
- Detayda seçenekler kart/sütun olarak yan yana; her kartta ad + 3 metin alanı (Kazanacaklarım / Kaybedeceklerim / Riskler). Alanlar düzenlenince (blur/debounce) PUT ile otomatik kaydedilir.
- **"Yeni seçenek ekle"** butonu: karara yeni boş seçenek ekler (sınırsız).
- Her kartta "Bunu seç" → neden sorulur (opsiyonel) → decide. Verilmiş kararda seçilen kart vurgulanır, neden gösterilir, "Yeniden aç" butonu olur.
- Karar ve seçenek silme (onay ile). Türkçe arayüz metinleri.

---
# Ek (v2): Pano kopyala / içe aktar / "neden seçtim" notu (T-006)

## "Neden seçtim" (karar gerekçesi)
- `decision_reason` artık yalnızca decide anında değil, **her zaman düzenlenebilir** bir alandır (kararın "Sonuç / Neden bunu seçtim?" notu). Karar `open` iken de yazılabilir (taslak gerekçe); `decided` iken de sonradan değiştirilebilir.
- `PUT /api/decisions/{id}` gövdesi artık `{title?, notes?, decision_reason?}` kabul eder.
- `decide` gövdesindeki `reason` **verilmişse** (anahtar mevcutsa) `decision_reason`'ı üzerine yazar; **verilmemişse** mevcut `decision_reason` korunur. `reopen` ve seçili seçeneğin silinmesi artık `decision_reason`'ı **silmez** (kullanıcının yazdığı gerekçe kaybolmasın); yalnızca `status`, `chosen_option_id`, `decided_at` sıfırlanır. (Bu, v1'deki "reason temizlenir" davranışını değiştirir; testler güncellenecek.)
- UI: Karar detayında, seçeneklerin altında her zaman görünen büyük bir textarea: **"Neden bunu seçtim? / Sonuç notu"**; debounce/blur ile PUT ile otomatik kaydedilir. "Bunu seç" modalındaki neden alanı bu alanla aynı değeri önceden doldurur.

## Pano formatı (kopyala / içe aktar)
Taşınan şey bir **board JSON**'udur (sürümlü):
```json
{
  "format": "makeurchoice.board",
  "version": 1,
  "title": "Hangi laptop?",
  "notes": "",
  "status": "open",
  "chosen_option": null,
  "decision_reason": "",
  "options": [
    {"name": "A", "gains": "...", "losses": "...", "risks": "..."}
  ]
}
```
- `chosen_option`: seçili seçeneğin **adı** (string) veya `null`. id'ler pano JSON'una girmez.
- Zorunlu: `title` (boş değil), `options` (dizi, boş olabilir). Diğer alanlar yoksa varsayılan: `""`, `status:"open"`, `chosen_option:null`. Bilinmeyen alanlar yok sayılır. `format` yoksa da kabul (LLM çıktısı toleransı); varsa `makeurchoice.board` olmalı, `version` > 1 ise 400.

### Kopyalama metni (istemci üretir)
"Panoyu kopyala" butonu panoyu panoya şu metin olarak koyar (Türkçe, LLM'e yapıştırmaya uygun):
```
Aşağıda bir karar panosu var (seçenekler: kazanç / kayıp / risk). Bunu benimle tartış; önerilerin varsa değiştirilmiş panoyu aynı JSON biçiminde, tek bir ```json bloğu olarak ver.

## <başlık>
Notlar: <notes>
Durum: <Açık|Verilmiş: seçilen ad>
Neden: <decision_reason>

### Seçenek 1: <ad>
- Kazanacaklarım: ...
- Kaybedeceklerim: ...
- Riskler: ...
(...)

```json
{ ...board JSON... }
```
```
Okunabilir kısım insan/LLM içindir; içe aktarma yalnızca JSON'u kullanır.

### İçe aktarma
- `POST /api/import` gövde: `{"text": "<yapıştırılan serbest metin>"}` **veya** doğrudan board JSON nesnesi. Sunucu `text` verilmişse içinden board JSON'unu çıkarır: önce ```json ... ``` çitli blokları (sonuncudan başlayıp) dener, yoksa metindeki ilk dengeli `{...}` nesnesini dener; hiçbiri geçerli board değilse 400 `{"error": "..."}` (Türkçe mesaj).
- Her zaman **yeni** bir karar oluşturur (var olanı ezmez): 201, yanıt Decision nesnesi (options dahil, id'ler yeni). `status:"decided"` ve `chosen_option` bir seçenek adıyla eşleşiyorsa karar o seçenek seçilmiş olarak oluşur (decided_at=şimdi); eşleşme yoksa `open`. `decision_reason` aynen alınır.
- Başlığın sonuna otomatik ek yapılmaz. Sınırlar: gövde ≤1MB, ≤100 seçenek, alan başına ≤20000 karakter (aşarsa 400).
- UI: üst çubukta/listede **"İçe aktar"** butonu → büyük bir textarea'lı modal ("LLM'den gelen panoyu buraya yapıştır") → "İçe aktar" → başarıda yeni karar seçilir; hata mesajı modalda gösterilir. **"Panoyu kopyala"** butonu karar detayında; `navigator.clipboard.writeText`, başarısızsa (izin yok) metni seçili bir textarea'da gösteren yedek yol; "Kopyalandı" geri bildirimi.
