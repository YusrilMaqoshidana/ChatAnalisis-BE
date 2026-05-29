# API Dokumentasi untuk Frontend

Ringkasan singkat API yang tersedia dan endpoint yang disarankan untuk memenuhi alur UI/UX:

- Alur UI: Upload File -> loading/progress -> Statistik -> Topic List -> Topic Detail -> Message Context (±5 pesan)

Base URL: http://<HOST>:<PORT>

Catatan: backend saat ini menyediakan endpoint upload training dan mekanisme progress (HTTP + WebSocket). Endpoint statistik dan browsing topic diusulkan dan belum tersedia kecuali disebutkan.

---

## 1. Health Check

- Method: GET
- Path: `/`
- Response (200):

```json
{
  "status": "success",
  "message": "Server berjalan normal",
  "data": {"status": "healthy", "app": "...", "version": "..."}
}
```

## 2. Upload & Start Topic Training

- Method: POST
- Path: `/topics/train`
- Content-Type: `multipart/form-data`
- Form fields:
  - `file` (file) — file chat export (WA) yang di-upload
  - `timeframe` (string, optional) — rentang waktu/label yang dipakai untuk normalisasi (opsional)
- Response: 202 Accepted

Contoh response:

```json
{
  "status": "success",
  "message": "Training started",
  "data": {"job_id": "<uuid>"}
}
```

Contoh curl:

```bash
curl -X POST "http://localhost:8000/topics/train" \
  -F "file=@mychat.txt" \
  -F "timeframe=2020-2024"
```

UX notes:
- Setelah upload, simpan `job_id` dari response dan gunakan untuk polling / WebSocket progress.

## 3. Polling Progress (HTTP)

- Method: GET
- Path: `/topics/progress/{job_id}`
- Response (200):

```json
{
  "status": "success",
  "message": "Job progress",
  "data": {
    "job_id": "<uuid>",
    "status": "processing|done|error",
    "progress": 0,
    "message": "Deskripsi langkah saat ini"
  }
}
```

## 4. Progress Updates (WebSocket)

- URL: `ws://<HOST>:<PORT>/topics/ws/{job_id}`
- Pesan JSON yang dikirimkan berisi status, message, dan `data` (payload progress).

Contoh penerimaan di browser (JS):

```javascript
const ws = new WebSocket("ws://localhost:8000/topics/ws/" + jobId);
ws.onmessage = (e) => {
  const msg = JSON.parse(e.data);
  // msg.status, msg.message, msg.data
  if (msg.status === 'done') {
    // fetch final results / stats
  }
};
```

## 5. Endpoint yang Direkomendasikan untuk Frontend (belum diimplementasikan)

Untuk memenuhi UI/UX yang diinginkan (Statistik, Word Cloud, Topic List, Topic Detail, dan Context), sarankan menambahkan endpoint berikut:

- GET `/topics/{job_id}/stats`
  - Deskripsi: Mengembalikan statistik chat untuk job tertentu.
  - Response contoh:

```json
{
  "status": "success",
  "data": {
    "top_senders": [{"sender":"Alice","count":120}],
    "busiest_hours": [{"hour":20,"count":300}],
    "busiest_days": [{"day":"Monday","count":900}],
    "top_words": [{"word":"lorem","count":150}],
    "total_messages": 1234
  }
}
```

- GET `/topics/{job_id}/topics` (list topics)
  - Deskripsi: Daftar topik hasil clustering BERTopic.
  - Query params: `page`, `per_page` (opsional)
  - Response contoh:

```json
{
  "status":"success",
  "data": [
    {"topic_id": 1, "name": "Topik A", "size": 120, "top_words":["kata1","kata2"]}
  ]
}
```

- GET `/topics/{job_id}/topics/{topic_id}/messages`
  - Deskripsi: Ambil pesan yang masuk ke dalam topik tertentu.
  - Query params: `page`, `per_page`
  - Response contoh: list pesan dengan `message_id`, `index`, `timestamp`, `sender`, `text`.

- GET `/messages/{job_id}/context?index={index}&window=5`
  - Deskripsi: Ambil pesan konteks sekitar indeks pesan tertentu (±window).
  - Response contoh:

```json
{
  "status":"success",
  "data": {
    "center_index": 120,
    "messages": [
      {"index":115, "sender":"Bob", "text":"...", "timestamp":"..."},
      // ... sampai index 125
    ]
  }
}
```

- GET `/topics/{job_id}/export/csv`
  - Deskripsi: Unduh CSV hasil analisis (opsional, untuk fitur ekspor).

