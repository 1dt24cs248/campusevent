"""Auth router: login and user info endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.deps import get_db, get_current_user
from app.models.identity import User
from app.models.academic import Department, Faculty, Section, Student
from app.schemas.auth import LoginRequest, Token, UserResponse
from app.security import verify_password, create_access_token
from app.audit import log_audit

router = APIRouter(prefix="/auth")


@router.post("/login", response_model=Token)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    """Login with institutional email, student USN, or faculty employee ID."""
    identifier = body.identifier.strip()
    if not identifier:
        user = None
    else:
        normalized = identifier.casefold()
        matches: dict[str, User] = {}
        email_users = db.query(User).filter(func.lower(User.email) == normalized).all()
        for email_user in email_users:
            matches[email_user.id] = email_user

        student_users = (
            db.query(User)
            .join(Student, Student.user_id == User.id)
            .filter(User.role == "STUDENT")
            .filter(func.upper(Student.usn) == identifier.upper())
            .all()
        )
        faculty_users = (
            db.query(User)
            .join(Faculty, Faculty.user_id == User.id)
            .filter(User.role == "FACULTY")
            .filter(func.upper(Faculty.employee_id) == identifier.upper())
            .all()
        )
        for candidate in [*student_users, *faculty_users]:
            matches[candidate.id] = candidate
        user = next(iter(matches.values())) if len(matches) == 1 else None

    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if hasattr(user, 'active') and not user.active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )
    access_token = create_access_token(data={"sub": user.id, "role": user.role})
    log_audit(db, user.id, "LOGIN", "User", user.id, {"email": user.email})
    db.commit()
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
def read_users_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get authenticated account and only that user's institutional profile."""
    result = {
        "id": current_user.id,
        "email": current_user.email,
        "role": current_user.role,
        "display_name": current_user.display_name,
        "active": current_user.active,
    }
    if current_user.role == "STUDENT":
        student = db.query(Student).filter(Student.user_id == current_user.id).first()
        if student:
            section = db.query(Section).filter(Section.id == student.section_id).first()
            department = db.query(Department).filter(
                Department.id == (section.department_id if section else None)
            ).first()
            result.update({
                "student_id": student.id,
                "usn": student.usn,
                "phone": student.phone,
                "department_id": department.id if department else None,
                "department": department.name if department else None,
                "program": student.program,
                "semester": student.semester,
                "section_id": section.id if section else None,
                "section": section.code if section else None,
                "admission_year": student.admission_year,
                "academic_status": student.academic_status,
                "profile": student.profile,
            })
    elif current_user.role == "FACULTY":
        faculty = db.query(Faculty).filter(Faculty.user_id == current_user.id).first()
        if faculty:
            department = db.query(Department).filter(
                Department.id == faculty.department_id
            ).first()
            result.update({
                "faculty_id": faculty.id,
                "employee_id": faculty.employee_id,
                "department_id": department.id if department else None,
                "department": department.name if department else None,
                "designation": faculty.designation,
            })
    return result
