
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st
from argon2 import PasswordHasher
from argon2.exceptions import (
    InvalidHashError,
    VerificationError,
    VerifyMismatchError,
)
from sqlalchemy import (
    Boolean,
    DateTime,
    Integer,
    String,
    create_engine,
    select,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


# --------------------------------------------------
# Database configuration
# --------------------------------------------------

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///retailpulse_dev.db")

# Render PostgreSQL URLs may use postgres:// or postgresql://.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgres://", "postgresql+psycopg://", 1
    )
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgresql://", "postgresql+psycopg://", 1
    )

engine_options = {"pool_pre_ping": True}

if DATABASE_URL.startswith("sqlite:"):
    engine_options["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_options)
SessionLocal = sessionmaker(
    bind=engine,
    expire_on_commit=False,
)


# --------------------------------------------------
# Database model
# --------------------------------------------------

class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="Viewer")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


password_hasher = PasswordHasher()


# --------------------------------------------------
# Initialization and initial Admin provisioning
# --------------------------------------------------

def initialize_database():
    """Create missing tables. Use migrations for future schema changes."""
    Base.metadata.create_all(engine)


def bootstrap_first_admin():
    """
    Create the first Admin only when the database has no users.
    Requires BOOTSTRAP_ADMIN_USERNAME and BOOTSTRAP_ADMIN_PASSWORD.
    Remove these environment variables after provisioning.
    """
    username = os.environ.get("BOOTSTRAP_ADMIN_USERNAME", "").strip()
    password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "")

    if not username or not password:
        return False

    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,50}", username):
        raise ValueError("Bootstrap Admin username has an invalid format.")

    if len(password) < 12:
        raise ValueError("Bootstrap Admin password must be at least 12 characters.")

    with SessionLocal() as db:
        if db.scalar(select(User.id).limit(1)) is not None:
            return False

        admin = User(
            username=username,
            password_hash=password_hasher.hash(password),
            role="Admin",
            is_active=True,
        )
        db.add(admin)

        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return False

    return True


# --------------------------------------------------
# User and password operations
# --------------------------------------------------

def authenticate_user(username: str, password: str):
    """Return an active user after password verification; otherwise None."""
    username = username.strip()

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == username))

        if user is None or not user.is_active:
            return None

        try:
            password_hasher.verify(user.password_hash, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return None

        if password_hasher.check_needs_rehash(user.password_hash):
            user.password_hash = password_hasher.hash(password)
            db.commit()

        return {
            "id": user.id,
            "username": user.username,
            "role": user.role,
        }


def create_user(username: str, password: str, role: str = "Viewer"):
    """Create a user. Call only from a properly authorized Admin action."""
    username = username.strip()

    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,50}", username):
        raise ValueError(
            "Username must be 3–50 characters: letters, numbers, _, . or -."
        )

    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters.")

    if role not in {"Admin", "Analyst", "Viewer"}:
        raise ValueError("Invalid role.")

    with SessionLocal() as db:
        user = User(
            username=username,
            password_hash=password_hasher.hash(password),
            role=role,
            is_active=True,
        )
        db.add(user)

        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise ValueError("That username already exists.") from exc

        return user.id


def get_active_user(user_id: int):
    """Re-check account status and role against the database."""
    with SessionLocal() as db:
        user = db.get(User, user_id)

        if user is None or not user.is_active:
            return None

        if user.role not in {"Admin", "Analyst", "Viewer"}:
            return None

        return {
            "id": user.id,
            "username": user.username,
            "role": user.role,
        }


# --------------------------------------------------
# Streamlit session helpers
# --------------------------------------------------

def logout():
    st.session_state.pop("auth_user", None)
    st.rerun()




def require_login():
    session_user = st.session_state.get("auth_user")

    if session_user:
        current_user = get_active_user(session_user["id"])

        if current_user:
            st.session_state["auth_user"] = current_user
            return current_user

        st.session_state.pop("auth_user", None)

    st.title("RetailPulse")
    st.caption("AI-Powered Retail Intelligence")
    st.subheader("Welcome to RetailPulse")

    signin_tab, register_tab = st.tabs(
        ["Sign In", "Create Account"]
    )

    # ---------------- SIGN IN ----------------
    with signin_tab:
        st.write("Sign in to access your dashboard.")

        with st.form("retailpulse_login"):
            username = st.text_input(
                "Username",
                max_chars=50,
                key="login_username",
            )

            password = st.text_input(
                "Password",
                type="password",
                key="login_password",
            )

            submitted = st.form_submit_button(
                "Sign In",
                width="stretch",
            )

        if submitted:
            if not username.strip() or not password:
                st.error("Enter your username and password.")
            else:
                user = authenticate_user(username, password)

                if user:
                    st.session_state["auth_user"] = user
                    st.rerun()
                else:
                    st.error(
                        "Sign-in failed. Check your credentials "
                        "or contact an Admin."
                    )

        with st.expander("Forgot Password?"):
            st.markdown("### Reset your password")

            st.write(
                "Password resets are handled by your "
                "RetailPulse administrator."
            )

            st.info(
                "Contact your Admin and provide your username. "
                "Never share your current password."
            )

    # ---------------- CREATE ACCOUNT ----------------
    with register_tab:
        st.write("Create your RetailPulse account.")

        with st.form("retailpulse_register"):
            new_username = st.text_input(
                "Choose a username",
                max_chars=50,
                key="register_username",
            )

            new_password = st.text_input(
                "Create a password (12+ characters)",
                type="password",
                key="register_password",
            )

            confirm_password = st.text_input(
                "Confirm password",
                type="password",
                key="register_confirm_password",
            )

            register_submitted = st.form_submit_button(
                "Create Account",
                width="stretch",
            )

        if register_submitted:
            if not new_username.strip():
                st.error("Choose a username.")

            elif not new_password:
                st.error("Choose a password.")

            elif new_password != confirm_password:
                st.error("The passwords do not match.")

            elif len(new_password) < 12:
                st.error(
                    "Your password must be at least "
                    "12 characters long."
                )

            else:
                try:
                    create_user(
                        username=new_username.strip(),
                        password=new_password,
                        role="Viewer",
                    )

                    st.success(
                        "Account created successfully! "
                        "You can now sign in."
                    )

                    st.info(
                        "Your account has the Viewer role. "
                        "Contact an Admin if you need a different role."
                    )

                except ValueError as exc:
                    st.error(str(exc))

    return None

