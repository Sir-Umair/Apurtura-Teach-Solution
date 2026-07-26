import json
import os
import time
import random
DATA_FILE = "students.json"

# =====================================================================
# PROBLEM 1 — Sorting Algorithm
# =====================================================================
# Right now we use Selection Sort which is O(n^2).
# For 100,000 records that means roughly 10 billion comparisons.
# On my machine, that would take several minutes or more.
#
# SOLUTION: Switch to Merge Sort which is O(n log n).
# For 100,000 records: 100,000 * 17 = ~1,700,000 comparisons (way faster).
# Merge Sort also keeps a stable order so students with the same GPA
# stay in their original sequence, which is a nice bonus.

def merge_sort_descending(arr):
    """Merge sort implementation that sorts (roll_no, student) tuples
    by marks in descending order. Time complexity: O(n log n)."""
    if len(arr) <= 1:
        return arr

    mid = len(arr) // 2
    left_half = merge_sort_descending(arr[:mid])
    right_half = merge_sort_descending(arr[mid:])

    return merge(left_half, right_half)

def merge(left, right):
    """Merge two sorted halves into one sorted list (descending by marks)."""
    result = []
    i = 0
    j = 0

    while i < len(left) and j < len(right):
        # descending order so we pick the LARGER marks first
        if left[i][1]["marks"] >= right[j][1]["marks"]:
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1

    # add whatever is left over
    while i < len(left):
        result.append(left[i])
        i += 1
    while j < len(right):
        result.append(right[j])
        j += 1

    return result

# old selection sort kept for comparison
def selection_sort_descending(arr):
    """Selection sort — O(n^2). Fine for small lists, too slow for 100k."""
    n = len(arr)
    for i in range(n - 1):
        max_idx = i
        for j in range(i + 1, n):
            if arr[j][1]["marks"] > arr[max_idx][1]["marks"]:
                max_idx = j
        if max_idx != i:
            arr[i], arr[max_idx] = arr[max_idx], arr[i]
    return arr

def generate_fake_records(count):
    """Create a dict of fake student records for testing."""
    records = {}
    for i in range(count):
        roll = str(100000 + i)
        records[roll] = {
            "name": f"Student_{i}",
            "age": random.randint(18, 25),
            "course": random.choice(["BSCS", "BSSE", "BSIT", "BSAI"]),
            "marks": round(random.uniform(0, 100), 1)
        }
    return records


def run_comparison():
    """Compare sorting performance between Selection Sort and Merge Sort."""
    # We use a smaller set for selection sort because it would take
    # too long with 100k records
    small_count = 5000
    large_count = 100000

    print("=" * 60)
    print("  PERFORMANCE COMPARISON: Selection Sort vs Merge Sort")
    print("=" * 60)

    # --- Test with small dataset ---
    print(f"\n--- Test with {small_count} records ---")
    fake_data = generate_fake_records(small_count)
    items = list(fake_data.items())

    # Merge Sort timing
    start = time.time()
    merge_sort_descending(list(items))  # copy so we don't modify original
    merge_time = time.time() - start
    print(f"Merge Sort   : {merge_time:.4f} seconds")

    # Selection Sort timing
    start = time.time()
    selection_sort_descending(list(items))
    selection_time = time.time() - start
    print(f"Selection Sort: {selection_time:.4f} seconds")

    if selection_time > 0:
        print(f"Merge Sort is {selection_time / merge_time:.1f}x faster")

    # --- Test Merge Sort with large dataset ---
    print(f"\n--- Merge Sort with {large_count} records ---")
    large_data = generate_fake_records(large_count)
    large_items = list(large_data.items())

    start = time.time()
    sorted_result = merge_sort_descending(large_items)
    merge_time_large = time.time() - start
    print(f"Merge Sort   : {merge_time_large:.4f} seconds")
    print(f"(Selection Sort would take estimated "
          f"{(selection_time / small_count**2) * large_count**2:.0f} seconds)")

    # Show top 5 and bottom 5 from the sorted result
    print(f"\nTop 5 students (highest GPA):")
    print(f"{'Roll No':<12}{'Name':<20}{'Marks':<10}{'GPA (4.0)':<10}")
    print("-" * 50)
    for roll, student in sorted_result[:5]:
        gpa = round((student["marks"] / 100) * 4, 2)
        print(f"{roll:<12}{student['name']:<20}{student['marks']:<10}{gpa:<10}")

    print(f"\nBottom 5 students (lowest GPA):")
    print(f"{'Roll No':<12}{'Name':<20}{'Marks':<10}{'GPA (4.0)':<10}")
    print("-" * 50)
    for roll, student in sorted_result[-5:]:
        gpa = round((student["marks"] / 100) * 4, 2)
        print(f"{roll:<12}{student['name']:<20}{student['marks']:<10}{gpa:<10}")

    # --- Summary ---
    print("\n" + "=" * 60)
    print("SUMMARY OF RECOMMENDED MODIFICATIONS")
    print("=" * 60)
    print("""
1. SORTING: Replace Selection Sort O(n^2) with Merge Sort O(n log n)
   - Proven above: Merge Sort handles 100k records in under a second.
   - Selection Sort would take minutes for the same dataset.

2. STORAGE: Replace JSON file with SQLite database
   - No need to load/save entire file for every operation.
   - Built-in indexing makes search O(log n) instead of O(n).
   - Supports SQL queries for sorting, filtering, pagination.

3. SEARCHING: Add indexes for frequently searched fields
   - Name index for quick name lookups.
   - SQLite CREATE INDEX handles this automatically.

4. MEMORY: Use pagination for displaying large result sets
   - Show 50 records per page instead of all 100k at once.
   - SQLite LIMIT/OFFSET makes this straightforward.

5. FILE I/O: Batch writes instead of per-operation saves
   - Group multiple changes into one write/transaction.
   - Reduces disk I/O significantly for bulk operations.
""")


if __name__ == "__main__":
    run_comparison()
