import os
import socket
import mysql.connector
from mysql.connector import Error
from fastapi import FastAPI

app = FastAPI(title="API v2")

DB_HOST = os.getenv("DB_HOST", "mysql-0.mysql-service.mysql-ns.svc.cluster.local")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "rootpassword")
DB_NAME = os.getenv("DB_NAME", "testdb")

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

@app.get("/")
def read_root():
    """Return version, hostname, and IP of the pod."""
    hostname = socket.gethostname()
    try:
        ip = socket.gethostbyname(hostname)
    except:
        ip = "unknown"
    return {
        "version": "v2",
        "hostname": hostname,
        "ip": ip
    }

@app.get("/users")
def read_users():
    """Return list of users from MySQL database."""
    connection = get_db_connection()
    if connection is None:
        return {"error": "Database connection failed", "users": []}
    
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT id, username, email FROM users")
        users = cursor.fetchall()
        cursor.close()
        connection.close()
        return {"users": users}
    except Error as e:
        return {"error": str(e), "users": []}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
