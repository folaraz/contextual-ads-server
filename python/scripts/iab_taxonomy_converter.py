import json

import pandas as pd


def build_nested_taxonomy_json(path=None):
    df = read_taxonomy_json(path=path)
    df = df.rename(columns={'Unique ID': 'id_str', 'Parent ID': 'parent_id_str'})

    valid_id_mask = df['id_str'].notna() & (df['id_str'] != '')
    df = df[valid_id_mask].copy()

    name_mapping = pd.Series(df['Name'].values, index=df['id_str']).to_dict()

    df.loc[df['parent_id_str'].isna(), 'parent_id_str'] = None

    graph = {id_str: [] for id_str in df['id_str']}
    all_children = set()

    for row in df.itertuples(index=False):
        id_str = row.id_str
        parent_id_str = row.parent_id_str

        if pd.notna(parent_id_str) and parent_id_str != id_str:
            if parent_id_str in graph:
                graph[parent_id_str].append(id_str)
            else:
                graph[parent_id_str] = [id_str]
            all_children.add(id_str)

    all_nodes = set(graph.keys())
    root_nodes = all_nodes - all_children

    def dfs(node_id, tier):
        new_node = {
            "id": node_id,
            "name": name_mapping.get(node_id, "Unknown"),
            "tier": tier
        }

        children_ids = graph[node_id]

        if children_ids:
            child_list = []
            for child_id in children_ids:
                child_node = dfs(child_id, tier + 1)
                child_list.append(child_node)

            new_node["children"] = child_list

        return new_node

    taxonomy_tree = []
    for root in root_nodes:
        taxonomy_tree.append(dfs(root, 1))

    return taxonomy_tree


def read_taxonomy_json(path):
    return pd.read_csv(
        path,
        sep='\t',
        dtype={
            'Unique ID': 'string',
            'Parent ID': 'string',
            'Unique ID 2': 'string',
            'Name': 'string',
        },
        engine='python',
        on_bad_lines='warn',
        encoding='utf-8',
        quoting=3
    )


def generate_taxonomy_mapping(path=None, index_col='Unique ID'):
    df = read_taxonomy_json(path=path)

    uniqueIdValues = df['Unique ID'].tolist()
    uniqueId2Values = df['Unique ID 2'].tolist()

    mapping = dict()

    zipped_values = zip(uniqueIdValues, uniqueId2Values) if index_col == 'Unique ID' else zip(uniqueId2Values,
                                                                                              uniqueIdValues)
    for k, v in zipped_values:
        if pd.notna(k) and k != '' and pd.notna(v) and v != '':
            mapping[k] = v
    return mapping


def write_taxonomy_json(taxonomy, path):
    with open(path, 'w') as f:
        json.dump(taxonomy, f, indent=4)


def main():
    content_taxonomy = build_nested_taxonomy_json(path='../data/raw/iab_content_taxonomy.tsv')
    product_taxonomy = build_nested_taxonomy_json(path='../data/raw/iab_ad_product_taxonomy.tsv')
    ad_product_to_content_mapping = generate_taxonomy_mapping(
        path='../data/raw/ad_product_to_content_taxonomy_mapping.tsv')
    content_to_ad_product_mapping = generate_taxonomy_mapping(
        path='../data/raw/content_to_ad_product_taxonomy_mapping.tsv')

    write_taxonomy_json(content_taxonomy, '../data/iab_content_taxonomy.json')
    write_taxonomy_json(product_taxonomy, '../data/iab_product_taxonomy.json')
    write_taxonomy_json(ad_product_to_content_mapping, '../data/ad_product_to_content_taxonomy_mapping.json')
    write_taxonomy_json(content_to_ad_product_mapping, '../data/content_to_ad_product_taxonomy_mapping.json')


if __name__ == '__main__':
    main()
