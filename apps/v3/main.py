import os
import socket
from typing import Optional, List
from datetime import datetime

import mysql.connector
from mysql.connector import Error
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, field_validator

app = FastAPI(
    title="API v3 - CRUD",
    description="Full CRUD API for user management with MySQL",
    version="3.0.0"
)

# ---------------------------------------------------------------------------
# Database configuration from environment variables
# ---------------------------------------------------------------------------
DB_HOST = os.getenv("DB_HOST", "mysql-0.mysql-service.mysql-ns.svc.cluster.local")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "rootpassword")
DB_NAME = os.getenv("DB_NAME", "testdb")


# ---------------------------------------------------------------------------
# Pydantic models for request/response validation
# ---------------------------------------------------------------------------
class UserCreate(BaseModel):
    """Schema for creating a new user."""
    username: str
    first_name: str
    last_name: Optional[str] = None
    email: str

    @field_validator("username")
    @classmethod
    def username_min_length(cls, v: str) -> str:
        if len(v.strip()) < 3:
            raise ValueError("Username must be at least 3 characters")
        return v.strip()

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if "@" not in v:
            raise ValueError("Invalid email format")
        return v.strip()


class UserUpdate(BaseModel):
    """Schema for fully updating a user (PUT)."""
    username: str
    first_name: str
    last_name: Optional[str] = None
    email: str


class UserPatch(BaseModel):
    """Schema for partially updating a user (PATCH). All fields optional."""
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None


class UserResponse(BaseModel):
    """Schema for user response."""
    id: int
    username: str
    first_name: str
    last_name: Optional[str] = None
    email: str


class UserListResponse(BaseModel):
    """Schema for paginated user list."""
    users: List[UserResponse]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------
def get_db_connection():
    """Create and return a MySQL database connection."""
    try:
        connection = mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None


def log_audit(action: str, user_id: Optional[int], details: str):
    """Log an audit trail entry. Fails silently if table doesn't exist."""
    connection = get_db_connection()
    if connection is None:
        return
    try:
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO audit_log (action, user_id, details) VALUES (%s, %s, %s)",
            (action, user_id, details)
        )
        connection.commit()
        cursor.close()
        connection.close()
    except Error:
        pass  # audit_log table might not exist, that's ok


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/")
def read_root():
    """Return version, hostname, and IP of the pod."""
    hostname = socket.gethostname()
    try:
        ip = socket.gethostbyname(hostname)
    except Exception:
        ip = "unknown"
    return {
        "version": os.getenv("API_VERSION", "v3"),
        "hostname": hostname,
        "ip": ip,
        "features": ["crud", "pagination", "audit"]
    }


@app.get("/users", response_model=UserListResponse)
def read_users(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search by username or email"),
    sort: Optional[str] = Query("id", description="Sort field: id, username, email"),
    order: Optional[str] = Query("asc", description="Sort order: asc or desc")
):
    """Return paginated list of users with optional search and sorting."""
    connection = get_db_connection()
    if connection is None:
        raise HTTPException(status_code=503, detail="Database connection failed")

    try:
        cursor = connection.cursor(dictionary=True)

        # Validate sort and order to prevent SQL injection
        allowed_sort_fields = ["id", "username", "email", "first_name", "last_name"]
        if sort not in allowed_sort_fields:
            sort = "id"
        if order not in ("asc", "desc"):
            order = "asc"

        # Build query with optional search filter
        where_clause = ""
        params: tuple = ()
        if search:
            where_clause = " WHERE username LIKE %s OR email LIKE %s "
            like_param = f"%{search}%"
            params = (like_param, like_param)

        # Get total count
        count_query = f"SELECT COUNT(*) as total FROM users{where_clause}"
        cursor.execute(count_query, params)
        total = cursor.fetchone()["total"]

        # Get paginated results
        offset = (page - 1) * page_size
        data_query = (
            f"SELECT id, username, first_name, last_name, email "
            f"FROM users{where_clause}"
            f" ORDER BY {sort} {order}"
            f" LIMIT %s OFFSET %s"
        )
        cursor.execute(data_query, params + (page_size, offset))
        users = cursor.fetchall()

        cursor.close()
        connection.close()

        return UserListResponse(
            users=users,
            total=total,
            page=page,
            page_size=page_size
        )

    except Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/users/{user_id}", response_model=UserResponse)
def read_user(user_id: int):
    """Return a single user by ID."""
    connection = get_db_connection()
    if connection is None:
        raise HTTPException(status_code=503, detail="Database connection failed")

    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, username, first_name, last_name, email FROM users WHERE id = %s",
            (user_id,)
        )
        user = cursor.fetchone()
        cursor.close()
        connection.close()

        if user is None:
            raise HTTPException(status_code=404, detail=f"User with id {user_id} not found")
        return user

    except HTTPException:
        raise
    except Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.post("/users", response_model=UserResponse, status_code=201)
