# ChatAnalisis API

FastAPI backend untuk analisis chat WhatsApp menggunakan BERTopic, MinIO, Redis, dan background processing.

## Arsitektur Saat Ini

- `POST /topics/train` menerima upload file lalu memulai background task.
- Progress job disimpan di Redis (TTL 24 jam).
- BERTopic model dimuat/disimpan ke MinIO.
- Jika model belum ada: `fit_transform()`.
- Jika model sudah ada: `partial_fit()`.
- Progress bisa dipantau via REST polling atau WebSocket progress stream.

## Quick Start

```bash
cd /home/usereal/Projects/Python/ChatAnalisis-BE
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

## Endpoint (Recommended)

- Health check: `GET /`
- Start training job: `POST /topics/train`
- Poll progress: `GET /topics/progress/{job_id}`
- Stream progress: `ws://localhost:8000/topics/ws/{job_id}`

## Request `POST /topics/train`

`multipart/form-data` fields:

- `file`: `.txt` atau `.zip`
- `timeframe`: `week | month | year` (kosong = train semua data)

Response:

```json
{
  "status": "success",
  "message": "Training started",
  "data": {
    "job_id": "uuid"
  }
}
```

## Response `GET /topics/progress/{job_id}`

```json
{
  "status": "success",
  "message": "Job progress",
  "data": {
    "job_id": "uuid",
    "status": "processing",
    "progress": 70,
    "message": "Updating BERTopic model"
  }
}
```

## WebSocket Progress Message `topics/ws/{job_id}`

```json
{"status": "processing", "message": "Training BERTopic", "data": {"job_id": "uuid", "progress": 50}}
{"status": "done", "message": "Training selesai", "data": {"job_id": "uuid", "progress": 100}}
{"status": "error", "message": "Pesan error", "data": {"job_id": "uuid"}}
```

## Progress Stages

- `5` validating upload
- `10` parsing
- `20` preprocessing
- `30` loading model MinIO
- `50` training
- `70` updating/finalizing
- `85` saving model
- `100` done
