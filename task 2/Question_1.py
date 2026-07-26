"""
Task 01: Library Management System (Advanced Version)
File: Question_1.py

Includes:
 1. User Authentication (Register/Login with password hashing)
 2. Book Issue & Return Logic
 3. Fine Calculation System ($1.00 / day overdue)
 4. File / Database Storage (SQLite DB + JSON File Backup)
 5. Search & Filter (by title, author, category, availability)
 6. Exception Handling (Custom exception hierarchy)
 7. Logging System (File logging to library.log + console)
 8. API Integration (Open Library REST API lookup)
"""

import os
import json
import sqlite3
import logging
import requests
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

# ==============================================================================
# 7. LOGGING SYSTEM
# ==============================================================================
LOG_FILE = "library.log"

def setup_logging():
    logger = logging.getLogger("LibrarySystem")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        
        file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        file_handler.setFormatter(formatter)
        
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    return logger

logger = setup_logging()

# ==============================================================================
# 6. CUSTOM EXCEPTION HANDLING
# ==============================================================================
class LibraryException(Exception):
    """Base Exception for Library System."""
    pass

class AuthenticationError(LibraryException):
    """Raised when authentication fails."""
    pass

class UserAlreadyExistsException(LibraryException):
    """Raised when user already exists."""
    pass

class BookNotFoundException(LibraryException):
    """Raised when book is not found."""
    pass

class BookNotAvailableException(LibraryException):
    """Raised when book has no available copies."""
    pass

class BorrowLimitExceededException(LibraryException):
    """Raised when user exceeds maximum allowed borrows."""
    pass

class OutstandingFineException(LibraryException):
    """Raised when user checkout is blocked due to unpaid fines."""
    pass

class BookAlreadyExistsException(LibraryException):
    """Raised when attempting to add a book with an existing ISBN."""
    pass

