import click

from mailadm.cmdline import get_mailadm_db
from mailadm.conn import UserInfo


@click.pass_context
def migrate(ctx):
    db = get_mailadm_db(ctx)
    with db.write_transaction() as conn:
        conn.execute("PRAGMA foreign_keys=on;")

        q = "SELECT addr, date, ttl, token_name from users"
        users = [UserInfo(*args) for args in conn.execute(q).fetchall()]
        q = "DROP TABLE users"
        conn.execute(q)

        conn.execute("""
                    CREATE TABLE users (
                        addr TEXT PRIMARY KEY,
                        date INTEGER,
                        ttl INTEGER,
                        token_name TEXT NOT NULL,
                        FOREIGN KEY (token_name) REFERENCES tokens (name)
                    )
                """)
        for u in users:
            q = """INSERT INTO users (addr, date, ttl, token_name)
                           VALUES (?, ?, ?, ?)"""
            conn.execute(q, (u.addr, u.date, u.ttl, u.token_name))

        q = "DELETE FROM config WHERE name=?"
        conn.execute(q, ("vmail_user",))
        conn.execute(q, ("path_virtual_mailboxes",))


if __name__ == "__main__":
    migrate()
