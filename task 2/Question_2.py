"""
================================================================================
TASK 02: MULTI-LIBRARIAN CONCURRENT SYSTEM REDESIGN & IMPLEMENTATION
File: Question_2.py
================================================================================

--------------------------------------------------------------------------------
QUESTION 01 (HIGH LEVEL ANSWER): REDESIGN FOR MULTI-LIBRARIAN CONCURRENCY
--------------------------------------------------------------------------------

PROBLEM ANALYSIS (Single-Librarian vs. Multi-Librarian System):
---------------------------------------------------------------
The original single-librarian application (Question_1.py) operates under the assumption
that only one operation occurs at a time. When scaling to support multiple librarians 
accessing the system simultaneously across multiple workstations or API endpoints, 
the following critical concurrency bugs arise:

1. RACE CONDITIONS & OVER-ISSUING (LOST UPDATES):
   - Example: Book 'Clean Code' has 1 available copy. Librarian A and Librarian B both 
     query `available_copies` simultaneously. Both read `available_copies = 1`. Both proceed 
     to issue the book. Both execute `UPDATE books SET available_copies = available_copies - 1`.
   - Result: `available_copies` becomes -1 (or 0), but 2 different members received the same 
     physical physical book, causing real-world inventory mismatch.

2. DATABASE LOCK CONTENTION & THREAD UNSAFETY:
   - SQLite by default in rollback journal mode blocks all readers during a write operation.
   - Sharing a single `sqlite3.Connection` across multiple threads causes `sqlite3.ProgrammingError: 
     SQLite objects created in a thread can only be used in the same thread`.

3. LACK OF AUDIT TRAIL & ACCOUNTABILITY:
   - In a multi-librarian environment, operations must be attributed to the specific 
     librarian who performed the issue, return, or fine collection.

--------------------------------------------------------------------------------
SYSTEM REDESIGN ARCHITECTURE & SOLUTION STRATEGY:
--------------------------------------------------------------------------------

1. DATABASE-LEVEL CONCURRENCY CONTROL:
   a) Write-Ahead Logging (WAL Mode):
      - We enable `PRAGMA journal_mode=WAL;` which allows concurrent readers while a write 
        is occurring, significantly improving throughput for multi-librarian web apps.
   b) Atomic Database Transactions & Conditional Updates:
      - Instead of Read-then-Update in two separate steps, we execute atomic updates:
        `UPDATE books SET available_copies = available_copies - 1 WHERE id = ? AND available_copies > 0;`
      - By checking `cursor.rowcount == 1`, we guarantee that only one librarian's transaction 
        succeeds even if 50 librarians submit a checkout at the exact same millisecond.
   c) Optimistic Concurrency Control (OCC) / Versioning:
      - For complex multi-field updates, we maintain a `version` column on records.
        `UPDATE books SET title=?, version=version+1 WHERE id=? AND version=current_version;`
      - If another librarian modified the record in the interim, `rowcount` is 0, signaling 
        a conflict that triggers an explicit user retry.

2. APPLICATION SERVER & THREAD SAFETY ARCHITECTURE:
   a) Thread-Local Connection Factory:
      - Connections are scoped per-thread (`threading.local()`) or managed via a robust 
        Connection Pool (e.g. SQLAlchemy QueuePool), preventing cross-thread connection sharing.
   b) Retry Mechanism with Exponential Backoff:
      - In case of database lock collisions (`sqlite3.OperationalError: database is locked`), 
        the system automatically retries with randomized backoff delays.

3. AUDIT LOGGING & SESSION ATTRIBUTION:
   a) Schema Enhancement:
      - `borrow_records` table updated with `issued_by_librarian_id` and `returned_by_librarian_id`.
      - An `audit_logs` table records every action with timestamp, librarian ID, action type, 
        and payload for complete operational governance.
   b) Stateless JWT / Session Token Authentication:
      - Each HTTP request carries the authenticated librarian's identity.

================================================================================
"""

import os
import time
import json
import sqlite3
import logging
import threading
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

# ==============================================================================
# LOGGING SETUP
# ==============================================================================
LOG_FILE = "multi_librarian.log"

