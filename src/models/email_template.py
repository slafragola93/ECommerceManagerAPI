from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import relationship

from src.database import Base

EMAIL_PURPOSES = ("order_shipped", "invoice", "receipt", "credit_note")
SUPPORTED_LOCALES = ("it", "en", "fr", "de", "es")
ORDER_STATE_SHIPPED = 3


class EmailTemplate(Base):
    __tablename__ = "email_templates"

    id_email_template = Column(Integer, primary_key=True, index=True)
    code = Column(String(80), nullable=False, unique=True, index=True)
    name = Column(String(200), nullable=False)
    purpose = Column(String(40), nullable=False, index=True)
    is_default = Column(Boolean, nullable=False, default=False, server_default="0")
    is_active = Column(Boolean, nullable=False, default=True, server_default="1")
    allowed_variables = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=True, server_default=func.now())
    updated_at = Column(DateTime, nullable=True, server_default=func.now(), onupdate=func.now())

    translations = relationship(
        "EmailTemplateTranslation",
        back_populates="template",
        cascade="all, delete-orphan",
    )


class EmailTemplateTranslation(Base):
    __tablename__ = "email_template_translations"
    __table_args__ = (
        UniqueConstraint("id_email_template", "locale", name="uq_email_template_locale"),
    )

    id_email_template_translation = Column(Integer, primary_key=True, index=True)
    id_email_template = Column(
        Integer,
        ForeignKey("email_templates.id_email_template", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    locale = Column(String(10), nullable=False)
    subject = Column(String(255), nullable=False)
    body_html = Column(Text, nullable=False)
    body_text = Column(Text, nullable=True)

    template = relationship("EmailTemplate", back_populates="translations")
