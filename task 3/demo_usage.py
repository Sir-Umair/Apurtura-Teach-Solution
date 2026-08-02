"""
APTURA TECH SOLUTIONS - Automated Usage Demonstration Script
File: demo_usage.py

Run this file with:
    python demo_usage.py

This script automatically registers a new employee, clocks them in/out,
calculates salary/overtime, and exports reports without requiring manual typing!
"""

import os
from task1 import (
    DatabaseManager,
    PayrollEngine,
    ReportExporter,
    hash_password,
    DATA_FILE
)

def run_automated_demo():
    print("================================================================================")
    print("         APTURA TECH - AUTOMATED SYSTEM DEMONSTRATION & USAGE GUIDE           ")
    print("================================================================================")

    # Step 1: Load database
    print("\n[STEP 1] Loading System Database...")
    db = DatabaseManager.load_data()
    print(f"Database Loaded! Current total users: {len(db['users'])}")

    # Step 2: Register a new employee automatically
    print("\n[STEP 2] Registering New Employee Data...")
    new_emp_id = "EMP200"
    new_user = {
        "emp_id": new_emp_id,
        "username": "ali_khan",
        "password_hash": hash_password("pass123"),
        "name": "Ali Khan",
        "role": "employee",
        "department": "Cyber Security",
        "hourly_rate": 40.0,
        "tax_rate": 0.12
    }

    db["users"][new_emp_id] = new_user
    DatabaseManager.save_data(db)
    print(f"[SUCCESS] Registered New Employee: '{new_user['name']}' ({new_emp_id})")

    # Step 3: Register Attendance (Clock In & Clock Out)
    print("\n[STEP 3] Registering Attendance Log (Clock In / Clock Out)...")
    sample_attendance = [
        {"emp_id": new_emp_id, "date": "2026-08-01", "clock_in": "09:00:00", "clock_out": "18:00:00", "hours_worked": 9.0, "status": "Present"},
        {"emp_id": new_emp_id, "date": "2026-08-02", "clock_in": "09:00:00", "clock_out": "19:30:00", "hours_worked": 10.5, "status": "Present"},
        {"emp_id": new_emp_id, "date": "2026-08-03", "clock_in": "08:30:00", "clock_out": "17:00:00", "hours_worked": 8.5, "status": "Present"}
    ]

    for att in sample_attendance:
        db["attendance"].append(att)

    DatabaseManager.save_data(db)
    print(f"[SUCCESS] Registered 3 Days of Attendance for {new_user['name']}!")

    # Step 4: Calculate Salary and Overtime
    print("\n[STEP 4] Calculating Salary & Overtime Breakdown...")
    payroll = PayrollEngine.calculate_employee_payroll(new_user, db["attendance"])

    print("--------------------------------------------------------------------------------")
    print(f"Employee ID:      {payroll['emp_id']}")
    print(f"Employee Name:    {payroll['name']}")
    print(f"Department:       {payroll['department']}")
    print(f"Days Logged:      {payroll['total_days_present']} Days")
    print(f"Total Hours:      {payroll['total_hours']} hrs")
    print(f"Regular Hours:    {payroll['regular_hours']} hrs @ ${payroll['hourly_rate']}/hr = ${payroll['regular_pay']}")
    print(f"Overtime Hours:   {payroll['overtime_hours']} hrs @ ${payroll['hourly_rate']*1.5:.2f}/hr = ${payroll['overtime_pay']}")
    print(f"Gross Salary:     ${payroll['gross_pay']:,.2f}")
    print(f"Tax Deductions:  -${payroll['tax_deduction']:,.2f}")
    print(f"NET SALARY PAID:  ${payroll['net_pay']:,.2f}")
    print("--------------------------------------------------------------------------------")

    # Step 5: Exporting Reports
    print("\n[STEP 5] Exporting Monthly Payroll Summary to CSV and PDF...")
    payroll_list = [PayrollEngine.calculate_employee_payroll(u, db["attendance"]) for uid, u in db["users"].items()]
    
    csv_msg = ReportExporter.export_to_csv(payroll_list, "demo_payroll_report.csv")
    pdf_msg = ReportExporter.export_to_pdf(payroll_list, "demo_payroll_report.pdf", "August 2026")
    
    print(f"[CSV REPORT]: {csv_msg}")
    print(f"[PDF REPORT]: {pdf_msg}")

    print("\n================================================================================")
    print("      DEMONSTRATION COMPLETED! CHECKS & FILES GENERATED SUCCESSFULLY.           ")
    print("================================================================================")

if __name__ == "__main__":
    run_automated_demo()
