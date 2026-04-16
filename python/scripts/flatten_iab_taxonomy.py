
import json
import os
from typing import List, Dict, Any, Optional


def flatten_taxonomy(
        nodes: List[Dict[str, Any]],
        parent_id: Optional[str] = None
) -> List[Dict[str, str | int | None]]:
    result = []

    for node in nodes:
        flat_node = {
            "id": node["id"],
            "parent_id": parent_id,
            "name": node["name"],
            "tier": node["tier"]
        }
        result.append(flat_node)

        if "children" in node and node["children"]:
            result.extend(flatten_taxonomy(node["children"], parent_id=node["id"]))

    return result


def convert_taxonomy(input_file: str, output_file: str, name: str) -> int:
    with open(input_file, "r") as f:
        nested_taxonomy = json.load(f)

    flat_taxonomy = flatten_taxonomy(nested_taxonomy)
    flat_taxonomy.sort(key=lambda x: (x["tier"], int(x["id"])))

    with open(output_file, "w") as f:
        json.dump(flat_taxonomy, f, indent=2)

    print(f"[{name}] Converted {len(flat_taxonomy)} entries -> {output_file}")
    return len(flat_taxonomy)


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.join(script_dir, "..", "..")

    input_data_dir = os.path.join(script_dir, "..", "data")
    output_data_dir = os.path.join(project_root, "data")

    # Ensure output directory exists
    os.makedirs(output_data_dir, exist_ok=True)

    # Define taxonomies to convert
    taxonomies = [
        ("iab_content_taxonomy.json", "iab_content_taxonomy_flat.json", "Content Taxonomy"),
        ("iab_product_taxonomy.json", "iab_product_taxonomy_flat.json", "Product Taxonomy"),
    ]

    total = 0
    for input_name, output_name, display_name in taxonomies:
        input_file = os.path.join(input_data_dir, input_name)
        output_file = os.path.join(output_data_dir, output_name)

        if os.path.exists(input_file):
            total += convert_taxonomy(input_file, output_file, display_name)
        else:
            print(f"[{display_name}] Input file not found: {input_file}")

    print(f"\nTotal: {total} taxonomy entries converted")


if __name__ == "__main__":
    main()
