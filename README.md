# Poem Memorizer

A Flask web application that helps you memorise poems stored in a SQLite database.

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure your database path
cp .env.example .env
# Edit .env and set POEM_DB=/path/to/your/poem.db

# 3. Run
flask run
# or: python app.py
```

The app will automatically create the required tables (users, memorization_sessions,
verse_attempts) in your database on first run.

---

## Database design

### Existing tables (read-only by the app)

| Table      | Key columns |
|------------|-------------|
| `chapters` | id, name, order, type, verse_count |
| `verses`   | id, number, content, chapter_id |

### New tables added by this app

#### `users`
Stores registered user accounts.

| Column          | Type      | Notes                   |
|-----------------|-----------|-------------------------|
| `id`            | INTEGER PK| Auto-increment          |
| `username`      | TEXT      | Unique                  |
| `password_hash` | TEXT      | Werkzeug PBKDF2-SHA256  |
| `created_at`    | TIMESTAMP | UTC, default now        |

#### `memorization_sessions`
One row per practice attempt of a chapter by a user.

| Column         | Type      | Notes                                     |
|----------------|-----------|-------------------------------------------|
| `id`           | INTEGER PK| Auto-increment                            |
| `user_id`      | INTEGER   | FK → users.id                            |
| `chapter_id`   | INTEGER   | FK → chapters.id                         |
| `started_at`   | TIMESTAMP | Set when session is created               |
| `completed_at` | TIMESTAMP | Set when report is generated (NULL = WIP) |
| `total_score`  | REAL      | 0–100, average over all verse similarities|
| `grade`        | TEXT      | Letter grade (A+ … F)                    |

#### `verse_attempts`
One row per verse answered within a session.

| Column        | Type      | Notes                              |
|---------------|-----------|------------------------------------|
| `id`          | INTEGER PK| Auto-increment                     |
| `session_id`  | INTEGER   | FK → memorization_sessions.id      |
| `verse_id`    | INTEGER   | FK → verses.id                     |
| `user_input`  | TEXT      | Exactly what the user typed        |
| `similarity`  | REAL      | 0.0–1.0, word-level Ratcliff score |
| `attempted_at`| TIMESTAMP | UTC                                |

---

## Features

- **User accounts** – register / login / logout with hashed passwords.
- **Chapter selection** – choose any chapter from the poem.
- **Sequential verse practice** – enter each verse from memory.
- **Hint** – from verse 2 onwards the previous verse is shown as a hint.
- **Instant feedback** – word-by-word diff shows correct / missing / extra words.
- **Per-verse score** – percentage similarity shown after each verse.
- **End-of-chapter report** – grade (A+…F), per-verse breakdowns, diff for each verse.
- **Personal history** – last 10 runs for the same chapter are displayed in the report.
- **Persistent storage** – all results saved to the database.

---

## Grading scale

| Score   | Grade |
|---------|-------|
| ≥ 97%   | A+    |
| ≥ 93%   | A     |
| ≥ 90%   | A−    |
| ≥ 87%   | B+    |
| ≥ 83%   | B     |
| ≥ 80%   | B−    |
| ≥ 77%   | C+    |
| ≥ 73%   | C     |
| ≥ 70%   | C−    |
| ≥ 60%   | D     |
| < 60%   | F     |
