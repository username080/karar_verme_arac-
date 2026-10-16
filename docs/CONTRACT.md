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
