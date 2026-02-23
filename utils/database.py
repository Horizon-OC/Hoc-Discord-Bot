import aiosqlite
from pathlib import Path
from typing import List, Optional, Tuple
from datetime import datetime
from config import Config
from utils.logger import bot_logger

class Database:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or Config.DATABASE_PATH
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
    async def connect(self):
        """Initialize database connection and create tables"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS guild_config (
                    guild_id INTEGER PRIMARY KEY,
                    mod_role_id INTEGER,
                    log_channel_id INTEGER,
                    prefix TEXT DEFAULT '?',
                    log_joins INTEGER DEFAULT 1,
                    log_leaves INTEGER DEFAULT 1,
                    log_bans INTEGER DEFAULT 1,
                    log_kicks INTEGER DEFAULT 1,
                    log_warnings INTEGER DEFAULT 1,
                    log_mutes INTEGER DEFAULT 1,
                    log_message_deletes INTEGER DEFAULT 0,
                    log_message_edits INTEGER DEFAULT 0,
                    starboard_channel_id INTEGER DEFAULT NULL,
                    starboard_threshold INTEGER DEFAULT 3,
                    sobboard_channel_id INTEGER DEFAULT NULL,
                    sobboard_threshold INTEGER DEFAULT 3,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Migrate existing tables: add starboard/sobboard columns if they don't exist yet
            for col, default in [
                ("starboard_channel_id", "NULL"),
                ("starboard_threshold",  "3"),
                ("sobboard_channel_id", "NULL"),
                ("sobboard_threshold",  "3"),
            ]:
                try:
                    await db.execute(
                        f"ALTER TABLE guild_config ADD COLUMN {col} INTEGER DEFAULT {default}"
                    )
                except Exception:
                    pass  # Column already exists — that's fine
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    moderator_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    reason TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (guild_id) REFERENCES guild_config(guild_id)
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS warnings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    moderator_id INTEGER NOT NULL,
                    reason TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    active INTEGER DEFAULT 1,
                    FOREIGN KEY (guild_id) REFERENCES guild_config(guild_id)
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS temp_bans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    reason TEXT,
                    FOREIGN KEY (guild_id) REFERENCES guild_config(guild_id)
                )
            """)
            
            # Indexes
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_actions_user 
                ON actions(guild_id, user_id)
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_warnings_user 
                ON warnings(guild_id, user_id, active)
            """)
            
            await db.commit()
            bot_logger.info("Database initialized successfully")
    
    # ──────────────────────────────────────────────────────────────────
    # Guild config
    # ──────────────────────────────────────────────────────────────────

    async def get_guild_config(self, guild_id: int) -> Optional[dict]:
        """Get guild configuration"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM guild_config WHERE guild_id = ?",
                (guild_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None
    
    async def set_mod_role(self, guild_id: int, role_id: int):
        """Set moderator role for a guild"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO guild_config (guild_id, mod_role_id)
                VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET mod_role_id = ?
            """, (guild_id, role_id, role_id))
            await db.commit()
    
    async def set_log_channel(self, guild_id: int, channel_id: int):
        """Set log channel for a guild"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO guild_config (guild_id, log_channel_id)
                VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET log_channel_id = ?
            """, (guild_id, channel_id, channel_id))
            await db.commit()
    
    async def update_log_settings(self, guild_id: int, **settings):
        """Update log settings for a guild"""
        valid_settings = {
            'log_joins', 'log_leaves', 'log_bans', 'log_kicks',
            'log_warnings', 'log_mutes', 'log_message_deletes', 'log_message_edits'
        }
        
        updates = {k: v for k, v in settings.items() if k in valid_settings}
        if not updates:
            return
        
        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [guild_id]
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(f"""
                INSERT INTO guild_config (guild_id, {', '.join(updates.keys())})
                VALUES (?, {', '.join(['?'] * len(updates))})
                ON CONFLICT(guild_id) DO UPDATE SET {set_clause}
            """, [guild_id] + list(updates.values()) + list(updates.values()))
            await db.commit()

    # ──────────────────────────────────────────────────────────────────
    # Starboard / Sobboard
    # ──────────────────────────────────────────────────────────────────

    async def set_starboard_channel(
        self, guild_id: int, channel_id: Optional[int], threshold: int = 3
    ):
        """Set (or clear) the starboard channel and threshold for a guild."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO guild_config (guild_id, starboard_channel_id, starboard_threshold)
                VALUES (?, ?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    starboard_channel_id = excluded.starboard_channel_id,
                    starboard_threshold  = excluded.starboard_threshold
                """,
                (guild_id, channel_id, threshold),
            )
            await db.commit()

    async def set_sobboard_channel(
        self, guild_id: int, channel_id: Optional[int], threshold: int = 3
    ):
        """Set (or clear) the sobboard channel and threshold for a guild."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO guild_config (guild_id, sobboard_channel_id, sobboard_threshold)
                VALUES (?, ?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    sobboard_channel_id = excluded.sobboard_channel_id,
                    sobboard_threshold  = excluded.sobboard_threshold
                """,
                (guild_id, channel_id, threshold),
            )
            await db.commit()

    # ──────────────────────────────────────────────────────────────────
    # Moderation actions & warnings
    # ──────────────────────────────────────────────────────────────────

    async def log_action(self, guild_id: int, user_id: int, moderator_id: int,
                        action: str, reason: Optional[str] = None):
        """Log a moderation action"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO actions (guild_id, user_id, moderator_id, action, reason)
                VALUES (?, ?, ?, ?, ?)
            """, (guild_id, user_id, moderator_id, action, reason))
            await db.commit()
    
    async def add_warning(self, guild_id: int, user_id: int, moderator_id: int,
                         reason: Optional[str] = None) -> int:
        """Add a warning to a user"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO warnings (guild_id, user_id, moderator_id, reason)
                VALUES (?, ?, ?, ?)
            """, (guild_id, user_id, moderator_id, reason))
            await db.commit()
            return cursor.lastrowid
    
    async def get_warnings(self, guild_id: int, user_id: int) -> List[dict]:
        """Get all active warnings for a user"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT * FROM warnings 
                WHERE guild_id = ? AND user_id = ? AND active = 1
                ORDER BY timestamp DESC
            """, (guild_id, user_id)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def clear_warnings(self, guild_id: int, user_id: int):
        """Clear all warnings for a user"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE warnings SET active = 0
                WHERE guild_id = ? AND user_id = ?
            """, (guild_id, user_id))
            await db.commit()
    
    async def remove_warning(self, warning_id: int) -> bool:
        """Remove a specific warning"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                UPDATE warnings SET active = 0
                WHERE id = ?
            """, (warning_id,))
            await db.commit()
            return cursor.rowcount > 0
    
    async def get_user_actions(self, guild_id: int, user_id: int, 
                              action: Optional[str] = None) -> List[dict]:
        """Get all actions for a user"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if action:
                query = """
                    SELECT * FROM actions 
                    WHERE guild_id = ? AND user_id = ? AND action = ?
                    ORDER BY timestamp DESC
                """
                params = (guild_id, user_id, action)
            else:
                query = """
                    SELECT * FROM actions 
                    WHERE guild_id = ? AND user_id = ?
                    ORDER BY timestamp DESC
                """
                params = (guild_id, user_id)
            
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
