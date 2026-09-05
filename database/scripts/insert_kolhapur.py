from sqlalchemy import create_engine, text
import os

engine = create_engine(os.environ.get('DATABASE_URL'))
with engine.connect() as conn:
    conn.execute(text("INSERT INTO states (state_code, state_name, state_name_normalized) VALUES ('27', 'Maharashtra', 'maharashtra') ON CONFLICT DO NOTHING"))
    conn.execute(text("INSERT INTO districts (district_lgd_code, state_code, district_name, district_name_normalized) VALUES ('2734', '27', 'Kolhapur', 'kolhapur') ON CONFLICT DO NOTHING"))
    conn.commit()
print('District Kolhapur inserted!')
