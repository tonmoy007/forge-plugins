# Data Model — Todo API

## users

| Column       | Type                     | Constraints              |
|--------------|--------------------------|--------------------------|
| id           | UUID                     | PRIMARY KEY, default gen_random_uuid() |
| email        | TEXT                     | NOT NULL, UNIQUE         |
| password_hash| TEXT                     | NOT NULL                 |
| created_at   | TIMESTAMPTZ              | NOT NULL, default now()  |
| updated_at   | TIMESTAMPTZ              | NOT NULL, default now()  |

Index: `users_email_idx` on `email` (supports login lookup).

## todos

| Column       | Type                     | Constraints              |
|--------------|--------------------------|--------------------------|
| id           | UUID                     | PRIMARY KEY, default gen_random_uuid() |
| user_id      | UUID                     | NOT NULL, FK → users(id) ON DELETE CASCADE |
| title        | TEXT                     | NOT NULL                 |
| description  | TEXT                     | nullable                 |
| due_date     | DATE                     | nullable                 |
| status       | TEXT                     | NOT NULL, CHECK IN ('open','done'), default 'open' |
| created_at   | TIMESTAMPTZ              | NOT NULL, default now()  |
| updated_at   | TIMESTAMPTZ              | NOT NULL, default now()  |

Indexes:
- `todos_user_id_idx` on `(user_id)` — all queries are user-scoped
- `todos_user_status_idx` on `(user_id, status)` — status filter
- `todos_user_due_date_idx` on `(user_id, due_date)` — date range filter

## refresh_tokens

| Column       | Type                     | Constraints              |
|--------------|--------------------------|--------------------------|
| id           | UUID                     | PRIMARY KEY              |
| user_id      | UUID                     | NOT NULL, FK → users(id) ON DELETE CASCADE |
| token_hash   | TEXT                     | NOT NULL, UNIQUE         |
| expires_at   | TIMESTAMPTZ              | NOT NULL                 |
| revoked_at   | TIMESTAMPTZ              | nullable                 |
| created_at   | TIMESTAMPTZ              | NOT NULL, default now()  |

Index: `refresh_tokens_token_hash_idx` on `token_hash`.

## Migration Strategy

Migrations are numbered sequentially (`001_initial_schema.sql`, `002_add_index.sql`, …)
and tracked in a `schema_migrations` table. The API container runs pending migrations
on startup before accepting traffic.
