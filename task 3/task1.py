"""
================================================================================
APTURA TECH SOLUTIONS - 1-Month Internship Program (Batch 02)
WEEK 03 - TASK 01: Employee Attendance & Payroll Automation System
File: task1.py

Objective:
Develop an enterprise-level Python application focusing on optimization,
automation, software architecture, and disaster recovery.

Included Modules in this single file:
1. Employee & Admin Login (SHA-256 Hashing, Hash-matching)
2. Password Reset / Forgot Password Mechanism
3. Dynamic Employee/Admin Registration (Role Selection + Admin Secret Code)
4. Attendance Management (Clock-in, Clock-out, Worked Hours, History)
5. Salary & Overtime Calculation (Base earnings, Tax Deductions, 1.5x Overtime)
6. Admin Payroll Modification (Edit Hourly Rates, Tax Rates, Departments)
7. Monthly Report Generation (Departmental & Company Summaries)
8. Export Reports (CSV and PDF Exporters)
9. Fault Tolerance & Recovery (Atomic File Writes, Corrupt DB Auto-Recovery)
================================================================================
"""

import os
import sys
import json
import csv
import hashlib
import shutil
from datetime import datetime, date
from typing import Dict, List, Optional, Any

# Optional ReportLab PDF library check
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


DATA_FILE = "payroll_database.json"
BACKUP_FILE = "payroll_database.json.bak"
ADMIN_SECRET_KEY = "ADMIN2026"  # Secret key for Admin operations & Password Resets


# ==============================================================================
# SECTION 1: SECURITY & DATA RECOVERY ENGINE
# ==============================================================================

def hash_password(password: str, salt: str = "aptura_salt_2026") -> str:
    """Hashes passwords using SHA-256 with a security salt."""
    return hashlib.sha256((password + salt).encode('utf-8')).hexdigest()

class DatabaseManager:
    """Manages database persistence with atomic file writes and corruption recovery."""

    @staticmethod
    def get_default_db() -> Dict[str, Any]:
        """Creates initial dataset with default Admin and Sample Employees."""
        return {
            "users": {
                "admin": {
                    "emp_id": "ADM001",
                    "username": "admin",
                    "password_hash": hash_password("admin123"),
                    "name": "System Administrator",
                    "role": "admin",
                    "department": "HR & Management",
                    "hourly_rate": 50.0,
                    "tax_rate": 0.15
                },
                "EMP101": {
                    "emp_id": "EMP101",
                    "username": "john_doe",
                    "password_hash": hash_password("emp123"),
                    "name": "John Doe",
                    "role": "employee",
                    "department": "Software Engineering",
                    "hourly_rate": 35.0,
                    "tax_rate": 0.12
                },
                "EMP102": {
                    "emp_id": "EMP102",
                    "username": "jane_smith",
                    "password_hash": hash_password("emp123"),
                    "name": "Jane Smith",
                    "role": "employee",
                    "department": "Quality Assurance",
                    "hourly_rate": 30.0,
                    "tax_rate": 0.10
                }
            },
            "attendance": [
                {
                    "emp_id": "EMP101",
                    "date": "2026-08-01",
                    "clock_in": "09:00:00",
                    "clock_out": "18:00:00",
                    "hours_worked": 9.0,
                    "status": "Present"
                },
                {
                    "emp_id": "EMP102",
                    "date": "2026-08-01",
                    "clock_in": "08:30:00",
                    "clock_out": "17:30:00",
                    "hours_worked": 9.0,
                    "status": "Present"
                }
            ]
        }

    @classmethod
    def load_data(cls) -> Dict[str, Any]:
        """Loads JSON data with automated recovery from corrupted files."""
        if not os.path.exists(DATA_FILE):
            data = cls.get_default_db()
            cls.save_data(data)
            return data

        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "users" not in data or "attendance" not in data:
                    raise ValueError("Database schema missing required keys.")
                return data
        except (json.JSONDecodeError, ValueError) as e:
            print(f"\n[WARNING] Database corruption detected ({e})!")
            print("[INFO] Attempting to recover from backup file...")
            if os.path.exists(BACKUP_FILE):
                try:
                    with open(BACKUP_FILE, "r", encoding="utf-8") as bf:
                        data = json.load(bf)
                        print("[SUCCESS] Database successfully restored from backup!")
                        cls.save_data(data)
                        return data
                except Exception as restore_err:
                    print(f"[ERROR] Backup restoration failed: {restore_err}")

            print("[CRITICAL] Re-initializing database to clean default state.")
            data = cls.get_default_db()
            cls.save_data(data)
            return data

    @classmethod
    def save_data(cls, data: Dict[str, Any]) -> bool:
        """Atomic write using temporary file swap to prevent file corruption on crash."""
        temp_file = DATA_FILE + ".tmp"
        try:
            if os.path.exists(DATA_FILE):
                shutil.copyfile(DATA_FILE, BACKUP_FILE)

            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)

            os.replace(temp_file, DATA_FILE)
            return True
        except Exception as e:
            print(f"[ERROR] Failed to save database atomically: {e}")
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass
            return False