def setup_logging():
    logger = logging.getLogger("MultiLibrarianSystem")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        formatter = logging.Formatter("[%(asctime)s] [%(threadName)s] [%(levelname)s] - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        
        file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        file_handler.setFormatter(formatter)
        
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    return logger

logger = setup_logging()

# ==============================================================================
# CUSTOM EXCEPTIONS
# ==============================================================================
class LibraryException(Exception):
    pass

class AuthenticationError(LibraryException):
    pass

class UserAlreadyExistsException(LibraryException):
    pass

class BookNotFoundException(LibraryException):
    pass

class BookNotAvailableException(LibraryException):
    pass

class BorrowLimitExceededException(LibraryException):
    pass

class OutstandingFineException(LibraryException):
    pass

class BookAlreadyExistsException(LibraryException):
    pass

class ConcurrencyConflictException(LibraryException):
    pass

# ==============================================================================
# RETRY DECORATOR FOR DB LOCK CONTENTION
# ==============================================================================
def retry_on_db_lock(max_retries=5, initial_delay=0.05):
    """Decorator to retry database transactions on SQLite lock contention."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            delay = initial_delay
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except sqlite3.OperationalError as e:
                    if "locked" in str(e).lower() or "busy" in str(e).lower():
                        if attempt == max_retries:
                            logger.error(f"DB Lock retry limit reached for {func.__name__}: {e}")
                            raise ConcurrencyConflictException("System is busy. Please try again.")
                        sleep_time = delay + random.uniform(0.01, 0.05)
                        logger.warning(f"DB Locked in {func.__name__}. Retrying attempt {attempt}/{max_retries} in {sleep_time:.3f}s...")
                        time.sleep(sleep_time)
                        delay *= 2
                    else:
                        raise
        return wrapper
    return decorator

# ==============================================================================
# THREAD-SAFE CONCURRENT DATABASE MANAGER
# ==============================================================================
class ConcurrentLibraryDatabase:
    """
    Thread-safe Database Manager designed for simultaneous multi-librarian access.
    Features:
     - SQLite Write-Ahead Logging (WAL) mode
     - Thread-local connection pool
     - Strict atomic updates to prevent race conditions
     - Full audit logging attributed to individual librarians
    """
    def __init__(self, db_path="concurrent_library.db"):
        self.db_path = db_path
        self._local = threading.local()
        self.init_db()

    def get_connection(self):
        """Returns a thread-local SQLite connection configured for concurrency."""
        if not hasattr(self._local, "connection") or self._local.connection is None:
            conn = sqlite3.connect(self.db_path, timeout=15.0)
            conn.row_factory = sqlite3.Row
            # Enable WAL mode for multi-reader multi-writer concurrency
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA busy_timeout=10000;")
            self._local.connection = conn
        return self._local.connection

    def close_connection(self):
        """Closes thread-local connection if open."""
        if hasattr(self._local, "connection") and self._local.connection is not None:
            self._local.connection.close()
            self._local.connection = None

    def init_db(self):
        """Initializes database schema with WAL mode and multi-librarian tracking."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        cursor = conn.cursor()

        # Users table (Librarians & Members)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT CHECK(role IN ('ADMIN', 'LIBRARIAN', 'MEMBER')) DEFAULT 'MEMBER',
            created_at TEXT NOT NULL
        )
        """)

        # Books table with optimistic locking version field
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            isbn TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            category TEXT NOT NULL,
            total_copies INTEGER DEFAULT 1,
            available_copies INTEGER DEFAULT 1,
            version INTEGER DEFAULT 1
        )
        """)

        # Borrow records with Librarian attribution
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS borrow_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            book_id INTEGER NOT NULL,
            issue_date TEXT NOT NULL,
            due_date TEXT NOT NULL,
            return_date TEXT,
            status TEXT CHECK(status IN ('ISSUED', 'RETURNED')) DEFAULT 'ISSUED',
            issued_by_librarian_id INTEGER NOT NULL,
            returned_by_librarian_id INTEGER,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(book_id) REFERENCES books(id),
            FOREIGN KEY(issued_by_librarian_id) REFERENCES users(id),
            FOREIGN KEY(returned_by_librarian_id) REFERENCES users(id)
        )
        """)

        # Fines table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS fines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            borrow_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            status TEXT CHECK(status IN ('UNPAID', 'PAID')) DEFAULT 'UNPAID',
            collected_by_librarian_id INTEGER,
            paid_at TEXT
        )
        """)

        # Audit logs for multi-librarian governance
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            librarian_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            details TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
        """)

        conn.commit()
        conn.close()

    def log_audit(self, conn, librarian_id, action, details):
        """Records an audit log entry within an active transaction."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.cursor().execute("""
        INSERT INTO audit_logs (librarian_id, action, details, timestamp)
        VALUES (?, ?, ?, ?)
        """, (librarian_id, action, json.dumps(details), now_str))

    # --------------------------------------------------------------------------
    # USER / LIBRARIAN REGISTRATION & LOGIN
    # --------------------------------------------------------------------------
    @retry_on_db_lock()
    def register_user(self, username, password, full_name, role="MEMBER"):
        pwd_hash = generate_password_hash(password)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (username, password_hash, full_name, role, created_at) VALUES (?, ?, ?, ?, ?)",
                (username, pwd_hash, full_name, role, now_str)
            )
            user_id = cursor.lastrowid
            conn.commit()
            logger.info(f"Registered User/Librarian: '{username}' [Role: {role}, ID: {user_id}]")
            return user_id
        except sqlite3.IntegrityError:
            raise UserAlreadyExistsException(f"Username '{username}' already exists.")

    def login_user(self, username, password):
        conn = self.get_connection()
        user = conn.cursor().execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if not user or not check_password_hash(user["password_hash"], password):
            raise AuthenticationError("Invalid username or password.")
        return dict(user)

    # --------------------------------------------------------------------------
    # BOOK MANAGEMENT
    # --------------------------------------------------------------------------
    @retry_on_db_lock()
    def add_book(self, librarian_id, isbn, title, author, category, total_copies=1):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO books (isbn, title, author, category, total_copies, available_copies, version)
            VALUES (?, ?, ?, ?, ?, ?, 1)
            """, (isbn, title, author, category, total_copies, total_copies))
            book_id = cursor.lastrowid
            self.log_audit(conn, librarian_id, "ADD_BOOK", {"book_id": book_id, "isbn": isbn, "title": title})
            conn.commit()
            logger.info(f"Book Added by Librarian #{librarian_id}: '{title}' (Copies: {total_copies})")
            return book_id
        except sqlite3.IntegrityError:
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

        conn = self.get_connection()
        rows = conn.cursor().execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    # --------------------------------------------------------------------------
    # THREAD-SAFE CONCURRENT BOOK ISSUE LOGIC (PREVENTS RACE CONDITIONS)
    # --------------------------------------------------------------------------
    @retry_on_db_lock()
    def issue_book_concurrent(self, librarian_id, user_id, book_id, borrow_days=14):
        """
        Issues a book atomically. Guarantees zero over-allocation under heavy concurrency.
        Uses an atomic UPDATE condition: available_copies > 0
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        # Start immediate transaction for write isolation
        cursor.execute("BEGIN IMMEDIATE")

        try:
            # 1. Check user exists
            user = cursor.execute("SELECT id, username FROM users WHERE id = ?", (user_id,)).fetchone()
            if not user:
                raise LibraryException(f"User ID {user_id} does not exist.")

            # 2. Check active borrows limit (Max 3)
            active_count = cursor.execute(
                "SELECT COUNT(*) as c FROM borrow_records WHERE user_id = ? AND status = 'ISSUED'", (user_id,)
            ).fetchone()["c"]
            if active_count >= 3:
                raise BorrowLimitExceededException(f"User '{user['username']}' reached max borrow limit (3 books).")

            # 3. Check unpaid fines threshold ($15.00)
            unpaid_total = cursor.execute(
                "SELECT COALESCE(SUM(amount), 0) as total FROM fines WHERE user_id = ? AND status = 'UNPAID'", (user_id,)
            ).fetchone()["total"]
            if unpaid_total >= 15.0:
                raise OutstandingFineException(f"User checkout blocked. Unpaid fine: ${unpaid_total:.2f}")

            # 4. ATOMIC BOOK DECREMENT & CONCURRENCY CHECK
            # We decrement available_copies ONLY IF available_copies > 0.
            cursor.execute("""
            UPDATE books 
            SET available_copies = available_copies - 1, 
                version = version + 1 
            WHERE id = ? AND available_copies > 0
            """, (book_id,))

            if cursor.rowcount == 0:
                # Either book doesn't exist OR available_copies was 0 (another thread grabbed the last copy)
                book = cursor.execute("SELECT title, available_copies FROM books WHERE id = ?", (book_id,)).fetchone()
                if not book:
                    raise BookNotFoundException("Book not found.")
                else:
                    raise BookNotAvailableException(f"Book '{book['title']}' is currently out of stock.")

            # 5. Insert Borrow Record with Librarian Attribution
            issue_dt = datetime.now()
            due_dt = issue_dt + timedelta(days=borrow_days)
            issue_str = issue_dt.strftime("%Y-%m-%d %H:%M:%S")
            due_str = due_dt.strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute("""
            INSERT INTO borrow_records (user_id, book_id, issue_date, due_date, status, issued_by_librarian_id)
            VALUES (?, ?, ?, ?, 'ISSUED', ?)
            """, (user_id, book_id, issue_str, due_str, librarian_id))
            borrow_id = cursor.lastrowid

            # 6. Audit log
            self.log_audit(conn, librarian_id, "ISSUE_BOOK", {
                "borrow_id": borrow_id, "user_id": user_id, "book_id": book_id
            })

            conn.commit()
            logger.info(f"SUCCESS: Librarian #{librarian_id} issued Borrow #{borrow_id} (User: {user_id}, Book: {book_id})")
            return {"borrow_id": borrow_id, "due_date": due_str}

        except Exception:
            conn.rollback()
            raise

    # --------------------------------------------------------------------------
    # THREAD-SAFE CONCURRENT BOOK RETURN LOGIC
    # --------------------------------------------------------------------------
    @retry_on_db_lock()
    def return_book_concurrent(self, librarian_id, borrow_id, daily_fine_rate=1.00):
        """Returns a book atomically and calculates fine, updating copies under transaction lock."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")

        try:
            record = cursor.execute("SELECT * FROM borrow_records WHERE id = ?", (borrow_id,)).fetchone()
            if not record or record["status"] == "RETURNED":
                raise LibraryException("Invalid or already returned borrow record.")

            return_dt = datetime.now()
            return_str = return_dt.strftime("%Y-%m-%d %H:%M:%S")
            due_dt = datetime.strptime(record["due_date"], "%Y-%m-%d %H:%M:%S")

            overdue_days = max(0, (return_dt.date() - due_dt.date()).days)
            fine_amount = overdue_days * daily_fine_rate

            # Update borrow record
            cursor.execute("""
            UPDATE borrow_records 
            SET return_date = ?, status = 'RETURNED', returned_by_librarian_id = ? 
            WHERE id = ?
            """, (return_str, librarian_id, borrow_id))

            # Increment available copies atomically
            cursor.execute("""
            UPDATE books 
            SET available_copies = available_copies + 1, version = version + 1 
            WHERE id = ?
            """, (record["book_id"],))

            if fine_amount > 0:
                cursor.execute("""
                INSERT INTO fines (borrow_id, user_id, amount, status)
                VALUES (?, ?, ?, 'UNPAID')
                """, (borrow_id, record["user_id"], fine_amount))

            self.log_audit(conn, librarian_id, "RETURN_BOOK", {
                "borrow_id": borrow_id, "overdue_days": overdue_days, "fine": fine_amount
            })

            conn.commit()
            logger.info(f"SUCCESS: Librarian #{librarian_id} returned Borrow #{borrow_id} (Fine: ${fine_amount:.2f})")
            return {"borrow_id": borrow_id, "overdue_days": overdue_days, "fine_amount": fine_amount}

        except Exception:
            conn.rollback()
            raise

    # --------------------------------------------------------------------------
    # FINE COLLECTION LOGIC
    # --------------------------------------------------------------------------
    @retry_on_db_lock()
    def collect_fine_concurrent(self, librarian_id, fine_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        try:
            fine = cursor.execute("SELECT * FROM fines WHERE id = ? AND status = 'UNPAID'", (fine_id,)).fetchone()
            if not fine:
                raise LibraryException("Fine record not found or already paid.")

            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
            UPDATE fines 
            SET status = 'PAID', collected_by_librarian_id = ?, paid_at = ? 
            WHERE id = ?
            """, (librarian_id, now_str, fine_id))

            self.log_audit(conn, librarian_id, "COLLECT_FINE", {"fine_id": fine_id, "amount": fine["amount"]})
            conn.commit()
            logger.info(f"SUCCESS: Librarian #{librarian_id} collected Fine #{fine_id} (${fine['amount']:.2f})")
            return True
        except Exception:
            conn.rollback()
            raise

    def get_audit_trail(self):
        conn = self.get_connection()
        rows = conn.cursor().execute("""
        SELECT a.id, u.username as librarian, a.action, a.details, a.timestamp 
        FROM audit_logs a 
        JOIN users u ON a.librarian_id = u.id 
        ORDER BY a.id ASC
        """).fetchall()
        return [dict(r) for r in rows]

# ==============================================================================
# MULTI-THREADED SIMULATION & STRESS TESTING
# ==============================================================================
def run_concurrency_demonstration():
    print("\n" + "=" * 75)
    print("  TASK 02: MULTI-LIBRARIAN CONCURRENT SYSTEM DEMONSTRATION")
    print("=" * 75 + "\n")

    db_filename = "demo_concurrent_library.db"
    if os.path.exists(db_filename):
        try:
            os.remove(db_filename)
        except OSError:
            pass

    db = ConcurrentLibraryDatabase(db_filename)

    # 1. SETUP LIBRARIANS AND MEMBERS
    print("--- 1. INITIALIZING LIBRARIANS AND MEMBERS ---")
    lib_alice = db.register_user("librarian_alice", "pass123", "Alice Smith", role="LIBRARIAN")
    lib_bob = db.register_user("librarian_bob", "pass123", "Bob Jones", role="LIBRARIAN")
    lib_charlie = db.register_user("librarian_charlie", "pass123", "Charlie Brown", role="LIBRARIAN")

    member_1 = db.register_user("student_dave", "pass123", "Dave Miller", role="MEMBER")
    member_2 = db.register_user("student_emma", "pass123", "Emma Watson", role="MEMBER")
    member_3 = db.register_user("student_frank", "pass123", "Frank Castle", role="MEMBER")
    member_4 = db.register_user("student_grace", "pass123", "Grace Hopper", role="MEMBER")
    member_5 = db.register_user("student_henry", "pass123", "Henry Ford", role="MEMBER")

    # 2. ADD BOOKS WITH LIMITED COPIES
    print("\n--- 2. CREATING BOOK CATALOG WITH CONSTRAINED INVENTORY ---")
    # Book A: 2 copies only
    book_hot = db.add_book(lib_alice, "978-0132350884", "Clean Architecture", "Robert C. Martin", "Technology", total_copies=2)
    # Book B: 5 copies
    book_python = db.add_book(lib_bob, "978-1449355739", "Learning Python", "Mark Lutz", "Technology", total_copies=5)

    print(f"Added 'Clean Architecture' (Book ID {book_hot}) with strictly 2 copies.")
    print(f"Added 'Learning Python' (Book ID {book_python}) with 5 copies.\n")

    # 3. STRESS TEST 1: SIMULTANEOUS CHECKOUT RACE CONDITION TEST
    # 5 Librarians trying to issue the SAME book (2 copies) to 5 different members simultaneously!
    print("--- 3. CONCURRENCY STRESS TEST 1: 5 SIMULTANEOUS CHECKOUTS FOR 2 COPIES ---")
    print("Explanation: 5 librarians submit issue requests for 'Clean Architecture' at the exact same millisecond.")
    print("Expected Outcome: Exactly 2 checkouts succeed, 3 checkout attempts fail safely with BookNotAvailableException.")

    librarians = [lib_alice, lib_bob, lib_charlie, lib_alice, lib_bob]
    members = [member_1, member_2, member_3, member_4, member_5]

    results = {"success": 0, "failed_stock": 0, "errors": 0}
    results_lock = threading.Lock()

    def librarian_checkout_worker(lib_id, user_id, book_id, worker_index):
        # Local connection per thread
        local_db = ConcurrentLibraryDatabase(db_filename)
        try:
            res = local_db.issue_book_concurrent(lib_id, user_id, book_id)
            with results_lock:
                results["success"] += 1
            print(f" [Thread #{worker_index}] Librarian #{lib_id} -> SUCCESS: Issued to User #{user_id} (Borrow ID #{res['borrow_id']})")
        except BookNotAvailableException as e:
            with results_lock:
                results["failed_stock"] += 1
            print(f" [Thread #{worker_index}] Librarian #{lib_id} -> REJECTED (Out of Stock): {e}")
        except Exception as e:
            with results_lock:
                results["errors"] += 1
            print(f" [Thread #{worker_index}] Librarian #{lib_id} -> ERROR: {e}")
        finally:
            local_db.close_connection()

    # Launch threads simultaneously
    threads = []
    start_time = time.time()
    for i in range(5):
        t = threading.Thread(
            target=librarian_checkout_worker, 
            args=(librarians[i], members[i], book_hot, i + 1),
            name=f"LibrarianThread-{i+1}"
        )
        threads.append(t)

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    elapsed = time.time() - start_time
    print(f"\nExecution Finished in {elapsed:.4f} seconds.")
    print(f"Summary Results: {results['success']} Succeeded | {results['failed_stock']} Rejected (Stock Exhausted) | {results['errors']} Errors")

    # 4. VERIFY INVENTORY INTEGRITY
    print("\n--- 4. DATA INTEGRITY VERIFICATION ---")
    catalog = db.search_books(query="Clean Architecture")
    book_state = catalog[0]
    print(f"Book 'Clean Architecture' Status:")
    print(f" - Total Copies: {book_state['total_copies']}")
    print(f" - Available Copies in DB: {book_state['available_copies']}")

    assert book_state['available_copies'] == 0, "CRITICAL CONCURRENCY BUG: Available copies should be 0!"
    assert results['success'] == 2, f"CRITICAL BUG: Expected exactly 2 successful borrows, got {results['success']}"
    print(" VERIFICATION PASSED: No over-allocation occurred! Stock maintained with 100% thread safety.\n")

    # 5. STRESS TEST 2: MIXED CONCURRENT READ, WRITE, ISSUE, AND RETURN
    print("--- 5. CONCURRENCY STRESS TEST 2: MIXED READ/WRITE WORKLOAD ---")
    print("Simulating 10 concurrent librarian operations (Issues, Returns, Catalog Searches)...")

    # First issue 3 copies of Learning Python to prepare return tests
    b1 = db.issue_book_concurrent(lib_alice, member_1, book_python)["borrow_id"]
    b2 = db.issue_book_concurrent(lib_bob, member_2, book_python)["borrow_id"]

    mixed_tasks_completed = 0
    mixed_lock = threading.Lock()

    def mixed_task_worker(task_id):
        nonlocal mixed_tasks_completed
        local_db = ConcurrentLibraryDatabase(db_filename)
        try:
            if task_id % 3 == 0:
                # Issue
                try:
                    local_db.issue_book_concurrent(lib_charlie, member_3, book_python)
                except LibraryException:
                    pass  # Domain rule block (e.g. limit reached or stock out)
            elif task_id % 3 == 1:
                # Return
                borrow_to_return = b1 if task_id == 1 else b2
                try:
                    local_db.return_book_concurrent(lib_alice, borrow_to_return)
                except LibraryException:
                    pass  # Already returned
            else:
                # Search
                local_db.search_books(query="Python")
            
            with mixed_lock:
                mixed_tasks_completed += 1
        finally:
            local_db.close_connection()

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(mixed_task_worker, i) for i in range(10)]
        for future in as_completed(futures):
            future.result()

    print(f" Successfully executed 10 concurrent mixed workload operations. Completed: {mixed_tasks_completed}/10.")

    # 6. MULTI-LIBRARIAN AUDIT TRAIL DISPLAY
    print("\n--- 6. MULTI-LIBRARIAN AUDIT TRAIL SAMPLE ---")
    audit_records = db.get_audit_trail()
    print(f"Total Audit Entries Recorded: {len(audit_records)}")
    print("First 5 Audit Logs:")
    for entry in audit_records[:5]:
        print(f" - [{entry['timestamp']}] [Librarian: {entry['librarian']}] Action: {entry['action']} | Payload: {entry['details']}")

    print("\n=======================================================")
    print("  ALL MULTI-LIBRARIAN CONCURRENCY TESTS PASSED!")
    print(f"  Check '{LOG_FILE}' for detailed concurrent thread logs.")
    print("=======================================================\n")

if __name__ == "__main__":
    run_concurrency_demonstration()
