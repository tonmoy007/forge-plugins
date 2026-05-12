# API Contracts — Todo API

Full OpenAPI spec in `openapi-spec.yaml`. This document summarises the key contracts.

## Authentication Endpoints

### POST /auth/register
Request: `{ "email": string, "password": string (min 8 chars) }`  
Response 201: `{ "access_token": string, "refresh_token": string, "token_type": "bearer" }`  
Response 409: `{ "type": "conflict", "detail": "email already registered" }`

### POST /auth/login
Request: `{ "email": string, "password": string }`  
Response 200: `{ "access_token": string, "refresh_token": string, "token_type": "bearer" }`  
Response 401: `{ "type": "unauthorized", "detail": "invalid credentials" }`  
Rate limit: 10 req/min/IP → 429

### POST /auth/refresh
Request: `{ "refresh_token": string }`  
Response 200: `{ "access_token": string, "refresh_token": string, "token_type": "bearer" }`  
Response 401: `{ "type": "unauthorized", "detail": "invalid or expired refresh token" }`  
Note: supplied refresh_token is immediately revoked; response contains new pair.

## Todo Endpoints (all require `Authorization: Bearer <access_token>`)

### GET /todos
Query params: `status` (open|done), `due_date_from` (YYYY-MM-DD), `due_date_to` (YYYY-MM-DD),
`cursor` (opaque string), `limit` (1–200, default 50)  
Response 200: `{ "items": [TodoItem], "next_cursor": string | null }`

### POST /todos
Request: `{ "title": string, "description"?: string, "due_date"?: YYYY-MM-DD }`  
Response 201: `TodoItem`

### GET /todos/:id
Response 200: `TodoItem`  
Response 404: `{ "type": "not_found" }` (same response for other user's items)

### PATCH /todos/:id
Request: partial `{ "title"?, "description"?, "due_date"?, "status"? }`  
Response 200: `TodoItem`

### DELETE /todos/:id
Response 204: no body

## TodoItem Schema

```json
{
  "id": "uuid",
  "title": "string",
  "description": "string | null",
  "due_date": "YYYY-MM-DD | null",
  "status": "open | done",
  "created_at": "ISO 8601",
  "updated_at": "ISO 8601"
}
```

## Common Error Shape (RFC 7807)

```json
{ "type": "string", "detail": "string", "request_id": "uuid" }
```
