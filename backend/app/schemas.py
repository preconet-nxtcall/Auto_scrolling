from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator

class UserSettingsResponse(BaseModel):
    global_scroll_speed: int = Field(default=50, ge=10, le=500)
    global_repeat_count: int = Field(default=3, ge=1, le=50)
    global_interaction_pause: int = Field(default=3000, ge=500, le=30000)
    global_start_delay: int = Field(default=2000, ge=0, le=10000)
    global_between_repeats_delay: int = Field(default=1000, ge=0, le=10000)
    global_between_documents_delay: int = Field(default=2000, ge=0, le=10000)

    model_config = ConfigDict(from_attributes=True)

class UserSettingsUpdate(BaseModel):
    global_scroll_speed: Optional[int] = Field(default=None, ge=10, le=500)
    global_repeat_count: Optional[int] = Field(default=None, ge=1, le=50)
    global_interaction_pause: Optional[int] = Field(default=None, ge=500, le=30000)
    global_start_delay: Optional[int] = Field(default=None, ge=0, le=10000)
    global_between_repeats_delay: Optional[int] = Field(default=None, ge=0, le=10000)
    global_between_documents_delay: Optional[int] = Field(default=None, ge=0, le=10000)

class DocumentBase(BaseModel):
    title: Optional[str] = None
    scroll_speed: Optional[int] = 50
    repeat_count: Optional[int] = 3
    sequence_order: Optional[int] = 0

class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    scroll_speed: Optional[int] = None
    repeat_count: Optional[int] = None
    interaction_pause: Optional[int] = None
    start_delay: Optional[int] = None
    between_repeats_delay: Optional[int] = None
    between_documents_delay: Optional[int] = None
    sequence_order: Optional[int] = None

    @field_validator('scroll_speed')
    @classmethod
    def validate_scroll_speed(cls, v):
        if v is not None and (v < 10 or v > 500):
            raise ValueError('scroll_speed must be between 10 and 500 px/sec')
        return v

    @field_validator('repeat_count')
    @classmethod
    def validate_repeat_count(cls, v):
        if v is not None and (v < 1 or v > 50):
            raise ValueError('repeat_count must be between 1 and 50 cycles')
        return v

    @field_validator('interaction_pause')
    @classmethod
    def validate_interaction_pause(cls, v):
        if v is not None and (v < 500 or v > 30000):
            raise ValueError('interaction_pause must be between 500ms and 30000ms')
        return v

    @field_validator('start_delay', 'between_repeats_delay', 'between_documents_delay')
    @classmethod
    def validate_delays(cls, v):
        if v is not None and (v < 0 or v > 10000):
            raise ValueError('delay must be between 0ms and 10000ms')
        return v

class BatchConfigUpdate(BaseModel):
    document_ids: List[int]
    scroll_speed: Optional[int] = None
    repeat_count: Optional[int] = None

class DocumentResponse(BaseModel):
    id: int
    user_id: int
    original_filename: str
    original_extension: str
    original_mime_type: str
    original_file_size: int
    original_file_path: str
    pdf_file_path: Optional[str] = None
    conversion_status: str
    conversion_error: Optional[str] = None
    page_count: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    title: str
    scroll_speed: Optional[int] = None
    repeat_count: Optional[int] = None
    interaction_pause: Optional[int] = None
    start_delay: Optional[int] = None
    between_repeats_delay: Optional[int] = None
    between_documents_delay: Optional[int] = None
    sequence_order: int

    effective_settings: Optional[Dict[str, Any]] = None

    # Backward-compatible Computed Aliases for Frontend Compatibility
    @property
    def status(self) -> str:
        return self.conversion_status

    @property
    def total_pages(self) -> int:
        return self.page_count

    @property
    def file_size_bytes(self) -> int:
        return self.original_file_size

    @property
    def original_format(self) -> str:
        return self.original_extension

    @property
    def pdf_path(self) -> Optional[str]:
        return self.pdf_file_path

    @property
    def error_message(self) -> Optional[str]:
        return self.conversion_error

    model_config = ConfigDict(from_attributes=True)
