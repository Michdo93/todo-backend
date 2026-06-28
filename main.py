"""
todo-backend – FastAPI + SQLite + JWT
Deploy auf Render.com als Web Service (Python)
"""
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from pydantic import BaseModel
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional, List
import os

# ── Config ────────────────────────────────────────────────────────────────────
SECRET_KEY  = os.getenv("SECRET_KEY", "CHANGE_THIS_IN_PRODUCTION_USE_RANDOM_32_CHARS")
ALGORITHM   = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 Tage

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./todo.db")

# Render.com: /data nur nutzen wenn Disk bereits gemountet ist (existiert + beschreibbar)
if DATABASE_URL.startswith("sqlite") and os.path.isdir("/data") and os.access("/data", os.W_OK):
    DATABASE_URL = "sqlite:////data/todo.db"

ALLOWED_ORIGINS_RAW = os.getenv("ALLOWED_ORIGINS", "*")
ALLOWED_ORIGINS = [o.strip() for o in ALLOWED_ORIGINS_RAW.split(",") if o.strip()] or ["*"]

# ── DB Setup ──────────────────────────────────────────────────────────────────
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ── Models ────────────────────────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"
    id         = Column(Integer, primary_key=True, index=True)
    username   = Column(String(50), unique=True, index=True, nullable=False)
    email      = Column(String(120), unique=True, index=True, nullable=False)
    hashed_pw  = Column(String, nullable=False)
    is_admin   = Column(Boolean, default=False)
    is_active  = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    lists      = relationship("TodoList", back_populates="owner", cascade="all, delete")

class TodoList(Base):
    __tablename__ = "todo_lists"
    id         = Column(Integer, primary_key=True, index=True)
    name       = Column(String(200), nullable=False)
    color      = Column(String(20), default="#1e2024")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    owner_id   = Column(Integer, ForeignKey("users.id"), nullable=False)
    owner      = relationship("User", back_populates="lists")
    items      = relationship("TodoItem", back_populates="todo_list", cascade="all, delete", order_by="TodoItem.position")

class TodoItem(Base):
    __tablename__ = "todo_items"
    id          = Column(Integer, primary_key=True, index=True)
    text        = Column(String(500), nullable=False)
    done        = Column(Boolean, default=False)
    priority    = Column(String(10), default="normal")   # low | normal | high
    due_date    = Column(DateTime, nullable=True)
    position    = Column(Integer, default=0)
    created_at  = Column(DateTime, default=datetime.utcnow)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    list_id     = Column(Integer, ForeignKey("todo_lists.id"), nullable=False)
    todo_list   = relationship("TodoList", back_populates="items")

Base.metadata.create_all(bind=engine)

# ── Auth Helpers ──────────────────────────────────────────────────────────────
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def hash_password(pw: str) -> str: return pwd_ctx.hash(pw)
def verify_password(plain: str, hashed: str) -> bool: return pwd_ctx.verify(plain, hashed)

