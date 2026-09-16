from sqlalchemy import Column, String, Integer, BigInteger, Boolean, ForeignKey, Table
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, relationship
from backend.core.database import Base

# Junction table for apps and categories (Many-to-Many)
# cascade delete configuration is handled at the SQL level via ForeignKey constraint ondelete='CASCADE'
app_categories = Table(
    'app_categories',
    Base.metadata,
    Column('app_id', String(255), ForeignKey('apps.id', ondelete='CASCADE'), primary_key=True),
    Column('category_name', String(100), ForeignKey('categories.name', ondelete='CASCADE'), primary_key=True)
)

class App(Base):
    __tablename__ = 'apps'
    
    id: Mapped[str] = Column(String(255), primary_key=True)
    name: Mapped[str] = Column(String(255), nullable=False)
    url = Column(String(1024), nullable=False)
    override_source = Column(String(50), nullable=True)
    preferred_apk_index = Column(Integer, nullable=True)
    pinned = Column(Boolean, nullable=False, default=False)
    allow_id_change = Column(Boolean, nullable=False, default=False)
    additional_settings = Column(JSON, nullable=False, default=dict)
    
    # Relationship to Category
    categories: Mapped[list['Category']] = relationship('Category', secondary=app_categories, back_populates='apps')
    
    # Relationship to LocalAppAPK
    apks: Mapped[list['LocalAppAPK']] = relationship('LocalAppAPK', back_populates='app', cascade='all, delete-orphan')

class LocalAppAPK(Base):
    __tablename__ = 'local_app_apks'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    app_id: Mapped[str] = Column(String(255), ForeignKey('apps.id', ondelete='CASCADE'), nullable=False)
    file_hash = Column(String(64), nullable=False)
    version: Mapped[str] = Column(String(50), nullable=False)
    architecture = Column(String(50), nullable=True)
    
    app: Mapped['App'] = relationship('App', back_populates='apks')

class Category(Base):
    __tablename__ = 'categories'
    
    name = Column(String(100), primary_key=True)
    color = Column(BigInteger, nullable=False)  # Handles 32-bit unsigned integer ARGB
    
    # Relationship to App
    apps: Mapped[list['App']] = relationship('App', secondary=app_categories, back_populates='categories')

class Setting(Base):
    __tablename__ = 'settings'
    
    key = Column(String(100), primary_key=True)
    value = Column(JSON, nullable=False)
