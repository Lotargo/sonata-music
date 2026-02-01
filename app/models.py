import os
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

class Track(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    original_path = db.Column(db.String(512), nullable=False)
    processed_path = db.Column(db.String(512), nullable=True)
    status = db.Column(db.String(50), default='pending')  # pending, processing, completed, failed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Metadata fields
    title = db.Column(db.String(255), nullable=True)
    artist = db.Column(db.String(255), nullable=True)
    cover_path = db.Column(db.String(512), nullable=True)

    # Target settings
    target_format = db.Column(db.String(10), nullable=True)
    target_sample_rate = db.Column(db.Integer, nullable=True)
    target_bitrate = db.Column(db.String(20), nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'filename': self.filename,
            'title': self.title or self.filename,
            'artist': self.artist or 'Unknown Artist',
            'cover_path': self.cover_path,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'original_path': self.original_path,
            'processed_path': os.path.basename(self.processed_path) if self.processed_path else None,
            'target_format': self.target_format,
            'target_sample_rate': self.target_sample_rate,
            'target_bitrate': self.target_bitrate
        }
