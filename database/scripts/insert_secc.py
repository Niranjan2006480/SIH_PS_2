import os
import pandas as pd
from sqlalchemy import create_engine, text

def process_secc(engine):
    print("Processing SECC Data...")
    file_path = 'datasets/[States wise] Socio Economic and Caste Census (SECC).xlsx'
    
    # Read the data, skip first two rows to get to the data
    df = pd.read_excel(file_path, engine='calamine', skiprows=2)
    
    state_col = df.columns[0]
    total_hh_col = df.columns[1]
    
    # Filter rows that look like states
    df_states = df[df[state_col].str.contains(r'\(\d+\)', na=False)]
    
    with engine.begin() as conn:
        for _, row in df_states.iterrows():
            state_raw = str(row[state_col])
            total_hh = int(row[total_hh_col]) if pd.notnull(row[total_hh_col]) else 0
            
            # Extract state code
            import re
            match = re.search(r'\((\d+)\)', state_raw)
            if match:
                state_code = str(int(match.group(1))) # Normalize "01" to "1" or "01"? In my LGD it was "27". In SECC it is "(27)"
                
                # Check if state exists before inserting (to avoid FK errors)
                res = conn.execute(text("SELECT state_code FROM states WHERE state_code = :sc OR state_code = :sc2"), 
                                   {"sc": state_code, "sc2": match.group(1)}).fetchone()
                if res:
                    sc = res[0]
                    sql = text("""
                        INSERT INTO state_economic_profile (state_code, geographic_level, total_households)
                        VALUES (:sc, 'State', :th)
                    """)
                    conn.execute(sql, {"sc": sc, "th": total_hh})
                
    print(f"Inserted SECC state economic profiles.")

if __name__ == "__main__":
    engine = create_engine(os.environ.get('DATABASE_URL'))
    process_secc(engine)
