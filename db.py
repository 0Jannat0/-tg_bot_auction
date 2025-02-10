import asyncpg
import datetime

class Database:
    def __init__(self, user, password, host, database):
        self.user = user
        self.password = password
        self.host = host
        self.database = database
        self.pool = None

    async def connect(self):
        try:
            self.pool = await asyncpg.create_pool(
                host=self.host,
                database=self.database,
                user=self.user,
                password=self.password,
                min_size=5,
                max_size=10
            )
            print(f"Connected to {self.database}")

            async with self.pool.acquire() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id SERIAL PRIMARY KEY,
                        telegram_id BIGINT UNIQUE NOT NULL,
                        username TEXT,
                        first_name TEXT,
                        last_name TEXT
                    )
                """)
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS auctions (
                        id SERIAL PRIMARY KEY,
                        admin_id BIGINT NOT NULL,
                        title TEXT NOT NULL,
                        description TEXT,
                        starting_bid INTEGER NOT NULL,
                        bid_step INTEGER NOT NULL,
                        current_bid INTEGER,
                        highest_bidder BIGINT,
                        end_time TIMESTAMP
                    )
                """)
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS bids (
                        id SERIAL PRIMARY KEY,
                        auction_id INTEGER REFERENCES auctions(id) ON DELETE CASCADE,
                        user_id BIGINT NOT NULL,
                        bid_amount INTEGER NOT NULL,
                        timestamp TIMESTAMP DEFAULT NOW()
                    )
                """)
        except Exception as e:
            print(f"Error connecting to database: {e}")
            exit()

    async def disconnect(self):
        if self.pool:
            await self.pool.close()
            print(f"Disconnected from {self.database}")

    async def add_user(self, tg_id, username, first_name, last_name):
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                        INSERT INTO users (telegram_id, username, first_name, last_name)
                        VALUES ($1, $2, $3, $4)
                        ON CONFLICT (telegram_id) DO NOTHING
                    """,
                    tg_id, username, first_name, last_name
                )
        except Exception as e:
            print(f"Error adding user: {e}")

    async def check_user(self, tg_id):
        try:
            async with self.pool.acquire() as conn:
                user = await conn.fetchrow(
                    """
                        SELECT id, username, first_name, last_name FROM users WHERE telegram_id = $1
                    """,
                    tg_id
                )
                return user
        except Exception as e:
            print(f"Error checking user: {e}")
            return None

    async def create_auction(self, admin_id, title, description, starting_bid, bid_step, end_time_minutes):
        end_time = datetime.datetime.now() + datetime.timedelta(minutes=end_time_minutes)
        try:
            async with self.pool.acquire() as conn:
                auction_id = await conn.fetchval(
                    """
                        INSERT INTO auctions (admin_id, title, description, starting_bid, bid_step, current_bid, highest_bidder, end_time)
                        VALUES ($1, $2, $3, $4, $5, $4, NULL, $6) RETURNING id
                    """,
                    admin_id, title, description, starting_bid, bid_step, end_time
                )
                return auction_id
        except Exception as e:
            print(f"Error creating auction: {e}")
            return None

    async def get_auction(self, auction_id):
        try:
            async with self.pool.acquire() as conn:
                return await conn.fetchrow("SELECT * FROM auctions WHERE id = $1", auction_id)
        except Exception as e:
            print(f"Error getting auction: {e}")
            return None

    async def place_bid(self, auction_id, user_id, bid_amount):
        try:
            async with self.pool.acquire() as conn:
                auction = await conn.fetchrow("SELECT current_bid, bid_step, end_time FROM auctions WHERE id = $1", auction_id)
                if not auction or bid_amount <= auction['current_bid']:
                    return False

                new_end_time = datetime.datetime.now() + datetime.timedelta(minutes=5)
                await conn.execute(
                    "UPDATE auctions SET current_bid = $1, highest_bidder = $2, end_time = $4 WHERE id = $3",
                    bid_amount, user_id, auction_id, new_end_time
                )
                await conn.execute(
                    "INSERT INTO bids (auction_id, user_id, bid_amount) VALUES ($1, $2, $3)",
                    auction_id, user_id, bid_amount
                )
                return True
        except Exception as e:
            print(f"Error placing bid: {e}")
            return False

    async def get_highest_bidder(self, auction_id):
        try:
            async with self.pool.acquire() as conn:
                return await conn.fetchrow("SELECT users.telegram_id as user_id, bids.bid_amount, users.username, users.first_name, users.last_name FROM bids INNER JOIN users ON bids.user_id = users.telegram_id WHERE bids.auction_id = $1 ORDER BY bids.bid_amount DESC LIMIT 1", auction_id)
        except Exception as e:
            print(f"Error getting highest bidder: {e}")
            return None

    async def get_expired_auctions(self):
        now = datetime.datetime.now()
        try:
            async with self.pool.acquire() as conn:
                return await conn.fetch("SELECT * FROM auctions WHERE end_time <= $1", now)
        except Exception as e:
            print(f"Error getting expired auctions: {e}")
            return None

    async def close_auction(self, auction_id):
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("DELETE FROM auctions WHERE id = $1", auction_id)
        except Exception as e:
            print(f"Error closing auction: {e}")

    async def get_latest_auction_id(self):
        try:
            async with self.pool.acquire() as conn:
                return await conn.fetchval("SELECT id FROM auctions ORDER BY id DESC LIMIT 1")
        except Exception as e:
            print(f"Error getting latest auction ID: {e}")
            return None