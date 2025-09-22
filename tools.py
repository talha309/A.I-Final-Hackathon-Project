# tools.py
from langchain_core.tools import tool
from db import get_student_collection, get_admin_collection
from typing import Dict, Any, List
import datetime

students = get_student_collection()
admins = get_admin_collection()

# ----------------------------
# Student Management (Admin-managed)
# ----------------------------
@tool
def add_student(name: str, student_id: int, department: str, email: str) -> Dict[str, Any]:
    """
    Add student (email must be unique). Returns inserted student doc or error.
    Signature: add_student(name, student_id, department, email)
    """
    email = email.lower().strip()
    if students.find_one({"email": email}):
        return {"error": f"Student with email {email} already exists"}
    student = {
        "name": name,
        "student_id": student_id,
        "department": department,
        "email": email,
        "created_at": datetime.datetime.utcnow()
    }
    result = students.insert_one(student)
    student["_id"] = str(result.inserted_id)
    return {"message": "Student added successfully", "student": student}

@tool
def get_student(identifier: str) -> Dict[str, Any]:
    """
    Get student by email OR by student_id (identifier passed as string).
    Example: get_student('anas@gmail.com') or get_student('123')
    """
    identifier = identifier.strip()
    student = students.find_one({"email": identifier.lower()})
    if not student:
        try:
            sid = int(identifier)
            student = students.find_one({"student_id": sid})
        except Exception:
            student = None
    if not student:
        return {"error": "Student not found"}
    student["_id"] = str(student["_id"])
    return student

@tool
def update_student(identifier: str, field: str, new_value: str) -> Dict[str, Any]:
    """
    Update student by email or student_id.
    Allowed fields: name, department, email, student_id
    If field is 'email', ensure new email doesn't already exist.
    """
    identifier = identifier.strip()
    query = {"email": identifier.lower()}
    if students.find_one(query) is None:
        try:
            sid = int(identifier)
            query = {"student_id": sid}
        except Exception:
            pass

    if field not in ["name", "department", "email", "student_id"]:
        return {"error": "Invalid field"}

    if field == "email":
        new_email = new_value.lower().strip()
        if students.find_one({"email": new_email}):
            return {"error": f"Student with email {new_email} already exists"}

    if field == "student_id":
        try:
            new_value = int(new_value)
        except Exception:
            return {"error": "student_id must be an integer"}

    result = students.update_one(query, {"$set": {field: new_value}})
    if result.matched_count == 0:
        return {"error": "Student not found"}
    student = students.find_one(query if field != "email" else {"email": new_value})
    student["_id"] = str(student["_id"])
    return {"message": "Student updated successfully", "student": student}

@tool
def delete_student(identifier: str) -> Dict[str, Any]:
    """
    Delete student by email or student_id.
    """
    identifier = identifier.strip()
    query = {"email": identifier.lower()}
    if students.find_one(query) is None:
        try:
            sid = int(identifier)
            query = {"student_id": sid}
        except Exception:
            pass

    result = students.delete_one(query)
    if result.deleted_count == 0:
        return {"error": "Student not found"}
    return {"message": f"Student deleted successfully"}

@tool
def list_students() -> Dict[str, Any]:
    """
    List all students, sorted by creation date (newest first).
    """
    result = list(students.find().sort("created_at", -1))
    out = []
    for s in result:
        s["_id"] = str(s["_id"])
        out.append(s)
    return {"students": out}

# ----------------------------
# Analytics
# ----------------------------
@tool
def get_total_students() -> Dict[str, Any]:
    """
    Get the total number of students.
    """
    return {"total_students": students.count_documents({})}

@tool
def get_students_by_department() -> Dict[str, Any]:
    """
    Get the count of students by department.
    """
    pipeline = [{"$group": {"_id": "$department", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}]
    return {"students_by_department": list(students.aggregate(pipeline))}

@tool
def get_recent_onboarded_students(limit: int = 5) -> Dict[str, Any]:
    """
    Get recently onboarded students, sorted by creation date.
    """
    limit = int(limit)
    cursor = students.find().sort("created_at", -1).limit(limit)
    out = []
    for s in cursor:
        s["_id"] = str(s["_id"])
        out.append(s)
    return {"recent_students": out}

@tool
def get_active_students_last_7_days() -> Dict[str, Any]:
    """
    Mocked active list. Returns a limited list of students as a mock.
    """
    cursor = students.find().limit(3)
    out = []
    for s in cursor:
        s["_id"] = str(s["_id"])
        out.append(s)
    return {"active_last_7_days": out}

# ----------------------------
# FAQ / Events
# ----------------------------
@tool
def get_cafeteria_timings() -> Dict[str, Any]:
    """
    Get cafeteria timings.
    """
    return {"cafeteria_timings": "Mon-Fri 8am-8pm, Sat-Sun 9am-5pm"}

@tool
def get_library_hours() -> Dict[str, Any]:
    """
    Get library hours.
    """
    return {"library_hours": "Mon-Fri 9am-10pm, Sat 9am-6pm, Sun Closed"}

@tool
def get_event_schedule() -> Dict[str, Any]:
    """
    Get the event schedule.
    """
    return {
        "events": [
            {"title": "Orientation", "date": "Sept 25"},
            {"title": "Tech Talk", "date": "Oct 5"},
            {"title": "Sports Day", "date": "Oct 15"},
        ]
    }

# ----------------------------
# Notifications (mock)
# ----------------------------
@tool
def send_email(student_identifier: str, message: str) -> Dict[str, Any]:
    """
    Mock sending an email to a student by email or student_id.
    """
    student = None
    student_identifier = student_identifier.strip()
    student = students.find_one({"email": student_identifier.lower()})
    if not student:
        try:
            sid = int(student_identifier)
            student = students.find_one({"student_id": sid})
        except Exception:
            pass

    if not student:
        return {"error": "Student not found"}
    print(f"[EMAIL MOCK] to={student['email']} message={message}")
    return {"message": f"Email mock sent to {student['email']}"}