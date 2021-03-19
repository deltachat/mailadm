import os
import sqlite3
from typing import Optional, List
from datetime import date


class DBManager:
    def __init__(self, db_path):
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self._execute('''CREATE TABLE IF NOT EXISTS mailusers
                        (username TEXT PRIMARY KEY,
                         date TEXT)''')
        self.db.execute(
                '''CREATE TABLE IF NOT EXISTS groups
                (id INTEGER PRIMARY KEY,
                topic TEXT)''')
        self.db.execute(
                '''CREATE TABLE IF NOT EXISTS usercountr
                (date TEXT PRIMARY KEY,
                users INTEGER)''')

    def _execute(self, statement, args=()):
        with self.db:
            return self.db.execute(statement, args)

    def store_mailusers(self, key, value):
        old_val = self.get_mailuser(key)
        if value is not None:
            self._execute('REPLACE INTO mailusers VALUES (?,?)', (key, value))
        else:
            self._execute('DELETE FROM mailusers WHERE username=?', (key, ))
        return old_val

    def list_usercount(self):
        users = []
        dates = []
        rows = self._execute('SELECT * FROM usercountr').fetchall()
        for row in rows:
            users.append(row['users'])
            dates.append(date.fromisoformat(row['date']))
        return dates, users

    def store_usercount(self, key, value):
        self._execute('REPLACE INTO usercountr VALUES (?,?)', (key, value))

    def get_mailuser(self, key):
        row = self._execute(
            'SELECT * FROM mailusers WHERE username=?',
            (key,),
        ).fetchone()
        return row['date'] if row else None

    def list_mailusers(self):
        rows = self._execute('SELECT * FROM mailusers').fetchall()
        return [(row['username'], row["date"]) for row in rows]

    def deltabot_shutdown(self, bot):
        self.db.close()

    def upsert_group(self, gid: int, topic: Optional[str]) -> None:
        with self.db:
            self.db.execute(
                'REPLACE INTO groups (id, topic) VALUES (?,?)',
                (gid, topic))

    def remove_group(self, gid: int) -> None:
        with self.db:
            self.db.execute('DELETE FROM groups WHERE id=?', (gid,))

    def get_group(self, gid: int) -> Optional[sqlite3.Row]:
        return self.db.execute(
            'SELECT * FROM groups WHERE id=?', (gid,)).fetchone()

    def get_groups(self) -> List[sqlite3.Row]:
        return self.db.execute('SELECT * FROM groups').fetchall()