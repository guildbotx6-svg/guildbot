import sys
sys.path.insert(0, r'c:\Users\AARON SEEMA\discord-bot')

try:
    with open(r'c:\Users\AARON SEEMA\discord-bot\commands\reconcile_bot.py', 'r', encoding='utf-8') as f:
        code = f.read()
    compile(code, 'reconcile_bot.py', 'exec')
    print("Compilation successful!")
except SyntaxError as e:
    print(f"SyntaxError at line {e.lineno}: {e.msg}")
    print(f"Text: {e.text}")
except Exception as e:
    print(f"Other error: {e}")