# ==============================================================================
# 4. DATABASE & FILE STORAGE MANAGER
# ==============================================================================
class LibraryDatabase:
    def __init__(self, db_path="library.db"):
        self.db_path = db_path
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                role TEXT CHECK(role IN ('ADMIN', 'MEMBER')) DEFAULT 'MEMBER'
            )
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                isbn TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                category TEXT NOT NULL,
                total_copies INTEGER DEFAULT 1,
                available_copies INTEGER DEFAULT 1
            )
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS borrow_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                book_id INTEGER NOT NULL,
                issue_date TEXT NOT NULL,
                due_date TEXT NOT NULL,
                return_date TEXT,
                status TEXT CHECK(status IN ('ISSUED', 'RETURNED')) DEFAULT 'ISSUED'
            )
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS fines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                borrow_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                status TEXT CHECK(status IN ('UNPAID', 'PAID')) DEFAULT 'UNPAID'
            )
            """)
            conn.commit()

    # 1. USER AUTHENTICATION
    def register_user(self, username, password, full_name, role="MEMBER"):
        pwd_hash = generate_password_hash(password)
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO users (username, password_hash, full_name, role) VALUES (?, ?, ?, ?)",
                    (username, pwd_hash, full_name, role)
                )
                user_id = cursor.lastrowid
                conn.commit()
            logger.info(f"User Registered: '{username}' (Role: {role})")
            return user_id
        except sqlite3.IntegrityError:
            logger.warning(f"Registration Error: Username '{username}' already exists.")
            raise UserAlreadyExistsException(f"Username '{username}' already exists.")

    def login_user(self, username, password):
        with self.get_connection() as conn:
            user = conn.cursor().execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            if not user or not check_password_hash(user["password_hash"], password):
                logger.warning(f"Authentication Failed for username '{username}'")
                raise AuthenticationError("Invalid username or password.")
            
            logger.info(f"User Logged In Successfully: '{username}'")
            return dict(user)

    # 5. SEARCH & FILTER
    def add_book(self, isbn, title, author, category, total_copies=1):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT INTO books (isbn, title, author, category, total_copies, available_copies)
                VALUES (?, ?, ?, ?, ?, ?)
                """, (isbn, title, author, category, total_copies, total_copies))
                book_id = cursor.lastrowid
                conn.commit()
            logger.info(f"Book Added: '{title}' (ISBN: {isbn})")
            return book_id
        except sqlite3.IntegrityError:
            logger.warning(f"Book with ISBN '{isbn}' already exists.")
            raise BookAlreadyExistsException(f"Book with ISBN '{isbn}' already exists.")

    def search_books(self, query="", category="", available_only=False):
        sql = "SELECT * FROM books WHERE 1=1"
        params = []

        if query:
            q = f"%{query}%"
            sql += " AND (title LIKE ? OR author LIKE ? OR isbn LIKE ?)"
            params.extend([q, q, q])

        if category:
            sql += " AND category = ?"
            params.append(category)

        if available_only:
            sql += " AND available_copies > 0"

        with self.get_connection() as conn:
            rows = conn.cursor().execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    # 2. BOOK ISSUE & RETURN & 3. FINE CALCULATION
    def issue_book(self, user_id, book_id, borrow_days=14):
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Check book availability
            book = cursor.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
            if not book:
                raise BookNotFoundException("Book not found.")
            if book["available_copies"] <= 0:
                logger.warning(f"Issue Failed: Book '{book['title']}' is out of stock.")
                raise BookNotAvailableException(f"'{book['title']}' is currently out of stock.")

            # Check user max active borrow limit (Max 3)
            active_count = cursor.execute(
                "SELECT COUNT(*) as c FROM borrow_records WHERE user_id = ? AND status = 'ISSUED'", (user_id,)
            ).fetchone()["c"]
            if active_count >= 3:
                logger.warning(f"Issue Failed: User ID {user_id} exceeded borrow limit.")
                raise BorrowLimitExceededException("Maximum borrow limit (3 books) reached.")

            # Check unpaid fines threshold ($15.00)
            unpaid_total = cursor.execute(
                "SELECT COALESCE(SUM(amount), 0) as total FROM fines WHERE user_id = ? AND status = 'UNPAID'", (user_id,)
            ).fetchone()["total"]
            if unpaid_total >= 15.0:
                logger.warning(f"Issue Failed: User ID {user_id} has unpaid fines ${unpaid_total:.2f}.")
                raise OutstandingFineException(f"Checkout blocked. Outstanding unpaid fine: ${unpaid_total:.2f}")

            issue_dt = datetime.now()
            due_dt = issue_dt + timedelta(days=borrow_days)
            issue_str = issue_dt.strftime("%Y-%m-%d %H:%M:%S")
            due_str = due_dt.strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute("""
            INSERT INTO borrow_records (user_id, book_id, issue_date, due_date, status)
            VALUES (?, ?, ?, ?, 'ISSUED')
            """, (user_id, book_id, issue_str, due_str))
            borrow_id = cursor.lastrowid

            cursor.execute("UPDATE books SET available_copies = available_copies - 1 WHERE id = ?", (book_id,))
            conn.commit()

        logger.info(f"Book Issued: Borrow ID {borrow_id} (Book: '{book['title']}', User ID: {user_id})")
        return {"borrow_id": borrow_id, "due_date": due_str}

    def return_book(self, borrow_id, daily_fine_rate=1.00):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            record = cursor.execute("SELECT * FROM borrow_records WHERE id = ?", (borrow_id,)).fetchone()
            if not record or record["status"] == "RETURNED":
                raise LibraryException("Invalid or already returned borrow record.")

            return_dt = datetime.now()
            return_str = return_dt.strftime("%Y-%m-%d %H:%M:%S")
            due_dt = datetime.strptime(record["due_date"], "%Y-%m-%d %H:%M:%S")

            # Fine calculation: $1.00 per overdue day
            overdue_days = max(0, (return_dt.date() - due_dt.date()).days)
            fine_amount = overdue_days * daily_fine_rate

            cursor.execute("UPDATE borrow_records SET return_date = ?, status = 'RETURNED' WHERE id = ?", (return_str, borrow_id))
            cursor.execute("UPDATE books SET available_copies = available_copies + 1 WHERE id = ?", (record["book_id"],))

            if fine_amount > 0:
                cursor.execute("""
                INSERT INTO fines (borrow_id, user_id, amount, status)
                VALUES (?, ?, ?, 'UNPAID')
                """, (borrow_id, record["user_id"], fine_amount))

            conn.commit()

        logger.info(f"Book Returned: Borrow ID {borrow_id} | Overdue Days: {overdue_days} | Fine: ${fine_amount:.2f}")
        return {"borrow_id": borrow_id, "overdue_days": overdue_days, "fine_amount": fine_amount}

    # 4. JSON FILE STORAGE BACKUP EXPORT
    def export_backup_to_json(self, file_path="catalog_backup.json"):
        with self.get_connection() as conn:
            books = [dict(r) for r in conn.cursor().execute("SELECT * FROM books").fetchall()]
            users = [dict(r) for r in conn.cursor().execute("SELECT id, username, full_name, role FROM users").fetchall()]
            borrows = [dict(r) for r in conn.cursor().execute("SELECT * FROM borrow_records").fetchall()]
            fines = [dict(r) for r in conn.cursor().execute("SELECT * FROM fines").fetchall()]

        backup_data = {
            "exported_at": datetime.now().isoformat(),
            "users": users,
            "books": books,
            "borrow_records": borrows,
            "fines": fines
        }

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, indent=2)

        logger.info(f"File Storage Backup Exported to '{file_path}'")
        return file_path

