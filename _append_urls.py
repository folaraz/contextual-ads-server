import re, json

# Read existing urls
with open('data/urls.txt') as f:
    existing_list = json.loads(f.read())

existing_set = set(existing_list)

# Extract all URLs from page_urls.go
with open('tests/fixtures/page_urls.go') as f:
    go_content = f.read()

urls_from_go = re.findall(r'"(https?://[^"]+)"', go_content)

# Deduplicate while preserving order
new_urls = []
seen = set(existing_set)
for u in urls_from_go:
    if u not in seen:
        new_urls.append(u)
        seen.add(u)

print(f'Existing URLs: {len(existing_list)}')
print(f'URLs found in page_urls.go: {len(urls_from_go)}')
print(f'New unique URLs to add: {len(new_urls)}')

combined = existing_list + new_urls
with open('data/urls.txt', 'w') as f:
    f.write('[\n')
    for i, url in enumerate(combined):
        comma = ',' if i < len(combined) - 1 else ''
        f.write(f'  "{url}"{comma}\n')
    f.write(']\n')

print(f'Total URLs in updated file: {len(combined)}')

