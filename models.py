from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey
from datetime import datetime, date

db = SQLAlchemy()

class Runner(db.Model):
    __tablename__ = "runners"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    photo_path = db.Column(db.String(255), nullable=True)  # relatif à /static (e.g., "uploads/xxx.jpg")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    entries = relationship("Entry", back_populates="runner", cascade="all, delete-orphan")

class CurrentChallenge(db.Model):
    __tablename__ = "current_challenge"
    id = db.Column(db.Integer, primary_key=True)  # toujours 1
    goal_km = db.Column(db.Float, nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)

class ChallengeHistory(db.Model):
    __tablename__ = "challenge_history"
    id = db.Column(db.Integer, primary_key=True)
    goal_km = db.Column(db.Float, nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    winner_runner_id = db.Column(db.Integer, ForeignKey("runners.id", ondelete="SET NULL"), nullable=True)
    winner_name = db.Column(db.String(200), nullable=True)
    winner_total_km = db.Column(db.Float, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    winner_runner = relationship("Runner")
    results = relationship("ChallengeResult", back_populates="challenge", cascade="all, delete-orphan")

class Entry(db.Model):
    __tablename__ = "entries"
    id = db.Column(db.Integer, primary_key=True)
    runner_id = db.Column(db.Integer, ForeignKey("runners.id", ondelete="CASCADE"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    distance_km = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=True)

    runner = relationship("Runner", back_populates="entries")

class ChallengeResult(db.Model):
    __tablename__ = "challenge_results"
    id = db.Column(db.Integer, primary_key=True)
    challenge_history_id = db.Column(db.Integer, ForeignKey("challenge_history.id", ondelete="CASCADE"), nullable=False)
    runner_id = db.Column(db.Integer, ForeignKey("runners.id", ondelete="SET NULL"), nullable=True)
    runner_name = db.Column(db.String(200), nullable=False)
    total_km = db.Column(db.Float, nullable=False)

    challenge = relationship("ChallengeHistory", back_populates="results")
    runner = relationship("Runner")

def init_db():
    db.create_all()