# ==============================================================================
# SECTION 2: SALARY & OVERTIME CALCULATION ENGINE
# ==============================================================================

class PayrollEngine:
    """Computes worked hours, overtime multiplier, tax deductions, and net salary."""

    STANDARD_HOURS_PER_DAY = 8.0
    OVERTIME_MULTIPLIER = 1.5

    @classmethod
    def calculate_employee_payroll(cls, user_data: Dict[str, Any], attendance_records: List[Dict[str, Any]], month: Optional[str] = None) -> Dict[str, Any]:
        """Calculates regular hours, overtime hours, gross pay, tax deductions, and net pay."""
        total_hours = 0.0
        regular_hours = 0.0
        overtime_hours = 0.0

        filtered_records = []
        for rec in attendance_records:
            if rec.get("emp_id") == user_data["emp_id"]:
                if month:
                    if rec.get("date", "").startswith(month):
                        filtered_records.append(rec)
                else:
                    filtered_records.append(rec)

        for rec in filtered_records:
            hw = rec.get("hours_worked", 0.0)
            total_hours += hw
            if hw > cls.STANDARD_HOURS_PER_DAY:
                regular_hours += cls.STANDARD_HOURS_PER_DAY
                overtime_hours += (hw - cls.STANDARD_HOURS_PER_DAY)
            else:
                regular_hours += hw

        hourly_rate = user_data.get("hourly_rate", 25.0)
        regular_pay = regular_hours * hourly_rate
        overtime_pay = overtime_hours * (hourly_rate * cls.OVERTIME_MULTIPLIER)
        gross_pay = regular_pay + overtime_pay
        
        tax_rate = user_data.get("tax_rate", 0.10)
        tax_deduction = gross_pay * tax_rate
        net_pay = gross_pay - tax_deduction

        return {
            "emp_id": user_data["emp_id"],
            "name": user_data["name"],
            "department": user_data["department"],
            "total_days_present": len(filtered_records),
            "total_hours": round(total_hours, 2),
            "regular_hours": round(regular_hours, 2),
            "overtime_hours": round(overtime_hours, 2),
            "hourly_rate": round(hourly_rate, 2),
            "regular_pay": round(regular_pay, 2),
            "overtime_pay": round(overtime_pay, 2),
            "gross_pay": round(gross_pay, 2),
            "tax_deduction": round(tax_deduction, 2),
            "net_pay": round(net_pay, 2)
        }


# ==============================================================================
# SECTION 3: REPORT EXPORTER (CSV & PDF)
# ==============================================================================