def create_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    payload = data.copy()
    payload.update({"exp": datetime.utcnow() + (expires_delta or timedelta(minutes=15))})
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    exc = HTTPException(status_code=401, detail="Ungültiges Token", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload  = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username: raise exc
    except JWTError: raise exc
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_active: raise exc
    return user

def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(403, "Admin-Rechte erforderlich")
    return current_user

# ── Schemas ───────────────────────────────────────────────────────────────────
class UserCreate(BaseModel):
    username: str; email: str; password: str

class UserOut(BaseModel):
    id: int; username: str; email: str; is_admin: bool; is_active: bool; created_at: datetime
    class Config: from_attributes = True

class TokenOut(BaseModel):
    access_token: str; token_type: str; user: UserOut

class TodoItemCreate(BaseModel):
    text: str
    priority: str = "normal"
    due_date: Optional[datetime] = None
    position: int = 0

class TodoItemUpdate(BaseModel):
    text: Optional[str] = None
    done: Optional[bool] = None
    priority: Optional[str] = None
    due_date: Optional[datetime] = None
    position: Optional[int] = None

class TodoItemOut(BaseModel):
    id: int; text: str; done: bool; priority: str
    due_date: Optional[datetime]; position: int
    created_at: datetime; updated_at: datetime; list_id: int
    class Config: from_attributes = True

class TodoListCreate(BaseModel):
    name: str; color: str = "#1e2024"

class TodoListUpdate(BaseModel):
    name: Optional[str] = None; color: Optional[str] = None

class TodoListOut(BaseModel):
    id: int; name: str; color: str; created_at: datetime; updated_at: datetime
    owner_id: int; items: List[TodoItemOut] = []
    class Config: from_attributes = True

class TodoListShort(BaseModel):
    id: int; name: str; color: str; created_at: datetime; updated_at: datetime
    owner_id: int; item_count: int = 0; done_count: int = 0
    class Config: from_attributes = True

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="ToDo-Backend", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS,
                  allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# ── Auth ──────────────────────────────────────────────────────────────────────
@app.post("/auth/register", response_model=TokenOut, status_code=201)
def register(data: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(400, "Benutzername bereits vergeben")
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(400, "E-Mail bereits registriert")
    if len(data.password) < 8:
        raise HTTPException(400, "Passwort muss mindestens 8 Zeichen haben")
    is_admin = db.query(User).count() == 0
    user = User(username=data.username, email=data.email,
                hashed_pw=hash_password(data.password), is_admin=is_admin)
    db.add(user); db.commit(); db.refresh(user)
    token = create_token({"sub": user.username}, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    return {"access_token": token, "token_type": "bearer", "user": user}

@app.post("/auth/login", response_model=TokenOut)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form.username).first()
    if not user or not verify_password(form.password, user.hashed_pw):
        raise HTTPException(401, "Benutzername oder Passwort falsch")
    if not user.is_active:
        raise HTTPException(403, "Konto gesperrt")
    token = create_token({"sub": user.username}, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    return {"access_token": token, "token_type": "bearer", "user": user}

@app.get("/auth/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)): return current_user

# ── Listen ────────────────────────────────────────────────────────────────────
@app.get("/lists", response_model=List[TodoListShort])
def get_lists(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lists = db.query(TodoList).filter(TodoList.owner_id == current_user.id)\
              .order_by(TodoList.updated_at.desc()).all()
    result = []
    for lst in lists:
        result.append(TodoListShort(
            id=lst.id, name=lst.name, color=lst.color,
            created_at=lst.created_at, updated_at=lst.updated_at,
            owner_id=lst.owner_id,
            item_count=len(lst.items),
            done_count=sum(1 for i in lst.items if i.done)
        ))
    return result

@app.post("/lists", response_model=TodoListOut, status_code=201)
def create_list(data: TodoListCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lst = TodoList(**data.model_dump(), owner_id=current_user.id)
    db.add(lst); db.commit(); db.refresh(lst)
    return lst

@app.get("/lists/{list_id}", response_model=TodoListOut)
def get_list(list_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lst = db.query(TodoList).filter(TodoList.id == list_id, TodoList.owner_id == current_user.id).first()
    if not lst: raise HTTPException(404, "Liste nicht gefunden")
    return lst

@app.put("/lists/{list_id}", response_model=TodoListOut)
def update_list(list_id: int, data: TodoListUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lst = db.query(TodoList).filter(TodoList.id == list_id, TodoList.owner_id == current_user.id).first()
    if not lst: raise HTTPException(404, "Liste nicht gefunden")
    for f, v in data.model_dump(exclude_unset=True).items(): setattr(lst, f, v)
    lst.updated_at = datetime.utcnow()
    db.commit(); db.refresh(lst); return lst

@app.delete("/lists/{list_id}", status_code=204)
def delete_list(list_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lst = db.query(TodoList).filter(TodoList.id == list_id, TodoList.owner_id == current_user.id).first()
    if not lst: raise HTTPException(404, "Liste nicht gefunden")
    db.delete(lst); db.commit()

# ── Items ─────────────────────────────────────────────────────────────────────
def _get_list_for_user(list_id: int, user_id: int, db: Session) -> TodoList:
    lst = db.query(TodoList).filter(TodoList.id == list_id, TodoList.owner_id == user_id).first()
    if not lst: raise HTTPException(404, "Liste nicht gefunden")
    return lst

@app.post("/lists/{list_id}/items", response_model=TodoItemOut, status_code=201)
def add_item(list_id: int, data: TodoItemCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lst = _get_list_for_user(list_id, current_user.id, db)
    item = TodoItem(**data.model_dump(), list_id=lst.id)
    db.add(item); db.commit(); db.refresh(item)
    lst.updated_at = datetime.utcnow(); db.commit()
    return item

@app.patch("/lists/{list_id}/items/{item_id}", response_model=TodoItemOut)
def update_item(list_id: int, item_id: int, data: TodoItemUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_list_for_user(list_id, current_user.id, db)
    item = db.query(TodoItem).filter(TodoItem.id == item_id, TodoItem.list_id == list_id).first()
    if not item: raise HTTPException(404, "Item nicht gefunden")
    for f, v in data.model_dump(exclude_unset=True).items(): setattr(item, f, v)
    item.updated_at = datetime.utcnow()
    db.commit(); db.refresh(item); return item

@app.delete("/lists/{list_id}/items/{item_id}", status_code=204)
def delete_item(list_id: int, item_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_list_for_user(list_id, current_user.id, db)
    item = db.query(TodoItem).filter(TodoItem.id == item_id, TodoItem.list_id == list_id).first()
    if not item: raise HTTPException(404, "Item nicht gefunden")
    db.delete(item); db.commit()

@app.delete("/lists/{list_id}/items/done/clear", status_code=204)
def clear_done(list_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_list_for_user(list_id, current_user.id, db)
    db.query(TodoItem).filter(TodoItem.list_id == list_id, TodoItem.done == True).delete()
    db.commit()

# ── Admin ─────────────────────────────────────────────────────────────────────
@app.get("/admin/users", response_model=List[UserOut])
def admin_list_users(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return db.query(User).order_by(User.created_at.desc()).all()

@app.patch("/admin/users/{user_id}/toggle-active", response_model=UserOut)
def admin_toggle_active(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user: raise HTTPException(404, "User nicht gefunden")
    if user.id == admin.id: raise HTTPException(400, "Eigenes Konto kann nicht gesperrt werden")
    user.is_active = not user.is_active; db.commit(); db.refresh(user); return user

@app.patch("/admin/users/{user_id}/toggle-admin", response_model=UserOut)
def admin_toggle_admin(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user: raise HTTPException(404, "User nicht gefunden")
    if user.id == admin.id: raise HTTPException(400, "Eigene Admin-Rechte können nicht entzogen werden")
    user.is_admin = not user.is_admin; db.commit(); db.refresh(user); return user

@app.delete("/admin/users/{user_id}", status_code=204)
def admin_delete_user(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user: raise HTTPException(404, "User nicht gefunden")
    if user.id == admin.id: raise HTTPException(400, "Eigenes Konto kann nicht gelöscht werden")
    db.delete(user); db.commit()

@app.get("/admin/stats")
def admin_stats(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return {
        "total_users": db.query(User).count(),
        "active_users": db.query(User).filter(User.is_active == True).count(),
        "total_lists": db.query(TodoList).count(),
        "total_items": db.query(TodoItem).count(),
        "done_items": db.query(TodoItem).filter(TodoItem.done == True).count(),
    }

@app.get("/")
def root(): return {"service": "todo-backend", "version": "1.0.0", "docs": "/docs"}
