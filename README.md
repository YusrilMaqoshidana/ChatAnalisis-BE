# ChatAnalisis API

FastAPI project dengan arsitektur **layered/clean architecture** — berisi API untuk **Upload File** dan **Get User** (dummy data).

## 📂 Struktur Project

```
ChatAnalisis/
├── app/
│   ├── main.py              # Entry point
│   ├── core/config.py       # Settings & konfigurasi
│   ├── models/user.py       # Pydantic schemas
│   ├── repositories/        # Data access layer (dummy data)
│   ├── services/            # Business logic
│   ├── api/v1/              # API routes (versioned)
│   └── utils/               # Helper functions
├── uploads/                 # Folder penyimpanan file
└── requirements.txt
```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd ChatAnalisis
pip install -r requirements.txt
```

### 2. Run Server

```bash
uvicorn app.main:app --reload
```

### 3. Buka API Docs

- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

## 📡 API Endpoints

| Method | Endpoint                        | Deskripsi             |
| ------ | ------------------------------- | --------------------- |
| `GET`  | `/`                             | Health check          |
| `GET`  | `/api/v1/users`                 | List semua user       |
| `GET`  | `/api/v1/users?search=budi`     | Cari user             |
| `GET`  | `/api/v1/users/{id}`            | Detail user by ID     |
| `POST` | `/api/v1/files/upload`          | Upload single file    |
| `POST` | `/api/v1/files/upload-multiple` | Upload multiple files |
| `GET`  | `/api/v1/files`                 | List uploaded files   |

## 🏗️ Arsitektur

```
Request → API Route → Service → Repository → Data Source
                         ↓
                       Utils (file handling, validation)
```

| Layer          | Tanggung Jawab                  |
| -------------- | ------------------------------- |
| **API Route**  | Terima request, return response |
| **Service**    | Business logic, validasi        |
| **Repository** | Akses data (dummy/database)     |
| **Model**      | Schema validasi (Pydantic)      |
| **Utils**      | Helper functions                |