def create_user(user: UserCreate):
    """Create a new user."""
    connection = get_db_connection()
    if connection is None:
        raise HTTPException(status_code=503, detail="Database connection failed")

    try:
        cursor = connection.cursor(dictionary=True)

        # Check if username already exists
        cursor.execute("SELECT id FROM users WHERE username = %s", (user.username,))
        if cursor.fetchone():
            cursor.close()
            connection.close()
            raise HTTPException(
                status_code=409,
                detail=f"User with username '{user.username}' already exists"
            )

        # Insert new user
        cursor.execute(
            "INSERT INTO users (username, first_name, last_name, email) VALUES (%s, %s, %s, %s)",
            (user.username, user.first_name, user.last_name, user.email)
        )
        connection.commit()

        # Fetch the created user
        new_id = cursor.lastrowid
        cursor.execute(
            "SELECT id, username, first_name, last_name, email FROM users WHERE id = %s",
            (new_id,)
        )
        created_user = cursor.fetchone()
        cursor.close()
        connection.close()

        log_audit("CREATE", new_id, f"Created user '{user.username}'")
        return created_user

    except HTTPException:
        raise
    except Error as e:
        if "Duplicate entry" in str(e):
            raise HTTPException(
                status_code=409,
                detail=f"User with username '{user.username}' already exists"
            )
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.put("/users/{user_id}", response_model=UserResponse)
def update_user(user_id: int, user: UserUpdate):
    """Fully update a user (all fields required)."""
    connection = get_db_connection()
    if connection is None:
        raise HTTPException(status_code=503, detail="Database connection failed")

    try:
        cursor = connection.cursor(dictionary=True)

        # Check user exists
        cursor.execute("SELECT id, username FROM users WHERE id = %s", (user_id,))
        existing = cursor.fetchone()
        if existing is None:
            cursor.close()
            connection.close()
            raise HTTPException(status_code=404, detail=f"User with id {user_id} not found")

        # Check username uniqueness (exclude current user)
        cursor.execute(
            "SELECT id FROM users WHERE username = %s AND id != %s",
            (user.username, user_id)
        )
        if cursor.fetchone():
            cursor.close()
            connection.close()
            raise HTTPException(
                status_code=409,
                detail=f"Username '{user.username}' is already taken"
            )

        # Update user
        cursor.execute(
            "UPDATE users SET username = %s, first_name = %s, last_name = %s, email = %s WHERE id = %s",
            (user.username, user.first_name, user.last_name, user.email, user_id)
        )
        connection.commit()

        # Fetch updated user
        cursor.execute(
            "SELECT id, username, first_name, last_name, email FROM users WHERE id = %s",
            (user_id,)
        )
        updated_user = cursor.fetchone()
        cursor.close()
        connection.close()

        log_audit("UPDATE", user_id, f"Updated user from '{existing['username']}' to '{user.username}'")
        return updated_user

    except HTTPException:
        raise
    except Error as e:
        if "Duplicate" in str(e):
            raise HTTPException(status_code=409, detail=f"Username '{user.username}' is already taken")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.patch("/users/{user_id}", response_model=UserResponse)
def partial_update_user(user_id: int, user: UserPatch):
    """Partially update a user (only provided fields are updated)."""
    connection = get_db_connection()
    if connection is None:
        raise HTTPException(status_code=503, detail="Database connection failed")

    try:
        cursor = connection.cursor(dictionary=True)

        # Check user exists
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        existing = cursor.fetchone()
        if existing is None:
            cursor.close()
            connection.close()
            raise HTTPException(status_code=404, detail=f"User with id {user_id} not found")

        # Build dynamic UPDATE query with only provided fields
        update_fields = {}
        if user.username is not None:
            # Check uniqueness
            cursor.execute(
                "SELECT id FROM users WHERE username = %s AND id != %s",
                (user.username, user_id)
            )
            if cursor.fetchone():
                cursor.close()
                connection.close()
                raise HTTPException(
                    status_code=409,
                    detail=f"Username '{user.username}' is already taken"
                )
            update_fields["username"] = user.username

        if user.first_name is not None:
            update_fields["first_name"] = user.first_name
        if user.last_name is not None:
            update_fields["last_name"] = user.last_name
        if user.email is not None:
            update_fields["email"] = user.email

        if not update_fields:
            cursor.close()
            connection.close()
            raise HTTPException(status_code=400, detail="No fields to update")

        # Build and execute dynamic query
        set_clause = ", ".join([f"{k} = %s" for k in update_fields.keys()])
        values = list(update_fields.values()) + [user_id]

        cursor.execute(
            f"UPDATE users SET {set_clause} WHERE id = %s",
            values
        )
        connection.commit()

        # Fetch updated user
        cursor.execute(
            "SELECT id, username, first_name, last_name, email FROM users WHERE id = %s",
            (user_id,)
        )
        updated_user = cursor.fetchone()
        cursor.close()
        connection.close()

        updated_fields = ", ".join(update_fields.keys())
        log_audit("PATCH", user_id, f"Updated fields: {updated_fields}")
        return updated_user

    except HTTPException:
        raise
    except Error as e:
        if "Duplicate" in str(e):
            raise HTTPException(status_code=409, detail="Username already taken")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: int):
    """Delete a user by ID. Returns 204 No Content."""
    connection = get_db_connection()
    if connection is None:
        raise HTTPException(status_code=503, detail="Database connection failed")

    try:
        cursor = connection.cursor(dictionary=True)

        # Check user exists
        cursor.execute("SELECT id, username FROM users WHERE id = %s", (user_id,))
        existing = cursor.fetchone()
        if existing is None:
            cursor.close()
            connection.close()
            raise HTTPException(status_code=404, detail=f"User with id {user_id} not found")

        # Delete user
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        connection.commit()
        cursor.close()
        connection.close()

        log_audit("DELETE", user_id, f"Deleted user '{existing['username']}'")
        return None  # 204 No Content

    except HTTPException:
        raise
    except Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/health/ready")
def health_ready():
    """Readiness probe endpoint - checks database connectivity."""
    connection = get_db_connection()
    if connection is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    connection.close()
    return {"status": "ready"}


@app.get("/health/live")
def health_live():
    """Liveness probe endpoint - simple process check."""
    return {"status": "alive"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
