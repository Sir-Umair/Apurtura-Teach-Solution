"""
APTURA TECH SOLUTIONS - Internship Program Batch 02
Automated Unit Test Suite for Task 01 (task1.py)

Usage:
    python test_payroll_system.py
"""

import os
import json
import unittest

from task1 import (
    hash_password,
    DatabaseManager,
    PayrollEngine,
    ReportExporter,
    DATA_FILE,
    BACKUP_FILE
)


class TestPayrollSystem(unittest.TestCase):

    def setUp(self):
        """Clean up and set up fresh test environment before each test."""
        self.test_data_file = "test_payroll_database.json"
        
        # Override data file constants for isolation
        DatabaseManager.DATA_FILE = self.test_data_file
        
        # Clean up any leftover files
        for f in [DATA_FILE, BACKUP_FILE, "test_report.csv", "test_report.pdf"]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass

    def tearDown(self):
        """Clean up test artifacts post execution."""
        for f in ["test_report.csv", "test_report.pdf"]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass

    def test_01_password_hashing(self):
        """Verify SHA-256 password hashing security."""
        p1 = hash_password("secret123")
        p2 = hash_password("secret123")
        p3 = hash_password("different_pass")
        
        self.assertEqual(p1, p2)
        self.assertNotEqual(p1, p3)

    def test_02_payroll_engine_regular_hours(self):
        """Verify salary calculation for standard 8-hour workday."""
        user_info = {
            "emp_id": "TEST01",
            "name": "Alice Tester",
            "department": "QA",
            "hourly_rate": 40.0,
            "tax_rate": 0.10
        }
        attendance = [
            {"emp_id": "TEST01", "date": "2026-08-01", "hours_worked": 8.0, "status": "Present"},
            {"emp_id": "TEST01", "date": "2026-08-02", "hours_worked": 8.0, "status": "Present"}
        ]

        payroll = PayrollEngine.calculate_employee_payroll(user_info, attendance)
        
        self.assertEqual(payroll["total_hours"], 16.0)
        self.assertEqual(payroll["regular_hours"], 16.0)
        self.assertEqual(payroll["overtime_hours"], 0.0)
        self.assertEqual(payroll["gross_pay"], 640.0)
        self.assertEqual(payroll["tax_deduction"], 64.0)
        self.assertEqual(payroll["net_pay"], 576.0)

    def test_03_payroll_engine_overtime_calculation(self):
        """Verify overtime calculations with 1.5x multiplier for work > 8 hours/day."""
        user_info = {
            "emp_id": "TEST02",
            "name": "Bob Overtime",
            "department": "Engineering",
            "hourly_rate": 30.0,
            "tax_rate": 0.20
        }
        attendance = [
            {"emp_id": "TEST02", "date": "2026-08-01", "hours_worked": 10.0, "status": "Present"}
        ]

        payroll = PayrollEngine.calculate_employee_payroll(user_info, attendance)

        self.assertEqual(payroll["regular_hours"], 8.0)
        self.assertEqual(payroll["overtime_hours"], 2.0)
        self.assertEqual(payroll["regular_pay"], 240.0)
        self.assertEqual(payroll["overtime_pay"], 90.0)
        self.assertEqual(payroll["gross_pay"], 330.0)
        self.assertEqual(payroll["tax_deduction"], 66.0)
        self.assertEqual(payroll["net_pay"], 264.0)

    def test_04_atomic_database_save_and_load(self):
        """Verify database persistence and default dataset initialization."""
        db_data = DatabaseManager.get_default_db()
        save_status = DatabaseManager.save_data(db_data)
        self.assertTrue(save_status)
        self.assertTrue(os.path.exists(DATA_FILE))

        loaded_data = DatabaseManager.load_data()
        self.assertIn("users", loaded_data)
        self.assertIn("attendance", loaded_data)
        self.assertIn("admin", loaded_data["users"])

    def test_05_corrupt_database_recovery(self):
        """Simulate file corruption and test auto-recovery from backup."""
        db_data = DatabaseManager.get_default_db()
        DatabaseManager.save_data(db_data)

        with open(DATA_FILE, "w", encoding="utf-8") as f:
            f.write("{ CORRUPTED JSON ...")

        recovered_data = DatabaseManager.load_data()
        self.assertIsNotNone(recovered_data)
        self.assertIn("users", recovered_data)

    def test_06_csv_report_export(self):
        """Verify CSV export functionality."""
        sample_payroll = [
            {
                "emp_id": "EMP101",
                "name": "John Doe",
                "department": "Engineering",
                "total_days_present": 5,
                "total_hours": 42.0,
                "regular_hours": 40.0,
                "overtime_hours": 2.0,
                "hourly_rate": 35.0,
                "regular_pay": 1400.0,
                "overtime_pay": 105.0,
                "gross_pay": 1505.0,
                "tax_deduction": 180.60,
                "net_pay": 1324.40
            }
        ]

        csv_filename = "test_report.csv"
        result_msg = ReportExporter.export_to_csv(sample_payroll, filename=csv_filename)
        self.assertIn("Successfully exported", result_msg)
        self.assertTrue(os.path.exists(csv_filename))

    def test_07_pdf_report_export(self):
        """Verify PDF export functionality via ReportLab."""
        sample_payroll = [
            {
                "emp_id": "EMP101",
                "name": "John Doe",
                "department": "Engineering",
                "total_days_present": 5,
                "total_hours": 40.0,
                "regular_hours": 40.0,
                "overtime_hours": 0.0,
                "hourly_rate": 35.0,
                "regular_pay": 1400.0,
                "overtime_pay": 0.0,
                "gross_pay": 1400.0,
                "tax_deduction": 168.0,
                "net_pay": 1232.0
            }
        ]

        pdf_filename = "test_report.pdf"
        result_msg = ReportExporter.export_to_pdf(sample_payroll, filename=pdf_filename)
        self.assertIn("Successfully generated PDF", result_msg)
        self.assertTrue(os.path.exists(pdf_filename))


if __name__ == "__main__":
    unittest.main()
