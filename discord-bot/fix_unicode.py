import re

with open('commands/reconcile_bot.py', 'r') as f:
    content = f.read()

# Remove emoji and unicode symbols
content = re.sub(r'[^\x00-\x7F]+', '', content)

with open('commands/reconcile_bot.py', 'w') as f:
    f.write(content)

print('Removed all unicode characters')