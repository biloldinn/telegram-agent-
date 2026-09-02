with open('main.py', 'r', encoding='utf-8') as f:
    text = f.read()

fixes = {
    'СЂСџвЂ˜вЂ№': '👋',
    'СЂСџвЂ˜вЂЎ': '👇',
    'СЂСџвЂ˜В¤': '👤',
    'СЂСџвЂ˜вЂ°': '👉',
    'СЂСџвЂ˜Тђ': '👥',
    'СЂСџвЂ˜вЂ˜': '👑',
    'СЂСџвЂњРЉ': '📋',
    'СЂСџвЂ˜РЃРІР‚РЊСЂСџвЂ™В»': '📞'
}

for bad, good in fixes.items():
    text = text.replace(bad, good)

import re
text = re.sub(r'СЂСџ[^\s<A-Za-z0-9_]*', '🔹', text)
text = text.replace('?\"T', '🔙')
text = text.replace('?\'?', '🔖')

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(text)
