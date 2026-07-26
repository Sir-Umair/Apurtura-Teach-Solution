import json
import os

DATA_FILE = "students.json"


def load_records():
    """Load student records from the JSON file. Returns a dict keyed by roll number."""
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r") as f:
            content = f.read().strip()
            if not content:
                return {}
            return json.loads(content)
    except (json.JSONDecodeError, IOError) as e:
        print(f"[Warning] Could not read data file properly ({e}). Starting with empty records.")
        return {}


def save_records(records):
    """Save the given records dict back to the JSON file."""
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(records, f, indent=4)
    except IOError as e:
        print(f"[Error] Could not save data: {e}")


def get_non_empty_input(prompt):
    """Keep asking until the user provides a non-empty string."""
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("This field cannot be empty. Please try again.")


def get_valid_age(prompt):
    """Keep asking until the user provides a valid age (positive integer)."""
    while True:
        value = input(prompt).strip()
        if value.isdigit() and int(value) > 0:
            return int(value)
        print("Please enter a valid positive number for age.")


def get_valid_marks(prompt):
    """Keep asking until the user provides valid marks (0-100)."""
    while True:
        value = input(prompt).strip()
        try:
            marks = float(value)
            if 0 <= marks <= 100:
                return marks
            print("Marks must be between 0 and 100.")
        except ValueError:
            print("Please enter a valid number for marks.")


def pause():
    input("\nPress Enter to continue...")



def add_student(records):
    print("\n--- Add Student ---")
    roll_no = get_non_empty_input("Enter Roll Number: ")

    if roll_no in records:
        print(f"A student with Roll Number '{roll_no}' already exists!")
        return

    name = get_non_empty_input("Enter Name: ")
    age = get_valid_age("Enter Age: ")
    course = get_non_empty_input("Enter Course/Class: ")
    marks = get_valid_marks("Enter Marks (0-100): ")

    records[roll_no] = {
        "name": name,
        "age": age,
        "course": course,
        "marks": marks
    }

    save_records(records)
    print(f"Student '{name}' (Roll No: {roll_no}) added successfully!")


def update_student(records):
    print("\n--- Update Student ---")
    roll_no = get_non_empty_input("Enter Roll Number of the student to update: ")

    if roll_no not in records:
        print(f"No student found with Roll Number '{roll_no}'.")
        return

    student = records[roll_no]
    print(f"Current details: {student}")
    print("Leave a field blank to keep it unchanged.")

    name = input(f"Enter new Name [{student['name']}]: ").strip()
    if name:
        student["name"] = name

    age = input(f"Enter new Age [{student['age']}]: ").strip()
    if age:
        if age.isdigit() and int(age) > 0:
            student["age"] = int(age)
        else:
            print("Invalid age input. Age not updated.")

    course = input(f"Enter new Course/Class [{student['course']}]: ").strip()
    if course:
        student["course"] = course

    marks = input(f"Enter new Marks [{student['marks']}]: ").strip()
    if marks:
        try:
            marks_val = float(marks)
            if 0 <= marks_val <= 100:
                student["marks"] = marks_val
            else:
                print("Marks must be between 0 and 100. Marks not updated.")
        except ValueError:
            print("Invalid marks input. Marks not updated.")

    records[roll_no] = student
    save_records(records)
    print("Student record updated successfully!")


def delete_student(records):
    print("\n--- Delete Student ---")
    roll_no = get_non_empty_input("Enter Roll Number of the student to delete: ")

    if roll_no not in records:
        print(f"No student found with Roll Number '{roll_no}'.")
        return

    student = records[roll_no]
    confirm = input(f"Are you sure you want to delete '{student['name']}' "
                     f"(Roll No: {roll_no})? (y/n): ").strip().lower()
    if confirm == "y":
        del records[roll_no]
        save_records(records)
        print("Student record deleted successfully!")
    else:
        print("Deletion cancelled.")


def search_student(records):
    print("\n--- Search Student ---")
    print("1. Search by Roll Number")
    print("2. Search by Name")
    choice = input("Enter your choice: ").strip()

    if choice == "1":
        roll_no = get_non_empty_input("Enter Roll Number: ")
        if roll_no in records:
            display_single(roll_no, records[roll_no])
        else:
            print(f"No student found with Roll Number '{roll_no}'.")

    elif choice == "2":
        name_query = get_non_empty_input("Enter Name (or part of it): ").lower()
        found = False
        for roll_no, student in records.items():
            if name_query in student["name"].lower():
                display_single(roll_no, student)
                found = True
        if not found:
            print(f"No student found matching name '{name_query}'.")
    else:
        print("Invalid choice.")


def display_single(roll_no, student):
    print("-" * 40)
    print(f"Roll Number : {roll_no}")
    print(f"Name        : {student['name']}")
    print(f"Age         : {student['age']}")
    print(f"Course      : {student['course']}")
    print(f"Marks       : {student['marks']}")
    print("-" * 40)


def display_all(records):
    print("\n--- All Student Records ---")
    if not records:
        print("No records found.")
        return

    print(f"{'Roll No':<10}{'Name':<20}{'Age':<6}{'Course':<15}{'Marks':<6}")
    print("-" * 57)
    for roll_no, student in records.items():
        print(f"{roll_no:<10}{student['name']:<20}{student['age']:<6}"
              f"{student['course']:<15}{student['marks']:<6}")


# ---------------------------------------------------------------------
# Main Menu Loop
# ---------------------------------------------------------------------

def main():
    records = load_records()

    menu = """
========================================
   SMART STUDENT RECORD MANAGEMENT SYSTEM
========================================
1. Add Student
2. Update Student
3. Delete Student
4. Search Student
5. Display All Records
6. Exit
========================================
"""

    while True:
        print(menu)
        choice = input("Enter your choice (1-6): ").strip()

        if choice == "1":
            add_student(records)
        elif choice == "2":
            update_student(records)
        elif choice == "3":
            delete_student(records)
        elif choice == "4":
            search_student(records)
        elif choice == "5":
            display_all(records)
        elif choice == "6":
            print("Exiting... All data has been saved. Goodbye!")
            break
        else:
            print("Invalid choice. Please enter a number between 1 and 6.")

        pause()


if __name__ == "__main__":
    main()