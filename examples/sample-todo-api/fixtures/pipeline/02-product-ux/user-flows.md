# User Flows — Todo API

## Flow 1: Registration and First Todo

1. Client POST /auth/register → 201 + tokens
2. Client stores access_token and refresh_token
3. Client POST /todos with Authorization header → 201 + todo item
4. Client GET /todos → 200 + array containing new item

## Flow 2: Token Refresh

1. Client detects 401 on any request
2. Client POST /auth/refresh with refresh_token → 200 + new token pair
3. Client retries original request with new access_token
4. Old refresh_token is invalidated (rotation)

## Flow 3: Filtered Todo List

1. Client GET /todos?status=open → 200 + open todos
2. Client GET /todos?due_date=2026-05-01..2026-05-31 → 200 + todos in range
3. Client GET /todos?status=open&due_date=2026-05-01..2026-05-31 → intersection

## Flow 4: Rate Limit Hit

1. Client sends > 10 POST /auth/login in 60s → 429 + Retry-After header
2. Client waits Retry-After seconds
3. Client retries → 200

## Error Handling Conventions

- 400: validation failure (body contains `errors` array with field names)
- 401: expired/invalid access_token
- 403: valid token but forbidden action (should not occur in v1 scope)
- 404: resource not found or belongs to another user
- 409: conflict (duplicate email)
- 429: rate limit exceeded
- 500: unexpected server error (request_id in response for tracing)
