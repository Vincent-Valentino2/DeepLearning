# TMDB Movies Dataset (Kaggle)

Place your downloaded dataset file from Kaggle here:
`data/TMDB_movie_dataset_v11.csv`

Dataset Source: [TMDB Movies Dataset (2023 - 930k movies) by asaniczka](https://www.kaggle.com/datasets/asaniczka/tmdb-movies-dataset-2023-930k-movies/data)

### Expected Columns in CSV:
- `id`: TMDB Movie ID (int)
- `title`: Film Title (str)
- `vote_average`: User rating average (strictly excluded from model features)
- `vote_count`: Total ratings (strictly excluded from model features)
- `status`: Release status (e.g. Released)
- `release_date`: YYYY-MM-DD
- `revenue`: Box office gross
- `runtime`: Duration in minutes
- `budget`: Production budget in USD
- `original_language`: ISO-639-1 language code (e.g. `en`, `ko`, `ja`)
- `overview`: Synopsis
- `popularity`: Target metric (thresholded to binary: Top 25% Popular vs Kurang Populer; never used as input)
- `poster_path`: Relative poster path (e.g. `/1pdfLvkbY9ohJlCjQH2CZjjYVvJ.jpg`)
- `backdrop_path`: Relative backdrop path
- `genres`: Comma-separated genre strings

### How Posters are Displayed:
TMDB hosts images at:
- Poster URL: `https://image.tmdb.org/t/p/w500{poster_path}`
- High-res Poster: `https://image.tmdb.org/t/p/original{poster_path}`
- Backdrop URL: `https://image.tmdb.org/t/p/w1280{backdrop_path}`

### Running Preprocessing & Model Training:
```bash
python backend/data_processor.py
```
This script will:
1. Scan for `data/*.csv` (including `TMDB_movie_dataset_v11.csv`).
2. Clean and preprocess features (Multi-Hot Genres, Log1p Budget, Scaled Runtime & Year, Encoded Language).
3. Compute the 75th percentile popularity threshold.
4. Train an MLP Classifier (`MLPClassifier` with layers `128, 64, 32`).
5. Save model artifacts to `backend/models/` for real-time inference.
6. Build a lightweight search index in `data/movies_index.json` for fast autocomplete with poster paths.
