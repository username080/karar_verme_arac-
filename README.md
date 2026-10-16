# MakeUrChoice

Bir konuda seçenekleri girin; her seçenek için kazanacaklarınızı, kaybedeceklerinizi ve riskleri yazın, sonunda birini seçip nedenini kaydedin. Geçmiş kararlar saklanır.

Her şey konteynerde çalışır; sisteminize paket kurmanız gerekmez. Tek gereksinim **Docker** veya **Podman**.

## Kullanım

```sh
./run.sh            # derler, başlatır, tarayıcıda http://localhost:8767 açar
./run.sh logs       # kayıtları izle
./run.sh stop       # durdur (veri korunur)
./run.sh rebuild    # imajı yeniden derle ve yeniden başlat (veri korunur)
```

Konteyner `--restart unless-stopped` ile çalışır; bilgisayar yeniden başlayınca otomatik döner.

## Veri

Veritabanı (SQLite) konteyner içinde `/data/choices.db` dosyasındadır ve `makeurchoice-data` adlı volume'da kalıcıdır. Konteyneri silmek veya `rebuild` yapmak veriyi silmez.

Volume yeri: `docker volume inspect makeurchoice-data` (podman için `podman volume inspect ...`).

### Yedekleme

```sh
docker run --rm -v makeurchoice-data:/data -v "$PWD":/backup python:3-slim \
  cp /data/choices.db /backup/choices-yedek.db
```

Geri yükleme için `./run.sh stop` sonrası aynı komutta `cp` yönünü ters çevirin (`cp /backup/choices-yedek.db /data/choices.db`), ardından `./run.sh`. Podman'da `docker` yerine `podman` yazın.

### Tamamen silmek

```sh
./run.sh stop && docker rm makeurchoice && docker volume rm makeurchoice-data
```

## Geliştirme / test

```sh
python3 -m unittest discover tests
```

Ortam değişkenleri: `PORT` (varsayılan 8767), `DB_PATH` (varsayılan `/data/choices.db`).
