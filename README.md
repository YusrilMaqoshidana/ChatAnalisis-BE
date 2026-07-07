# ChatAnalisis API (KISS Version)

FastAPI backend untuk analisis dan pemrosesan chat WhatsApp sederhana.

## Fitur Utama

- Endpoint tunggal `/analysis` untuk parsing, filter tanggal, dan penambahan indeks.
- Penyimpanan otomatis ke MinIO dengan nama `{session_id}.csv`.
- Konfigurasi Lifecycle MinIO untuk auto-delete file secara otomatis setelah 1 hari.
- Struktur sangat sederhana, ringan, dan cepat (tanpa background tasks / Redis / heavy ML).

## Quick Start

### 1. Prasyarat
- Python 3.11+
- MinIO Server (berjalan di localhost:9000 atau dikonfigurasi melalui `.env`)

### 2. Jalankan Lokal

```bash
# Buat virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependensi
pip install -r requirements.txt

# Salin env file
cp .env.example .env

# Jalankan server
uvicorn app.main:app --reload
```

Server akan berjalan secara default di `http://0.0.0.0:8000`.

## Dokumentasi API

Lihat [API.md](docs/API.md) untuk detail endpoint `/analysis` dan `/`.
