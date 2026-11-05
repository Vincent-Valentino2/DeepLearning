-- PostgreSQL initialization script for Movie Recommendation & Popularity Prediction system

CREATE TABLE IF NOT EXISTS prediction_logs (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    release_year INT NOT NULL,
    runtime INT NOT NULL,
    budget BIGINT DEFAULT 0,
    original_language VARCHAR(10) NOT NULL,
    genres TEXT,
    predicted_probability FLOAT NOT NULL,
    is_popular BOOLEAN NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    model_architecture TEXT,
    poster_url TEXT
);

CREATE TABLE IF NOT EXISTS bookmarked_movies (
    id SERIAL PRIMARY KEY,
    movie_id INT,
    title VARCHAR(255) NOT NULL,
    poster_path TEXT,
    release_date VARCHAR(50),
    vote_average FLOAT,
    added_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Seed initial test sample
INSERT INTO prediction_logs (title, release_year, runtime, budget, original_language, genres, predicted_probability, is_popular)
VALUES ('Inception', 2010, 148, 160000000, 'en', 'Action, Science Fiction, Adventure', 0.96, TRUE)
ON CONFLICT DO NOTHING;
