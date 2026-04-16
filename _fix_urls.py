import re, json

with open('data/urls.txt') as f:
    content = f.read()

# Split at the closing bracket of the JSON array
bracket_idx = content.index('\n]\n')
json_part = content[:bracket_idx + 2]  # includes the ]
rest_part = content[bracket_idx + 2:]  # everything after ]

# Parse existing array
existing_list = json.loads(json_part)
existing_set = set(existing_list)

# Extract URLs from the rest (numbered list format)
new_urls_raw = re.findall(r'https?://[^\s,\]"]+', rest_part)

# Deduplicate while preserving order
new_urls = []
for u in new_urls_raw:
    if u not in existing_set:
        new_urls.append(u)
        existing_set.add(u)

print(f'Existing URLs in array: {len(existing_list)}')
print(f'URLs found outside array: {len(new_urls_raw)}')
print(f'New unique URLs to add: {len(new_urls)}')

# Write combined result
combined = existing_list + new_urls
with open('data/urls.txt', 'w') as f:
    f.write('[\n')
    for i, url in enumerate(combined):
        comma = ',' if i < len(combined) - 1 else ''
        f.write(f'  "{url}"{comma}\n')
    f.write(']\n')

print(f'Total URLs in updated file: {len(combined)}')

