"""
Convert IAB taxonomy TSV file to a nested JSON structure.
"""
import csv
import json


def build_nested_taxonomy(tsv_file_path, output_json_path):
    """
    Read IAB taxonomy TSV and convert to nested JSON structure.

    Args:
        tsv_file_path: Path to the input TSV file
        output_json_path: Path to save the output JSON file
    """
    # Read the TSV file
    rows = []
    with open(tsv_file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            rows.append(row)

    # Create a mapping of ID to row data
    id_to_node = {}
    for row in rows:
        node_id = row['Unique ID']
        parent_id = row['Parent'].strip() if row['Parent'].strip() else None

        id_to_node[node_id] = {
            'id': node_id,
            'name': row['Name'],
            'parent_id': parent_id,
            'children': []
        }

    # Build the tree structure
    root_nodes = []
    for node_id, node in id_to_node.items():
        if node['parent_id'] is None:
            # This is a root node (Tier 1)
            root_nodes.append(node)
        else:
            # Add this node as a child of its parent
            parent = id_to_node.get(node['parent_id'])
            if parent:
                parent['children'].append(node)

    # Clean up the structure by removing parent_id references
    def clean_node(node):
        cleaned = {
            'id': node['id'],
            'name': node['name']
        }
        if node['children']:
            cleaned['children'] = [clean_node(child) for child in node['children']]
        return cleaned

    taxonomy = [clean_node(node) for node in root_nodes]

    # Write to JSON file
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(taxonomy, f, indent=2, ensure_ascii=False)

    print(f"✅ Successfully converted taxonomy to JSON")

    return taxonomy


if __name__ == '__main__':
    tsv_path = 'data/iab_taxonomy.tsv'
    json_path = 'data/iab_taxonomy.json'

    taxonomy = build_nested_taxonomy(tsv_path, json_path)