## 6. Error Handling Model

- Semua response error mengikuti model `BaseResponse`:

```json
{
  "status": "error",
  "message": "Deskripsi error"
}
```

## 7. Rekomendasi Implementasi untuk Backend

- Tambahkan endpoints di atas (`/stats`, `/topics`, `/messages/context`) agar frontend dapat menampilkan:
  - Statistik ringkasan (pengirim teraktif, jam/hari teraktif)
  - Word cloud (kirim `top_words` dengan bobot/ukuran)
  - List topik dan ukuran topik
  - Pesan per topik dengan pagination
  - Context in-app: pesan ±5 sebelum/sesudah

## 8. Checklist FE Integration

- Upload file -> panggil `POST /topics/train` dan dapatkan `job_id`
- Tampilkan loading; buka WebSocket `ws://.../topics/ws/{job_id}` untuk real-time progress
- Saat `status === 'done'`, panggil `GET /topics/{job_id}/stats` dan `GET /topics/{job_id}/topics`
- Tampilkan word cloud dari `top_words`
- Pada klik topic -> panggil `GET /topics/{job_id}/topics/{topic_id}/messages` dan tampilkan pesan
- Untuk melihat konteks pesan -> panggil `GET /messages/{job_id}/context?index={i}&window=5`

---

Jika mau, saya bisa:
- Membuat file ini sebagai `docs/API_FE.md` (sudah dilakukan),
- atau langsung implementasikan endpoint backend yang diusulkan — pilih salah satu.

## 9. Alur Proyek (End-to-End)

- 1) Upload: Pengguna mengunggah file ekspor chat melalui UI.
- 2) Validasi & Preprocessing: Backend menerima file, memvalidasi ukuran/format, lalu mem-parsing dan membersihkan teks (normalisasi tanggal, penghapusan stopwords, tokenisasi).
- 3) Anonimisasi (opsional): Jika diperlukan, identitas sensitif dapat dihapus atau di-hash sebelum analisis.
- 4) Training Async: Backend memicu proses training BERTopic secara asinkron (background task) dan menyimpan `job_id`. Status progres tersedia melalui HTTP polling dan WebSocket.
- 5) Analisis & Ekstraksi: Setelah training selesai, sistem mengekstrak:
  - Daftar topik dan kata kunci per topik
  - Mapping pesan -> topic
  - Statistik: pengirim teraktif, jam/hari teraktif, total pesan
  - Top kata untuk word cloud (dengan bobot)
- 6) Penyimpanan Hasil: Hasil analisis disimpan (file, cache, atau DB) terkait `job_id` untuk diambil oleh frontend.
- 7) Penyajian di FE: Frontend memanggil endpoint `stats` dan `topics` untuk menampilkan dashboard, word cloud, dan daftar topik. Pengguna bisa membuka detail topik untuk melihat pesan dan konteks (±5 pesan).
- 8) Ekspor (opsional): Pengguna dapat mengunduh CSV atau laporan PDF dari hasil analisis.

## 10. Teknologi yang Dipakai

- **Bahasa & Framework**: Python 3.10+, `FastAPI` untuk API HTTP dan WebSocket.
- **Server ASGI**: `uvicorn` untuk menjalankan aplikasi.
- **Model Topik**: BERTopic (mengandalkan `scikit-learn`, `sentence-transformers` atau embedding provider) untuk clustering topik.
- **NLP & Preprocessing**: `pandas`, `numpy`, `nltk`/`spaCy` (tokenisasi, stopwords), regex untuk parsing chat teks.
- **Penyimpanan & Cache**: `redis` dipakai untuk menyimpan state progress job dan cache hasil sementara.
- **Background Processing**: BackgroundTasks (FastAPI) untuk job async; dapat diganti/skalakan ke Celery/RQ jika diperlukan.
- **WebSocket**: Native WebSocket dari FastAPI untuk streaming progress real-time.
- **Validation & Schemas**: `pydantic` untuk model response/validation.
- **Utilities**: library tambahan seperti `python-multipart` untuk upload file dan `python-dotenv` atau konfigurasi via `app.config`.
- **Containerization / Deployment (opsional)**: Docker + Docker Compose untuk environment reproducible; Nginx/Traefik untuk reverse proxy; Gunicorn/Uvicorn behind proxy.

---

Jika Anda ingin, saya dapat:
- Menambahkan diagram alur singkat di README atau `docs/` (mermaid),
- Atau mulai mengimplementasikan endpoint `/topics/{job_id}/stats` dan `/topics/{job_id}/topics` sekarang.