class ReportExporter:
    """Exports monthly and departmental reports to CSV and PDF formats."""

    @staticmethod
    def export_to_csv(payroll_list: List[Dict[str, Any]], filename: str = "monthly_payroll_report.csv") -> str:
        """Exports payroll summary list to CSV."""
        if not payroll_list:
            return "No payroll records to export."

        fieldnames = [
            "emp_id", "name", "department", "total_days_present", "total_hours",
            "regular_hours", "overtime_hours", "hourly_rate", "regular_pay",
            "overtime_pay", "gross_pay", "tax_deduction", "net_pay"
        ]

        try:
            with open(filename, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(payroll_list)
            return f"Successfully exported CSV report to '{filename}'."
        except Exception as e:
            return f"Error writing CSV file: {e}"

    @staticmethod
    def export_to_pdf(payroll_list: List[Dict[str, Any]], filename: str = "monthly_payroll_report.pdf", month: str = "Current Month") -> str:
        """Exports payroll summary list to a styled PDF using ReportLab."""
        if not REPORTLAB_AVAILABLE:
            return "ReportLab package is missing. Install using `pip install reportlab`."

        try:
            doc = SimpleDocTemplate(filename, pagesize=letter)
            elements = []
            styles = getSampleStyleSheet()

            title_style = ParagraphStyle(
                'TitleStyle', parent=styles['Heading1'],
                fontSize=18, textColor=colors.HexColor("#1A365D"),
                alignment=1, spaceAfter=10
            )
            elements.append(Paragraph("APTURA TECH SOLUTIONS", title_style))
            
            sub_style = ParagraphStyle(
                'SubTitleStyle', parent=styles['Heading2'],
                fontSize=11, textColor=colors.HexColor("#4A5568"),
                alignment=1, spaceAfter=20
            )
            elements.append(Paragraph(f"Monthly Employee Attendance & Payroll Report ({month})", sub_style))

            data = [
                ["ID", "Name", "Dept", "Days", "Reg Hrs", "OT Hrs", "Gross ($)", "Tax ($)", "Net ($)"]
            ]

            total_gross = 0.0
            total_net = 0.0

            for p in payroll_list:
                data.append([
                    p["emp_id"], p["name"], p["department"],
                    str(p["total_days_present"]), f"{p['regular_hours']:.1f}", f"{p['overtime_hours']:.1f}",
                    f"${p['gross_pay']:,.2f}", f"${p['tax_deduction']:,.2f}", f"${p['net_pay']:,.2f}"
                ])
                total_gross += p["gross_pay"]
                total_net += p["net_pay"]

            data.append([
                "TOTAL", "-", "-", "-", "-", "-",
                f"${total_gross:,.2f}", "-", f"${total_net:,.2f}"
            ])

            table = Table(data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2B6CB0")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('BACKGROUND', (0, 1), (-1, -2), colors.HexColor("#F7FAFC")),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#EDF2F7")),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ]))

            elements.append(table)
            doc.build(elements)
            return f"Successfully generated PDF report at '{filename}'."
        except Exception as e:
            return f"Failed to generate PDF report: {e}"


# ==============================================================================
# SECTION 4: CLI INTERFACE & MAIN SYSTEM PROGRAM
# ==============================================================================

class PayrollSystemCLI:
    """Main System Application Interface."""

    def __init__(self):
        self.db = DatabaseManager.load_data()
        self.current_user: Optional[Dict[str, Any]] = None

    def refresh_db(self):
        """Reloads database state from disk."""
        self.db = DatabaseManager.load_data()

    def reset_password(self):
        """Allows resetting a forgotten password securely via Admin authorization key."""
        print("\n==========================================")
        print("         FORGOT / RESET PASSWORD          ")
        print("==========================================")
        user_id = input("Enter Username or Employee ID: ").strip()
        
        users = self.db.get("users", {})
        target_user = None
        for uid, u in users.items():
            if u.get("username") == user_id or u.get("emp_id") == user_id:
                target_user = u
                break

        if not target_user:
            print(f"[ERROR] User ID or Username '{user_id}' not found.")
            return

        print(f"\nUser Found: {target_user['name']} ({target_user['emp_id']} | Role: {target_user['role'].upper()})")
        print("[SECURITY] Admin Authorization Code Required for Password Reset!")
        auth_code = input("Enter Admin Authorization Code (Hint: ADMIN2026): ").strip()
        
        if auth_code != ADMIN_SECRET_KEY:
            print("[ERROR] Invalid Authorization Code! Password reset canceled.")
            return

        new_pass = input("Enter New Password: ").strip()
        if not new_pass:
            print("[ERROR] Password cannot be empty.")
            return

        target_user["password_hash"] = hash_password(new_pass)
        success = DatabaseManager.save_data(self.db)
        if success:
            print(f"\n[SUCCESS] Password for {target_user['name']} has been reset successfully!")
            print(f"[INFO] You can now log in with your new password.")
        else:
            print("[ERROR] Failed to save updated password.")

    def register_new_employee(self):
        """Registers a new user into the system (Role chosen dynamically during enrollment)."""
        print("\n==========================================")
        print("          USER ENROLLMENT / REGISTRATION  ")
        print("==========================================")
        
        print("Select Account Role:")
        print("1. Standard Employee")
        print("2. System Administrator (Admin)")
        role_choice = input("Select Role (1-2) [default 1]: ").strip() or "1"
        
        role = "employee"
        if role_choice == "2":
            print("\n------------------------------------------")
            print(f"[SECURITY] Admin Enrollment Requires Secret Authorization Code!")
            admin_code = input("Enter Admin Authorization Code (Hint: ADMIN2026): ").strip()
            if admin_code != ADMIN_SECRET_KEY:
                print("\n[ERROR] Invalid Admin Authorization Code! Enrollment as Admin Denied.")
                print("[INFO] Fallback: Enrolling as Standard Employee.")
                role = "employee"
            else:
                print("\n[SUCCESS] Admin Authorization Code Verified! Enrolling as ADMIN.")
                role = "admin"

        print("\n------------------------------------------")
        emp_id = input("Enter Employee/User ID (e.g. EMP103 or ADM002): ").strip()
        if not emp_id:
            print("[ERROR] ID cannot be empty.")
            return

        if emp_id in self.db.get("users", {}):
            print(f"[ERROR] User ID '{emp_id}' is already registered!")
            return

        username = input("Enter Username: ").strip()
        if not username:
            print("[ERROR] Username cannot be empty.")
            return

        password = input("Enter Password: ").strip()
        if not password:
            print("[ERROR] Password cannot be empty.")
            return

        name = input("Enter Full Name: ").strip()
        dept = input("Enter Department: ").strip()
        
        try:
            hourly_rate_str = input("Enter Hourly Rate ($) [default 35.0]: ").strip() or "35.0"
            hourly_rate = float(hourly_rate_str)
        except ValueError:
            print("[ERROR] Invalid numeric input for hourly rate.")
            return

        # Save registered user
        user_record = {
            "emp_id": emp_id,
            "username": username,
            "password_hash": hash_password(password),
            "name": name,
            "role": role,
            "department": dept,
            "hourly_rate": hourly_rate,
            "tax_rate": 0.12 if role == "employee" else 0.15
        }
        self.db["users"][emp_id] = user_record

        success = DatabaseManager.save_data(self.db)
        if success:
            print(f"\n==========================================")
            print(f"[SUCCESS] User '{name}' Registered Successfully!")
            print(f"Assigned Role: {role.upper()}")
            print(f"==========================================")
            
            proceed = input("\nWould you like to log in now with your new account? (y/n): ").strip().lower()
            if proceed == 'y':
                self.current_user = user_record
                print(f"\n[LOGIN SUCCESS] Entered System as {name} ({role.upper()})!")
        else:
            print("[ERROR] Failed to save registered user data.")

    def admin_edit_payroll_details(self):
        """Allows Admin to view, modify, and update employee payroll details (Hourly Rate, Tax Rate, Dept)."""
        print("\n==========================================")
        print("  ADMIN: MODIFY EMPLOYEE PAYROLL DETAILS  ")
        print("==========================================")
        
        users = self.db.get("users", {})
        if not users:
            print("No registered users found.")
            return

        print(f"{'ID':<8} | {'Name':<18} | {'Role':<10} | {'Dept':<18} | {'Hourly Rate ($)':<15} | {'Tax Rate (%)':<12}")
        print("-" * 90)
        for uid, u in users.items():
            print(f"{u['emp_id']:<8} | {u['name']:<18} | {u['role']:<10} | {u['department']:<18} | ${u.get('hourly_rate', 0.0):<14.2f} | {u.get('tax_rate', 0.10)*100:<11.1f}%")
        print("-" * 90)

        target_id = input("\nEnter Employee ID to modify payroll details: ").strip()
        
        target_user = None
        for uid, u in users.items():
            if u.get("emp_id") == target_id or u.get("username") == target_id:
                target_user = u
                break

        if not target_user:
            print(f"[ERROR] Employee ID '{target_id}' not found.")
            return

        print(f"\nModifying Payroll Details for: {target_user['name']} ({target_user['emp_id']})")
        print(f"Current Hourly Rate: ${target_user.get('hourly_rate', 30.0)}/hr")
        print(f"Current Tax Rate:    {target_user.get('tax_rate', 0.12)*100:.1f}%")
        print(f"Current Department:  {target_user.get('department', 'N/A')}")
        print("------------------------------------------")

        new_rate = input("Enter New Hourly Rate ($) [Press Enter to keep current]: ").strip()
        new_tax = input("Enter New Tax Rate % (e.g. 15 for 15%) [Press Enter to keep current]: ").strip()
        new_dept = input("Enter New Department [Press Enter to keep current]: ").strip()

        if new_rate:
            try:
                target_user["hourly_rate"] = float(new_rate)
            except ValueError:
                print("[WARNING] Invalid rate input. Keeping current rate.")

        if new_tax:
            try:
                target_user["tax_rate"] = float(new_tax) / 100.0
            except ValueError:
                print("[WARNING] Invalid tax rate input. Keeping current tax rate.")

        if new_dept:
            target_user["department"] = new_dept

        DatabaseManager.save_data(self.db)
        print(f"\n[SUCCESS] Payroll details updated successfully for {target_user['name']}!")

    def login(self) -> bool:
        """Authenticates Admin or Employee users."""
        print("\n==========================================")
        print("          EMPLOYEE & ADMIN LOGIN          ")
        print("==========================================")
        print("Default Logins:")
        print("  - Admin:    Username = admin    | Password = admin123")
        print("  - Employee: Username = john_doe | Password = emp123")
        print("  - Employee: Username = jane_smith| Password = emp123")
        print("------------------------------------------")
        
        username_or_id = input("Enter Username or Employee ID: ").strip()
        password = input("Enter Password: ").strip()

        hashed_attempt = hash_password(password)
        users = self.db.get("users", {})
        
        matched_user = None
        for uid, user_info in users.items():
            if user_info.get("username") == username_or_id or user_info.get("emp_id") == username_or_id:
                if user_info.get("password_hash") == hashed_attempt or user_info.get("password_hash") == password:
                    matched_user = user_info
                    break

        if matched_user:
            self.current_user = matched_user
            print(f"\n[SUCCESS] Welcome, {matched_user['name']}! (Role: {matched_user['role'].upper()})")
            return True
        else:
            print("\n[ERROR] Invalid Credentials! Access Denied.")
            return False

    def clock_in_out(self):
        """Allows employee to clock in or clock out."""
        if not self.current_user:
            return

        emp_id = self.current_user["emp_id"]
        today_str = date.today().isoformat()
        attendance = self.db.get("attendance", [])

        today_record = None
        for rec in attendance:
            if rec.get("emp_id") == emp_id and rec.get("date") == today_str:
                today_record = rec
                break

        now_time = datetime.now().strftime("%H:%M:%S")

        print(f"\n--- Attendance Action ({today_str}) ---")
        if not today_record:
            print("1. Clock In Now")
            print("2. Cancel")
            choice = input("Select choice (1-2): ").strip()
            if choice == "1":
                new_record = {
                    "emp_id": emp_id,
                    "date": today_str,
                    "clock_in": now_time,
                    "clock_out": None,
                    "hours_worked": 0.0,
                    "status": "In Progress"
                }
                attendance.append(new_record)
                self.db["attendance"] = attendance
                DatabaseManager.save_data(self.db)
                print(f"[SUCCESS] Clocked IN at {now_time}.")
        else:
            if today_record.get("clock_out") is None:
                print(f"Clocked IN at: {today_record['clock_in']}")
                print("1. Clock Out Now")
                print("2. Cancel")
                choice = input("Select choice (1-2): ").strip()
                if choice == "1":
                    clock_in_dt = datetime.strptime(today_record["clock_in"], "%H:%M:%S")
                    clock_out_dt = datetime.strptime(now_time, "%H:%M:%S")
                    hours_worked = round((clock_out_dt - clock_in_dt).total_seconds() / 3600.0, 2)

                    today_record["clock_out"] = now_time
                    today_record["hours_worked"] = hours_worked
                    today_record["status"] = "Present"
                    
                    DatabaseManager.save_data(self.db)
                    print(f"[SUCCESS] Clocked OUT at {now_time}. Total Hours Worked: {hours_worked} hrs.")
            else:
                print(f"[INFO] Shift already completed today ({today_record['clock_in']} - {today_record['clock_out']}).")

    def view_attendance_history(self):
        """Displays attendance logs."""
        emp_id = self.current_user["emp_id"]
        records = [r for r in self.db.get("attendance", []) if r.get("emp_id") == emp_id]

        print(f"\n--- Attendance History for {self.current_user['name']} ---")
        if not records:
            print("No attendance records found.")
            return

        print(f"{'Date':<12} | {'Clock In':<10} | {'Clock Out':<10} | {'Hours':<6} | {'Status':<10}")
        print("-" * 58)
        for r in records:
            print(f"{r.get('date'):<12} | {r.get('clock_in'):<10} | {r.get('clock_out') or 'N/A':<10} | {r.get('hours_worked'):<6} | {r.get('status'):<10}")

    def view_payroll_statement(self):
        """Displays current payroll metrics."""
        payroll = PayrollEngine.calculate_employee_payroll(self.current_user, self.db.get("attendance", []))

        print(f"\n==========================================")
        print(f"     PAYROLL STATEMENT - {payroll['name']}    ")
        print(f"==========================================")
        print(f"Employee ID:      {payroll['emp_id']}")
        print(f"Department:       {payroll['department']}")
        print(f"Days Present:     {payroll['total_days_present']}")
        print(f"Regular Hours:    {payroll['regular_hours']} hrs @ ${payroll['hourly_rate']}/hr")
        print(f"Overtime Hours:   {payroll['overtime_hours']} hrs @ ${payroll['hourly_rate']*1.5:.2f}/hr")
        print(f"Regular Pay:      ${payroll['regular_pay']:,.2f}")
        print(f"Overtime Pay:     ${payroll['overtime_pay']:,.2f}")
        print(f"------------------------------------------")
        print(f"Gross Pay:        ${payroll['gross_pay']:,.2f}")
        print(f"Tax Deductions:  -${payroll['tax_deduction']:,.2f}")
        print(f"==========================================")
        print(f"NET SALARY:       ${payroll['net_pay']:,.2f}")
        print(f"==========================================")

    def admin_generate_reports(self):
        """Generates company-wide payroll report and exports to CSV/PDF."""
        users = self.db.get("users", {})
        attendance = self.db.get("attendance", [])

        month = input("Enter Target Month (YYYY-MM) or press Enter for ALL: ").strip()
        month_param = month if month else None

        payroll_list = []
        for uid, user_info in users.items():
            p_data = PayrollEngine.calculate_employee_payroll(user_info, attendance, month=month_param)
            payroll_list.append(p_data)

        print(f"\n==========================================================================================")
        print(f"                       MONTHLY PAYROLL SUMMARY REPORT                                     ")
        print(f"==========================================================================================")
        print(f"{'ID':<8} | {'Name':<15} | {'Department':<20} | {'Reg Hrs':<8} | {'OT Hrs':<8} | {'Gross ($)':<10} | {'Net ($)':<10}")
        print("-" * 90)

        total_gross = 0.0
        total_net = 0.0

        for p in payroll_list:
            print(f"{p['emp_id']:<8} | {p['name']:<15} | {p['department']:<20} | {p['regular_hours']:<8} | {p['overtime_hours']:<8} | ${p['gross_pay']:<9.2f} | ${p['net_pay']:<9.2f}")
            total_gross += p["gross_pay"]
            total_net += p["net_pay"]

        print("-" * 90)
        print(f"TOTAL COMPANY PAYROLL | Gross: ${total_gross:,.2f} | Net Discarded/Paid: ${total_net:,.2f}")
        print("==========================================================================================\n")

        print("1. Export to CSV Report")
        print("2. Export to PDF Report")
        print("3. Export to Both CSV & PDF")
        print("4. Return to Main Menu")

        opt = input("Select Option (1-4): ").strip()
        date_str = month if month else date.today().strftime("%Y_%m")

        if opt in ("1", "3"):
            csv_res = ReportExporter.export_to_csv(payroll_list, f"payroll_report_{date_str}.csv")
            print(f"[INFO] {csv_res}")
        if opt in ("2", "3"):
            pdf_res = ReportExporter.export_to_pdf(payroll_list, f"payroll_report_{date_str}.pdf", month=month if month else "All-Time")
            print(f"[INFO] {pdf_res}")

    def run(self):
        """Main Loop."""
        while True:
            if not self.current_user:
                print("\n==========================================")
                print("  APTURA TECH - ATTENDANCE & PAYROLL SYSTEM")
                print("==========================================")
                print("1. Login")
                print("2. Enroll / Register New User")
                print("3. Forgot / Reset Password")
                print("4. System Maintenance & Diagnostics")
                print("5. Exit Application")
                choice = input("Enter choice (1-5): ").strip()

                if choice == "1":
                    self.login()
                elif choice == "2":
                    self.register_new_employee()
                elif choice == "3":
                    self.reset_password()
                elif choice == "4":
                    print(f"\n[DIAGNOSTICS]")
                    print(f"Database File: {DATA_FILE} (Exists: {os.path.exists(DATA_FILE)})")
                    print(f"Backup File:   {BACKUP_FILE} (Exists: {os.path.exists(BACKUP_FILE)})")
                    print(f"ReportLab PDF Support: {'AVAILABLE' if REPORTLAB_AVAILABLE else 'NOT INSTALLED'}")
                elif choice == "5":
                    print("Exiting application. Goodbye!")
                    sys.exit(0)
                else:
                    print("[ERROR] Invalid choice. Try again.")
            else:
                role = self.current_user.get("role", "employee")
                print(f"\n--- MAIN MENU ({self.current_user['name']} | Role: {role.upper()}) ---")

                if role == "admin":
                    print("1. Clock In / Clock Out")
                    print("2. View My Attendance")
                    print("3. View My Payroll Statement")
                    print("4. Register / Add New User")
                    print("5. Modify & Edit Employee Payroll Details")
                    print("6. Reset / Change User Password")
                    print("7. Generate & Export Monthly Reports (CSV/PDF)")
                    print("8. Logout")
                    choice = input("Select action (1-8): ").strip()

                    if choice == "1":
                        self.clock_in_out()
                    elif choice == "2":
                        self.view_attendance_history()
                    elif choice == "3":
                        self.view_payroll_statement()
                    elif choice == "4":
                        self.register_new_employee()
                    elif choice == "5":
                        self.admin_edit_payroll_details()
                    elif choice == "6":
                        self.reset_password()
                    elif choice == "7":
                        self.admin_generate_reports()
                    elif choice == "8":
                        print(f"Logged out from {self.current_user['name']}.")
                        self.current_user = None
                    else:
                        print("[ERROR] Invalid selection.")
                else:
                    print("1. Clock In / Clock Out")
                    print("2. View My Attendance History")
                    print("3. View My Payroll Statement")
                    print("4. Reset My Password")
                    print("5. Logout")
                    choice = input("Select action (1-5): ").strip()

                    if choice == "1":
                        self.clock_in_out()
                    elif choice == "2":
                        self.view_attendance_history()
                    elif choice == "3":
                        self.view_payroll_statement()
                    elif choice == "4":
                        self.reset_password()
                    elif choice == "5":
                        print(f"Logged out from {self.current_user['name']}.")
                        self.current_user = None
                    else:
                        print("[ERROR] Invalid selection.")

if __name__ == "__main__":
    cli = PayrollSystemCLI()
    cli.run()
