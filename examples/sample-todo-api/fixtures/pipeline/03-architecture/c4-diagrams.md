# C4 Diagrams — Todo API

## Level 1: System Context

```
[User / API Client] --> [Todo API System] --> [Postgres Database]
```

External actors: any HTTP client (mobile app, CLI, web frontend).  
The system has no external service dependencies beyond Postgres.

## Level 2: Container Diagram

```
[HTTP Client]
    |
    v
[FastAPI Container :8000]
    | auth routes        | todo routes
    v                    v
[AuthService]       [TodoService]
    |                    |
    +--------------------+
              |
              v
    [asyncpg connection pool]
              |
              v
    [Postgres :5432]
       - users
       - todos
       - refresh_tokens
```

## Level 3: Component Diagram (FastAPI Container)

```
[Router]
  ├── [auth_router]
  │     ├── register_handler  → AuthService.register()
  │     ├── login_handler     → AuthService.login()
  │     └── refresh_handler   → AuthService.refresh_token()
  └── [todo_router]
        ├── list_handler      → TodoService.list(user_id, filters)
        ├── create_handler    → TodoService.create(user_id, data)
        ├── get_handler       → TodoService.get(user_id, todo_id)
        ├── update_handler    → TodoService.update(user_id, todo_id, data)
        └── delete_handler    → TodoService.delete(user_id, todo_id)

[Middleware stack]
  1. RequestIDMiddleware   — attaches request_id to context
  2. StructuredLogMiddleware — emits JSON log on response
  3── RateLimitMiddleware  — enforces per-IP limits on auth endpoints
  4. JWTAuthMiddleware     — validates Bearer token on protected routes
```

## Level 4: Code (not shown)

Code-level detail is in `pipeline/04-spec/interface-spec.md`.
