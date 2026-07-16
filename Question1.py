import json
import os

DATA_FILE = "students.json"

def load_records():
    """Load student records from the JSON file.
    Returns a dict keyed by roll number.
    """
    if not os.path.exists(DATA_FILE):
        print(f"[Error] Data file '{DATA_FILE}' not found. Please run record.py first to add students.")
        return {}
    try:
        with open(DATA_FILE, "r") as f:
            content = f.read().strip()
            if not content:
                return {}
            return json.loads(content)
    except (json.JSONDecodeError, IOError) as e:
        print(f"[Error] Could not read data file: {e}")
        return {}

def selection_sort_by_gpa(records_dict):
    """Return a list of (roll_no, student) tuples sorted by GPA (marks) descending.
    GPA is represented directly by the 'marks' value (0-100) or scaled.
    """
    # Convert dict to a list of tuples for sorting
    student_list = list(records_dict.items())  # List of (roll_no, student_details_dict)
    n = len(student_list)
    
    for i in range(n - 1):
        # Assume the student with the highest GPA (max marks) is at index i
        max_idx = i
        for j in range(i + 1, n):
            # Comparing the 'marks' field of student details
            if student_list[j][1]["marks"] > student_list[max_idx][1]["marks"]:
                max_idx = j
                
        # Swap the found maximum with the element at index i
        if max_idx != i:
            student_list[i], student_list[max_idx] = student_list[max_idx], student_list[i]
            
    return student_list

def display_sorted(sorted_students):
    """Print the sorted student records in a clean tabular format."""
    print("\n" + "=" * 55)
    print("           STUDENTS SORTED BY GPA (HIGHEST TO LOWEST)")
    print("=" * 55)
    print(f"{'Roll No':<12}{'Name':<20}{'Marks (0-100)':<15}{'GPA (4.0 Scale)':<15}")
    print("-" * 55)
    
    for roll_no, details in sorted_students:
        marks = details["marks"]
        # Convert marks out of 100 to a standard 4.0 GPA scale
        gpa = round((marks / 100) * 4, 2)
        print(f"{roll_no:<12}{details['name']:<20}{marks:<15.1f}{gpa:<15.2f}")
    print("=" * 55)

def main():
    print("Loading student records...")
    records = load_records()
    if not records:
        print("No student records found to sort.")
        return
        
    print(f"Sorting {len(records)} student record(s)...")
    sorted_students = selection_sort_by_gpa(records)
    display_sorted(sorted_students)

if __name__ == "__main__":
    main()
