from sqlalchemy import (
    Column, Integer, String, BigInteger, Text, DateTime, ForeignKey, Boolean, LargeBinary, func
)
from sqlalchemy.orm import relationship
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=True)
    role = Column(String(50), default="MEMBER", index=True)
    is_active = Column(Boolean, default=True, index=True)
    
    # Global Default Auto-Scroll Settings
    global_scroll_speed = Column(Integer, default=50, nullable=False)            # px/sec
    global_repeat_count = Column(Integer, default=3, nullable=False)             # cycles
    global_interaction_pause = Column(Integer, default=3000, nullable=False)     # ms
    global_start_delay = Column(Integer, default=2000, nullable=False)           # ms
    global_between_repeats_delay = Column(Integer, default=1000, nullable=False) # ms
    global_between_documents_delay = Column(Integer, default=2000, nullable=False) # ms

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    documents = relationship("Document", back_populates="user", cascade="all, delete-orphan")

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False, default=1)
    
    # Core Document Metadata Fields
    original_filename = Column(String(255), nullable=False)
    original_extension = Column(String(50), nullable=False)
    original_mime_type = Column(String(100), nullable=False)
    original_file_size = Column(BigInteger, nullable=False)
    original_file_path = Column(String(500), nullable=False)
    
    # Database Binary Storage (Stores file data directly inside database)
    original_file_data = Column(LargeBinary, nullable=True)
    pdf_file_data = Column(LargeBinary, nullable=True)

    pdf_file_path = Column(String(500), nullable=True)
    conversion_status = Column(String(50), default="uploaded", index=True)  # uploaded, processing, completed, failed
    conversion_error = Column(Text, nullable=True)
    page_count = Column(Integer, default=0)
    
    # Auto-Viewer & Presentation Customizations (Nullable = Inherit Global Setting)
    title = Column(String(255), nullable=False)
    scroll_speed = Column(Integer, nullable=True)             # px/sec (None = Inherit)
    repeat_count = Column(Integer, nullable=True)            # cycles (None = Inherit)
    interaction_pause = Column(Integer, nullable=True)       # ms (None = Inherit)
    start_delay = Column(Integer, nullable=True)             # ms (None = Inherit)
    between_repeats_delay = Column(Integer, nullable=True)   # ms (None = Inherit)
    between_documents_delay = Column(Integer, nullable=True) # ms (None = Inherit)
    sequence_order = Column(Integer, default=0)              # playlist order index
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="documents")

    def get_effective_settings(self, user: User = None) -> dict:
        target_user = user or self.user
        g_speed = target_user.global_scroll_speed if target_user else 50
        g_repeat = target_user.global_repeat_count if target_user else 3
        g_pause = target_user.global_interaction_pause if target_user else 3000
        g_start = target_user.global_start_delay if target_user else 2000
        g_between_rep = target_user.global_between_repeats_delay if target_user else 1000
        g_between_doc = target_user.global_between_documents_delay if target_user else 2000

        return {
            "scroll_speed": self.scroll_speed if self.scroll_speed is not None else g_speed,
            "repeat_count": self.repeat_count if self.repeat_count is not None else g_repeat,
            "interaction_pause": self.interaction_pause if self.interaction_pause is not None else g_pause,
            "start_delay": self.start_delay if self.start_delay is not None else g_start,
            "between_repeats_delay": self.between_repeats_delay if self.between_repeats_delay is not None else g_between_rep,
            "between_documents_delay": self.between_documents_delay if self.between_documents_delay is not None else g_between_doc,
        }

    # Property aliases for backward-compatibility with frontend
    @property
    def status(self) -> str:
        return self.conversion_status

    @status.setter
    def status(self, value: str):
        self.conversion_status = value

    @property
    def total_pages(self) -> int:
        return self.page_count

    @total_pages.setter
    def total_pages(self, value: int):
        self.page_count = value

    @property
    def file_size_bytes(self) -> int:
        return self.original_file_size

    @property
    def original_format(self) -> str:
        return self.original_extension

    @property
    def pdf_path(self) -> str:
        return self.pdf_file_path

    @pdf_path.setter
    def pdf_path(self, value: str):
        self.pdf_file_path = value

    @property
    def error_message(self) -> str:
        return self.conversion_error

    @error_message.setter
    def error_message(self, value: str):
        self.conversion_error = value
