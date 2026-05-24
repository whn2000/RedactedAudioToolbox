import ast

def check(name):
    try:
        with open(name, 'r', encoding='utf-8') as f:
            ast.parse(f.read())
        print(f"{name} syntax OK")
    except Exception as e:
        print(f"{name} syntax error: {e}")

check('main.py')
check('elitetmhelper2.py')
check('flac_downsampler.py')
check('lossless_checker.py')
