import base64

one_way = b'\x08\x1c\x10\x02\x1a\x1e\x12\n2025-01-12j\x07\x08\x01\x12\x03LAXr\x07\x08\x01\x12\x03SFO@\x01H\x01p\x01\x82\x01\x0b\x08\xfc\x06`\x04\x08'

# Re-encode to base64
re_encoded_str = base64.b64encode(one_way).decode('utf-8')

# Insert underscores at the 6th position from the end
insert_index = len(re_encoded_str) - 6
modified_str = re_encoded_str[:insert_index] + '_' * 7 + re_encoded_str[insert_index:]

url = f'https://www.google.com/travel/flights/search?tfs={modified_str}'

print(url)
