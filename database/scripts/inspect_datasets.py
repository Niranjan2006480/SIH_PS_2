import os
import pandas as pd
import geopandas as gpd
import json
import traceback

def inspect_datasets(base_dir="datasets"):
    inventory = []
    
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            path = os.path.join(root, file)
            size = os.path.getsize(path)
            ext = os.path.splitext(file)[1].lower()
            
            # Skip shapefile sidecars to avoid duplicates, we'll read .shp which uses them
            if ext in ['.shx', '.dbf', '.prj'] and os.path.exists(os.path.splitext(path)[0] + '.shp'):
                continue
                
            info = {
                "filename": file,
                "path": path,
                "file_type": ext,
                "size_bytes": size,
                "num_rows": None,
                "num_columns": None,
                "column_names": [],
                "sample_records": [],
                "error": None
            }
            
            try:
                if ext == '.csv':
                    df = pd.read_csv(path, nrows=10)
                    df_full = pd.read_csv(path)
                    info["num_rows"] = len(df_full)
                    info["num_columns"] = len(df_full.columns)
                    info["column_names"] = list(df_full.columns)
                    info["sample_records"] = df.to_dict(orient='records')
                elif ext in ['.xls', '.xlsx']:
                    # some files may fail if they are old format, handle via xlrd/openpyxl
                    df = pd.read_excel(path, nrows=10)
                    df_full = pd.read_excel(path)
                    info["num_rows"] = len(df_full)
                    info["num_columns"] = len(df_full.columns)
                    info["column_names"] = list(df_full.columns)
                    info["sample_records"] = df.to_dict(orient='records')
                elif ext == '.shp':
                    df = gpd.read_file(path)
                    info["num_rows"] = len(df)
                    info["num_columns"] = len(df.columns)
                    info["column_names"] = list(df.columns)
                    info["sample_records"] = df.head(5).drop(columns=['geometry']).to_dict(orient='records')
                    info["crs"] = str(df.crs)
                elif ext == '.dbf':
                    # standalone dbf
                    df = gpd.read_file(path)
                    info["num_rows"] = len(df)
                    info["num_columns"] = len(df.columns)
                    info["column_names"] = list(df.columns)
                    info["sample_records"] = df.head(5).drop(columns=['geometry'], errors='ignore').to_dict(orient='records')
            except Exception as e:
                info["error"] = str(e)
            
            inventory.append(info)
            print(f"Processed: {file}")

    with open("dataset_inventory.json", "w", encoding="utf-8") as f:
        json.dump(inventory, f, indent=4, default=str)
    print("Done! Inventory saved to dataset_inventory.json")
    
if __name__ == "__main__":
    inspect_datasets()
