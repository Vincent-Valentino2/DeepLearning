# TMDB Movie Popularity & Recommendation Platform

> **Proyek Studi Kasus Midterm Exam (UTS) - Rapid Application Deployment via Containers & CI/CD**

Aplikasi sistem prediksi popularitas film dan kurasi rekomendasi film berbasis Machine Learning / Deep Learning (Multilayer Perceptron - MLP Classifier) dengan arsitektur **3-Tier Microservices Container (Frontend, Backend, Database)** dan otomasi **Continuous Integration & Continuous Deployment (CI/CD)**.

---

## 🏗️ 1. Arsitektur 3 Container (Bobot 50 Poin)

Aplikasi telah dirancang memenuhi kriteria minimal **3 container terisolasi** yang saling terhubung dalam satu bridge network (`app_network`):

```
                        ┌───────────────────────────────────────────────┐
                        │              Host Machine / Client            │
                        └──────────────────────┬────────────────────────┘
                                               │ HTTP :3000 (Local: 5174)
                                               ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ Docker Network (app_network)                                                           │
│                                                                                        │
│   ┌──────────────────────────┐             ┌──────────────────────────┐                │
│   │  Container 1: FRONTEND   │             │   Container 2: BACKEND   │                │
│   │  React 19 + Vite         │  /api/*     │   FastAPI (Python 3.12)  │                │
│   │  Tailwind CSS            ├────────────►│   Scikit-Learn MLP Model │                │
│   │  Nginx Alpine Reverse    │             │   Port: 8001             │                │
│   │  Port: 80 (Host: 3000)   │             │   Healthcheck: /api/heal.│                │
│   └──────────────────────────┘             └────────────┬─────────────┘                │
│                                                         │                              │
│                                                         │ SQL (Port 5432)              │
│                                                         ▼                              │
│                                            ┌──────────────────────────┐                │
│                                            │  Container 3: DATABASE   │                │
│                                            │  PostgreSQL 16 Alpine    │                │
│                                            │  Persistent Volume pgdata│                │
│                                            │  Auto-migration init.sql │                │
│                                            └──────────────────────────┘                │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

1. **Container 1 (Frontend):**
   - **Teknologi:** React 19, TypeScript, Vite, Tailwind CSS v4, Lucide Icons.
   - **Multi-stage Build:** Dibuat menggunakan Node.js 22 Alpine, kemudian di-serve menggunakan Nginx Alpine ringan. Nginx juga bertindak sebagai reverse-proxy meneruskan request `/api/` ke container backend.
2. **Container 2 (Backend REST API & ML):**
   - **Teknologi:** Python 3.12, FastAPI, Uvicorn, Scikit-Learn, Pandas, NumPy, Joblib.
   - **Fungsi:** Menyediakan API health check (`/api/health`), pencarian film TMDB (`/api/movies/search`), dan kalkulasi prediksi probabilitas popularitas (`/api/predict`) berbasis model neural network MLP v2.0.
3. **Container 3 (Database):**
   - **Teknologi:** PostgreSQL 16 Alpine dengan persistent Docker Volume (`pgdata`).
   - **Fungsi:** Menyimpan log riwayat inferensi prediksi (`prediction_logs`) dan bookmark film favorit (`bookmarked_movies`). Diinisialisasi otomatis via `db/init.sql`.

---

## 🔄 2. Implementasi Pipeline CI/CD (Bobot 20 Poin)

Konfigurasi workflow otomatis terletak pada [`.github/workflows/ci-cd.yml`](.github/workflows/ci-cd.yml) menggunakan **GitHub Actions**:

* **Continuous Integration (CI):**
  - **Frontend Check:** Linting, TypeScript check, dan kompilasi Vite (`pnpm run build`).
  - **Backend Check:** Verifikasi environment Python 3.12, install requirements, serta validasi integritas model MLP Joblib.
  - **Container Build Test:** Menggunakan Docker Buildx untuk memastikan `Dockerfile.frontend` dan `Dockerfile.backend` lolos proses build image tanpa error.
* **Continuous Deployment (CD):**
  - Berjalan otomatis setelah seluruh tahapan CI sukses di branch `main`.
  - Mempersiapkan rilis deployment ke staging/production container.

---

## 🚀 3. Panduan Menjalankan Aplikasi

### Opsi A: Development Mode (Lokal tanpa Docker)

1. **Jalankan Backend (Terminal 1):**
   ```bash
   # Masuk virtualenv dan jalankan server FastAPI
   backend/.venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8001 --reload
   ```
   *Healthcheck backend:* `http://localhost:8001/api/health`

2. **Jalankan Frontend (Terminal 2):**
   ```bash
   pnpm install
   pnpm run dev
   ```
   *Akses web browser:* `http://localhost:5174/`

---

### Opsi B: Production Mode (3 Container via Docker Compose)

Pastikan Docker Desktop / Podman telah berjalan di komputer Anda, lalu jalankan:

```bash
# Build dan jalankan seluruh container (FE, BE, DB) di background
docker compose up --build -d

# Cek status ketiga container
docker compose ps

# Cek logs container
docker compose logs -f
```

* **Frontend:** Buka browser di `http://localhost:3000`
* **Backend API Docs (Swagger):** `http://localhost:8001/docs`
* **PostgreSQL:** Port `5432` (User: `deeplearning`, Database: `movierec_db`)

Untuk mematikan container:
```bash
docker compose down
```

---

## 📋 4. Panduan Push ke GitHub untuk Tim

> [!IMPORTANT]
> File dataset Kaggle (`.csv`) dan database lokal besar (`.db`) sudah otomatis di-ignore oleh `.gitignore` karena GitHub membatasi ukuran maksimal file **100MB**. Jangan pernah memaksa push file `.csv` atau `.db` mentah ke git.

Untuk melakukan push repositori ini ke GitHub kelompok:

1. Buat repository baru di GitHub (misal: `uts-deeplearning-cicd`).
2. Sambungkan remote repository dan push:
   ```bash
   # Tambahkan remote repository tim Anda
   git remote add origin https://github.com/<USERNAME_ATAU_ORG>/<NAMA_REPO>.git

   # Push branch main
   git push -u origin main
   ```

---

## 📹 5. Checklist Video Penjelasan (5 - 15 Menit) (20 Poin)

Rekomendasi alur presentasi video:
1. **Menit 0:00 - 02:00:** Perkenalan anggota kelompok dan deskripsi singkat aplikasi prediksi film.
2. **Menit 02:00 - 05:00:** Penjelasan arsitektur 3 container (Nginx Frontend, FastAPI Backend, PostgreSQL Database) serta bedah file `Dockerfile` dan `docker-compose.yml`.
3. **Menit 05:00 - 09:00:** Demonstrasi alur CI/CD pada tab **Actions** di GitHub (tunjukkan pipeline build test berjalan otomatis).
4. **Menit 09:00 - 13:00:** Demonstrasi live aplikasi di browser (input parameter film, prediksi MLP keluar, pengecekan data di container).
5. **Menit 13:00 - 15:00:** Kesimpulan dan penutup.