# ==============================================================================
# 8. API INTEGRATION (OPEN LIBRARY REST API)
# ==============================================================================
def search_open_library_api(query):
    """Integrates with Open Library REST API to fetch book details."""
    logger.info(f"API Integration: Querying Open Library for '{query}'")
    url = "https://openlibrary.org/search.json"
    try:
        res = requests.get(url, params={"q": query, "limit": 3}, timeout=5)
        if res.status_code == 200:
            docs = res.json().get("docs", [])
            results = []
            for d in docs:
                title = d.get("title", "Unknown")
                authors = ", ".join(d.get("author_name", ["Unknown"]))
                isbns = d.get("isbn", ["N/A"])
                results.append({"title": title, "author": authors, "isbn": isbns[0]})
            logger.info(f"API Integration: Retrieved {len(results)} books.")
            return results
    except Exception as e:
        logger.error(f"API Integration Error: {str(e)}")
    return []

# ==============================================================================
# TO THE POINT DEMONSTRATION MAIN EXECUTABLE
# ==============================================================================
if __name__ == "__main__":
    print("\n=======================================================")
    print("  TASK 01: LIBRARY MANAGEMENT SYSTEM (ADVANCED VERSION)")
    print("=======================================================\n")

    db = LibraryDatabase("demo_library.db")

    # 1. USER AUTHENTICATION
    print("--- 1. USER AUTHENTICATION ---")
    try:
        user_id = db.register_user("john_dev", "secret123", "John Dev", role="MEMBER")
        print(f"Registered User 'john_dev' with ID: {user_id}")
    except UserAlreadyExistsException:
        print("User 'john_dev' already registered.")

    user = db.login_user("john_dev", "secret123")
    print(f"Logged In User: {user['full_name']} (Role: {user['role']})\n")

    # 5. SEARCH & FILTER
    print("--- 2. BOOK CATALOG SEARCH & FILTER ---")
    try:
        db.add_book("978-0132350884", "Clean Code", "Robert C. Martin", "Technology", total_copies=2)
    except BookAlreadyExistsException:
        pass

    try:
        db.add_book("978-0451524935", "1984", "George Orwell", "Fiction", total_copies=1)
    except BookAlreadyExistsException:
        pass

    all_books = db.search_books()
    print(f"Catalog contains {len(all_books)} book(s):")
    for b in all_books:
        print(f" - [{b['isbn']}] '{b['title']}' by {b['author']} (Category: {b['category']} | Available: {b['available_copies']}/{b['total_copies']})")
    print()

    # 2. BOOK ISSUE & RETURN
    print("--- 3. BOOK ISSUE & RETURN ---")
    book_id = all_books[0]["id"]
    issue_res = db.issue_book(user["id"], book_id)
    print(f"Issued '{all_books[0]['title']}' to {user['username']}. Due Date: {issue_res['due_date'][:10]}")

    return_res = db.return_book(issue_res["borrow_id"])
    print(f"Returned Book Record #{return_res['borrow_id']}. Overdue Days: {return_res['overdue_days']} | Fine Amount: ${return_res['fine_amount']:.2f}\n")

    # 6. EXCEPTION HANDLING DEMONSTRATION
    print("--- 4. EXCEPTION HANDLING TEST ---")
    try:
        # Attempting to login with incorrect password
        db.login_user("john_dev", "wrong_password")
    except AuthenticationError as e:
        print(f"Caught Expected Exception: [AuthenticationError] -> {e}\n")

    # 4. FILE / DATABASE STORAGE BACKUP
    print("--- 5. FILE STORAGE BACKUP EXPORT ---")
    backup_file = db.export_backup_to_json("library_backup.json")
    print(f"Database Snapshot Exported to JSON File: '{backup_file}'\n")

    # 8. API INTEGRATION LOOKUP
    print("--- 6. OPEN LIBRARY API INTEGRATION ---")
    api_results = search_open_library_api("Python")
    print("Fetched External Books from Open Library API:")
    for item in api_results:
        print(f" - [{item['isbn']}] '{item['title']}' by {item['author']}")

    print("\n=======================================================")
    print("  ALL OPERATIONS COMPLETED SUCCESSFULLY!")
    print(f"  Check '{LOG_FILE}' for system logging output.")
    print("=======================================================\n")
