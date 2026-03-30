from sqlalchemy import (
    Column, String, Integer, Boolean,
    DateTime, ForeignKey, Float, Text, JSON
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import uuid


def generate_uuid():
    return str(uuid.uuid4())


# ─── Venue ───────────────────────────────────────────────────

class Venue(Base):
    __tablename__ = "venues"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False)  # arrows-bar
    subscription_tier = Column(String, default="basic") # basic / pro / enterprise
    weekly_report_email = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    tables = relationship("Table", back_populates="venue")
    sessions = relationship("Session", back_populates="venue")


# ─── Table ───────────────────────────────────────────────────

class Table(Base):
    __tablename__ = "tables"

    id = Column(String, primary_key=True, default=generate_uuid)
    venue_id = Column(String, ForeignKey("venues.id"), nullable=False)
    table_number = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    venue = relationship("Venue", back_populates="tables")
    players = relationship("Player", back_populates="table")


# ─── Session ─────────────────────────────────────────────────

class Session(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True, default=generate_uuid)
    venue_id = Column(String, ForeignKey("venues.id"), nullable=False)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    ended_at = Column(DateTime(timezone=True), nullable=True)
    game_mode = Column(String, default="auto")  # auto / manual
    date = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    venue = relationship("Venue", back_populates="sessions")
    players = relationship("Player", back_populates="session")
    game_rounds = relationship("GameRound", back_populates="session")
    game_lobbies = relationship("GameLobby", back_populates="session")


# ─── Player ──────────────────────────────────────────────────

class Player(Base):
    __tablename__ = "players"

    id = Column(String, primary_key=True, default=generate_uuid)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    table_id = Column(String, ForeignKey("tables.id"), nullable=False)
    display_name = Column(String, nullable=False)
    token = Column(String, unique=True, nullable=False)
    contact = Column(String, nullable=True)       # phone or email
    is_remembered = Column(Boolean, default=False)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    last_seen_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    session = relationship("Session", back_populates="players")
    table = relationship("Table", back_populates="players")
    answers = relationship("Answer", back_populates="player")
    lobbies = relationship("LobbyPlayer", back_populates="player")


# ─── Question ────────────────────────────────────────────────

class Question(Base):
    __tablename__ = "questions"

    id = Column(String, primary_key=True, default=generate_uuid)
    game_type = Column(String, nullable=False)   # trivia / table_vs_table / hangman / emoji
    content = Column(Text, nullable=False)
    correct_answer = Column(String, nullable=False)
    difficulty = Column(String, default="medium") # easy / medium / hard
    category = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    answers = relationship("Answer", back_populates="question")
    venue_history = relationship("VenueQuestionHistory", back_populates="question")


# ─── Venue Question History ──────────────────────────────────

class VenueQuestionHistory(Base):
    __tablename__ = "venue_question_history"

    id = Column(String, primary_key=True, default=generate_uuid)
    venue_id = Column(String, ForeignKey("venues.id"), nullable=False)
    question_id = Column(String, ForeignKey("questions.id"), nullable=False)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    used_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    question = relationship("Question", back_populates="venue_history")


# ─── Game Round ──────────────────────────────────────────────

class GameRound(Base):
    __tablename__ = "game_rounds"

    id = Column(String, primary_key=True, default=generate_uuid)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    game_type = Column(String, nullable=False)   # trivia / table_vs_table
    question_id = Column(String, ForeignKey("questions.id"), nullable=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    ended_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String, default="waiting")   # waiting / active / completed

    # Relationships
    session = relationship("Session", back_populates="game_rounds")
    answers = relationship("Answer", back_populates="round")
    table_scores = relationship("TableRoundScore", back_populates="round")


# ─── Answer ──────────────────────────────────────────────────

class Answer(Base):
    __tablename__ = "answers"

    id = Column(String, primary_key=True, default=generate_uuid)
    player_id = Column(String, ForeignKey("players.id"), nullable=False)
    question_id = Column(String, ForeignKey("questions.id"), nullable=False)
    round_id = Column(String, ForeignKey("game_rounds.id"), nullable=False)
    submitted_answer = Column(String, nullable=False)
    is_correct = Column(Boolean, nullable=False)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())
    response_time_ms = Column(Integer, nullable=False)  # milliseconds

    # Relationships
    player = relationship("Player", back_populates="answers")
    question = relationship("Question", back_populates="answers")
    round = relationship("GameRound", back_populates="answers")


# ─── Table Round Score ───────────────────────────────────────

class TableRoundScore(Base):
    __tablename__ = "table_round_scores"

    id = Column(String, primary_key=True, default=generate_uuid)
    round_id = Column(String, ForeignKey("game_rounds.id"), nullable=False)
    table_id = Column(String, ForeignKey("tables.id"), nullable=False)
    total_correct = Column(Integer, default=0)
    avg_response_time_ms = Column(Float, default=0.0)
    final_score = Column(Float, default=0.0)
    winner = Column(Boolean, default=False)

    # Relationships
    round = relationship("GameRound", back_populates="table_scores")


# ─── Game Lobby ──────────────────────────────────────────────

class GameLobby(Base):
    __tablename__ = "game_lobbies"

    id = Column(String, primary_key=True, default=generate_uuid)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    game_type = Column(String, nullable=False)   # ludo / chess / snakes / hangman / emoji
    created_by_player_id = Column(String, ForeignKey("players.id"), nullable=False)
    table_id = Column(String, ForeignKey("tables.id"), nullable=False)
    is_open = Column(Boolean, default=False)     # False = table only, True = whole venue
    status = Column(String, default="waiting")   # waiting / active / completed
    max_players = Column(Integer, default=4)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    session = relationship("Session", back_populates="game_lobbies")
    players = relationship("LobbyPlayer", back_populates="lobby")
    game_state = relationship("GameState", back_populates="lobby", uselist=False)


# ─── Lobby Player ────────────────────────────────────────────

class LobbyPlayer(Base):
    __tablename__ = "lobby_players"

    id = Column(String, primary_key=True, default=generate_uuid)
    lobby_id = Column(String, ForeignKey("game_lobbies.id"), nullable=False)
    player_id = Column(String, ForeignKey("players.id"), nullable=False)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String, default="waiting")   # waiting / playing / left

    # Relationships
    lobby = relationship("GameLobby", back_populates="players")
    player = relationship("Player", back_populates="lobbies")


# ─── Game State ──────────────────────────────────────────────

class GameState(Base):
    __tablename__ = "game_states"

    id = Column(String, primary_key=True, default=generate_uuid)
    lobby_id = Column(String, ForeignKey("game_lobbies.id"), unique=True, nullable=False)
    current_state = Column(JSON, nullable=False)  # flexible per game type
    last_updated_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    lobby = relationship("GameLobby", back_populates="game_state")


# ─── Analytics Snapshot ──────────────────────────────────────

class AnalyticsSnapshot(Base):
    __tablename__ = "analytics_snapshots"

    id = Column(String, primary_key=True, default=generate_uuid)
    venue_id = Column(String, ForeignKey("venues.id"), nullable=False)
    week_start_date = Column(DateTime(timezone=True), nullable=False)
    total_scans = Column(Integer, default=0)
    avg_dwell_time_minutes = Column(Float, default=0.0)
    ghost_players = Column(Integer, default=0)
    remembered_players = Column(Integer, default=0)
    returning_players = Column(Integer, default=0)
    best_performing_game = Column(String, nullable=True)
    best_night = Column(String, nullable=True)
    cross_table_interactions = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())