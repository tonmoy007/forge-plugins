# Interface Spec — Todo API

## AuthService

```python
class AuthService:
    async def register(self, email: str, password: str) -> TokenPair:
        """Create user, hash password (bcrypt), return token pair.
        Raises DuplicateEmailError if email exists."""

    async def login(self, email: str, password: str) -> TokenPair:
        """Verify credentials, return token pair.
        Raises InvalidCredentialsError on mismatch."""

    async def refresh_token(self, token: str) -> TokenPair:
        """Validate refresh token, revoke it, return new pair.
        Raises InvalidTokenError if expired or revoked."""
```

## TodoService

```python
class TodoService:
    async def list(
        self,
        user_id: UUID,
        status: str | None,
        due_date_from: date | None,
        due_date_to: date | None,
        cursor: str | None,
        limit: int,
    ) -> Page[Todo]:
        """Return paginated todo list for user, applying filters."""

    async def create(self, user_id: UUID, data: TodoCreate) -> Todo:
        """Insert todo row, return created record."""

    async def get(self, user_id: UUID, todo_id: UUID) -> Todo:
        """Fetch single todo. Raises NotFoundError if absent or wrong owner."""

    async def update(self, user_id: UUID, todo_id: UUID, data: TodoUpdate) -> Todo:
        """Partial update. Raises NotFoundError if absent or wrong owner."""

    async def delete(self, user_id: UUID, todo_id: UUID) -> None:
        """Delete todo. Raises NotFoundError if absent or wrong owner."""
```

## Pydantic Models

```python
class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"

class TodoCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    due_date: date | None = None

class TodoUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    due_date: date | None = None
    status: Literal["open", "done"] | None = None

class Todo(BaseModel):
    id: UUID
    title: str
    description: str | None
    due_date: date | None
    status: Literal["open", "done"]
    created_at: datetime
    updated_at: datetime

class Page(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: str | None
```

## Error Types

```python
class DuplicateEmailError(Exception): ...
class InvalidCredentialsError(Exception): ...
class InvalidTokenError(Exception): ...
class NotFoundError(Exception): ...
```

All exceptions are caught in route handlers and mapped to RFC 7807 responses.
