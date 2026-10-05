# RedditBot

Reddit post'larından ve yorumlarından otomatik YouTube Shorts videoları üreten Python aracı. RSS üzerinden post çeker, TTS ile seslendirir, sahte Reddit kart görselleri ekler ve dikey (1080x1920) video olarak YouTube'a yükler.

**Repo:** https://github.com/FlowConductor/RedditBot

## Ne yapar

`main.py` şu pipeline'ı çalıştırır:

1. **Reddit fetch** — `config.yaml`'daki subreddit'lerden RSS ile post çekilir; daha önce kullanılan postlar ve yasaklı başlıklar filtrelenir.
2. **Yorum çekme** — Postun yorum RSS'inden yorumlar çekilir, hedef süreye ulaşana kadar birleştirilir.
3. **TTS** — `edge-tts` ile seslendirilir, WordBoundary olaylarından kelime zamanlamaları çıkarılır.
4. **Segment eşleme** — Başlık/yorum segmentleri TTS zamanlamalarına eşlenir (ilk kart t=0'da başlar, `timing_offset_sec` ile kayma telafi edilir).
5. **Reddit kartları** — `Pillow` ile sahte Reddit kart PNG'leri üretilir.
6. **Video** — `ffmpeg` ile arka plan videosu üzerine kartlar ve ses birleştirilir.
7. **YouTube yükleme** — (opsiyonel) YouTube Data API v3 ile yüklenir.

## Gereksinimler

- Python 3.10+
- `ffmpeg` ve `ffprobe` (PATH'te)
- Google Cloud hesabı (YouTube yüklemek için)

## Kurulum

```bash
git clone https://github.com/FlowConductor/RedditBot.git
cd RedditBot
pip install -r requirements.txt
```

### 1. Yapılandırma

```bash
cp config.example.yaml config.yaml
```

`config.yaml` içindeki subreddit listesini ve ayarları kendinize göre düzenleyin.

### 2. Google OAuth (YouTube yüklemek için)

1. [Google Cloud Console](https://console.cloud.google.com)'da proje oluşturun.
2. **YouTube Data API v3**'ü etkinleştirin.
3. **OAuth consent screen** oluşturun (External + Testing).
4. **Credentials → Create Credentials → OAuth client ID** → Application type: **Desktop app**.
5. İndirdiğiniz JSON'ı proje köküne `client_secret.json` olarak koyun.
6. Consent screen'de kendi Gmail adresinizi **test kullanıcısı** olarak ekleyin.
7. İlk çalıştırmada tarayıcı açılır; yetkilendirme sonrası `token.json` oluşur ve sonraki çalıştırmalarda tekrar sorulmaz.

> Not: Uygulama Testing modunda kalırsa token 7 günde expire olur. Haftalık yeniden yetkilendirmeyi istemiyorsanız consent screen'i **Publish app** ile yayınlayın.

### 3. Arka plan videoları

İlk çalıştırmada yoksa otomatik indirilir; elle indirmek için:

```bash
python main.py --download-bg 10
```

## Kullanım

```bash
# Tek video üret ve YouTube'a yükle
python main.py

# 3 video üret, yükleme yapma
python main.py --count 3 --no-upload

# Mevcut postları listele (video üretmeden)
python main.py --list
```

| Argüman | Açıklama |
|---|---|
| `--count N` | Üretilecek video sayısı (varsayılan 1) |
| `--no-upload` | YouTube yüklemesini atla, video `output/`'da kalır |
| `--download-bg N` | N arka plan videosu indir ve çık |
| `--list` | Mevcut postları listele ve çık |

## Dosya yapısı

```
├── main.py                  # Pipeline orkestrasyonu, CLI
├── config.example.yaml      # Yapılandırma şablonu (config.yaml olarak kopyalanır)
├── reddit_fetcher.py        # RSS çekme, filtreleme, segment oluşturma
├── tts_engine.py            # edge-tts seslendirme, zamanlama eşleme
├── reddit_card.py           # Sahte Reddit kart PNG'leri
├── video_maker.py           # ffmpeg video birleştirme
├── background_downloader.py # yt-dlp ile arka plan indirme
├── subtitle_generator.py    # ASS altyazı üretimi
└── youtube_uploader.py      # YouTube Data API v3 yükleme
```

Çalışma zamanında oluşan dosyalar (`.gitignore`'da): `config.yaml`, `client_secret.json`, `token.json`, `used_posts.json`, `backgrounds/`, `output/`, `uploaded/`.

## Yapılandırma özeti (`config.yaml`)

- `subreddits` — Çekilecek subreddit listesi
- `reddit.target_duration_sec` — Hedef video süresi
- `reddit.comment_count` — Maksimum yorum sayısı
- `reddit.timing_offset_sec` — Kart/ses senkron kayması telafisi
- `tts.voice` — edge-tts sesi (örn. `en-US-GuyNeural`)
- `video.width/height/fps` — Çıktı boyutu (varsayılan 1080x1920)
- `video.reddit_card` — Kart renkleri, font, yorum sayısı
- `youtube.*` — OAuth, etiketler, açıklama şablonu

## Not

Bu araç Reddit içeriğini otomatik olarak yeniden yayınlar. Yüklediğiniz içerikte telif hakkına dikkat edin; Reddit içerik politikalarını ve YouTube topluluk kurallarını inceleyin.
