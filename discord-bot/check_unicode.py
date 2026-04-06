with open('commands/reconcile_bot.py', 'r') as f:
    content = f.read()
non_ascii = [char for char in content if ord(char) > 127]
print('Non-ASCII characters found:', len(non_ascii))
if non_ascii:
    print('Characters:', set(non_ascii))