import json
import os

def generate_md():
    with open("dataset_inventory.json", "r", encoding="utf-8") as f:
        data = json.load(f)
        
    md = "# Dataset Inventory\n\n"
    
    for item in data:
        md += f"## {item['filename']}\n"
        md += f"- **Path:** `{item['path']}`\n"
        md += f"- **Type:** {item['file_type']}\n"
        md += f"- **Size:** {item['size_bytes']} bytes\n"
        if item.get("error"):
            md += f"- **Error during parsing:** {item['error']}\n"
        else:
            if item['num_rows'] is not None:
                md += f"- **Rows:** {item['num_rows']}\n"
                md += f"- **Columns:** {item['num_columns']}\n"
                md += f"- **Column Names:** {', '.join([str(c) for c in item['column_names']])}\n"
                md += f"- **Sample Record:**\n```json\n{json.dumps(item['sample_records'][0] if item['sample_records'] else {}, indent=2, default=str)}\n```\n"
        
        md += "\n---\n\n"
        
    with open("Dataset_Inventory.md", "w", encoding="utf-8") as f:
        f.write(md)

if __name__ == "__main__":
    generate_md()
