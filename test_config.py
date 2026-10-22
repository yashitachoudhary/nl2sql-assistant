from app.models.db_config import DBConfig

# 1. Valid MySQL config: port should auto-fill to 3306
cfg = DBConfig(db_type="mysql", db_host="localhost",
               db_user="root", db_password="secret", db_name="mydb")
print(cfg.db_port)   # expect 3306
print(cfg)           # password should appear hidden

# 2. Valid SQLite config: no host needed
cfg2 = DBConfig(db_type="sqlite", db_name="demo/demo_database.db")
print(cfg2.db_type)

# 3. Invalid db_type: should raise an error
try:
    DBConfig(db_type="oracle", db_name="x")
except Exception as e:
    print("Rejected oracle:", type(e).__name__)

# 4. MySQL with no host: should raise an error
try:
    DBConfig(db_type="mysql", db_name="x")
except Exception as e:
    print("Rejected missing host:", type(e).__name__)