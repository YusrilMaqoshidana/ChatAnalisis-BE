# Chat Analysis API Documentation (KISS Version)

Dokumentasi API backend untuk analisis chat WhatsApp yang telah disederhanakan.

---

## Base URL

```
http://localhost:8000
```

---

## API Reference

### 1. Health Check

Mengecek status kesehatan server.

- **URL**: `/`
- **Method**: `GET`
- **Response `200 OK`**:
  ```json
  {
    "status": "success",
    "message": "Server berjalan normal",
    "data": {
      "status": "healthy",
      "app": "ChatAnalisis API",
      "version": "1.0.0"
    }
  }
  ```

---

### 2. Chat Analysis

Memproses file CSV chat, memotong data berdasarkan tanggal, menambahkan kolom indeks, dan menyimpan hasilnya ke MinIO dengan mekanisme auto-delete (1 hari).

- **URL**: `/analysis`
- **Method**: `POST`
- **Content-Type**: `multipart/form-data`

#### Parameters (Form Fields)

| Parameter    | Type          | Required | Description                                                                   |
| ------------ | ------------- | -------- | ----------------------------------------------------------------------------- |
| `file`       | File (Binary) | Ya       | File CSV yang berisi data percakapan chat.                                    |
| `session_id` | String        | Ya       | ID unik sesi analisis (akan digunakan sebagai nama file di MinIO).            |
| `startDate`  | String        | Tidak    | Tanggal awal pemotongan data (e.g. `YYYY-MM-DD` atau `YYYY-MM-DD HH:MM:SS`).  |
| `endDate`    | String        | Tidak    | Tanggal akhir pemotongan data (e.g. `YYYY-MM-DD` atau `YYYY-MM-DD HH:MM:SS`). |

#### Alur Pemrosesan

1. Membaca file CSV yang diunggah.
2. Mendeteksi kolom timestamp, pengirim, dan pesan (otomatis mengenali header variatif seperti `tanggal`, `timestamp`, `sender`, `pesan`, dll).
3. Melakukan pemotongan baris chat berdasarkan rentang `startDate` sampai `endDate` secara inklusif.
4. Membuat data CSV baru yang bersih dan terstruktur dengan kolom:
   - `index` (Sequential integer dimulai dari 0)
   - `timestamp` (ISO datetime formatted)
   - `pengirim` (Nama/identitas pengirim)
   - `pesan` (Isi pesan)
5. Menyimpan file CSV tersebut ke MinIO dengan penamaan `{session_id}.csv` di dalam bucket yang dikonfigurasi.
6. Mengonfigurasi lifecycle bucket MinIO agar file dihapus otomatis setelah 1 hari.

#### Response `200 OK`

```json
{
  "status": "success",
  "message": "Analisis selesai dan disimpan di MinIO",
  "data": {
    "session_id": "session-123",
    "filename": "session-123.csv",
    "bucket": "bertopic",
    "row_count": 250
  }
}
```

#### Error Responses

| Status Code          | Kondisi                           | JSON Body                                                                              |
| -------------------- | --------------------------------- | -------------------------------------------------------------------------------------- |
| `400 Bad Request`    | File bukan format CSV atau kosong | `{"status": "error", "message": "Format file tidak didukung. Harap upload file CSV."}` |
| `400 Bad Request`    | Kegagalan parsing CSV             | `{"status": "error", "message": "Gagal memproses CSV: [detail error]"}`                |
| `500 Internal Error` | Gagal upload ke MinIO             | `{"status": "error", "message": "Gagal mengunggah ke MinIO: [detail error]"}`          |
