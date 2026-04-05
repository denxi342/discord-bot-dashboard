import os

file_path = "static/js/dashboard.js"
with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
    text = f.read()

# Try to find all cyrillic mojibake and decode them
def fix_mojibake(s):
    try:
        # Encode back to cp1251 (which is how the raw utf-8 bytes were interpreted)
        raw_bytes = s.encode('cp1251')
        # Decode correctly as utf-8
        return raw_bytes.decode('utf-8')
    except:
        return s

fixed_text = ""
lines = text.split("\n")
changed = 0
for i, line in enumerate(lines):
    new_line = line
    # Simple heuristic: find sequences of "Р" + something
    if "Р" in line:
        # We will extract words containing Р and try to fix them
        words = line.split()
        for word in words:
            if "Р" in word:
                # Find substring of mojibake
                import re
                mojibakes = re.findall(r'[А-Яа-яЁё]+', line)
                for mb in mojibakes:
                    if 'Р' in mb:
                        fixed = fix_mojibake(mb)
                        if fixed != mb and '"' not in fixed and "'" not in fixed:
                            new_line = new_line.replace(mb, fixed)
                            
    if "вњ…" in new_line or "вќЊ" in new_line or "рџЋ®" in new_line:
        # Check specific emojis double encoded
        new_line = fix_mojibake(new_line)
        
    if "Р" in new_line:
         # Brute force fix the whole line if it still has "Р" (often the start of mojibake)
         try:
             fixed_line = new_line.encode('cp1251').decode('utf-8')
             new_line = fixed_line
         except:
             pass

    if new_line != line:
        changed += 1
    
    fixed_text += new_line + "\n"

# Extra safe manual replacements for the main ones seen in screenshot just in case
replacements = {
    "Р”СЂСѓР·СЊСЏ": "Друзья",
    "Р’ СЃРµС‚Рё": "В сети",
    "Р’СЃРµ": "Все",
    "РћР¶РёРґР°РЅРёРµ": "Ожидание",
    "Р”РѕР±Р°РІРёС‚СЊ РІ РґСЂСѓР·СЊСЏ": "Добавить в друзья",
    "Р”РћР‘РђР’Р˜РўР¬ Р’ Р”Р РЈР—Р¬РЇ": "ДОБАВИТЬ В ДРУЗЬЯ",
    "Р’С‹ РјРѕР¶РµС‚Рµ РґРѕР±Р°РІРёС‚СЊ РґСЂСѓР·РµР№ РїРѕ РёРјРµРЅРё РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ": "Вы можете добавить друзей по имени пользователя",
    "Р’РІРµРґРёС‚Рµ РёРјСЏ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ": "Введите имя пользователя",
    "РћС‚РїСЂР°РІРёС‚СЊ Р·Р°РїСЂРѕСЃ": "Отправить запрос",
    "Р—Р°РіСЂСѓР·РєР°...": "Загрузка...",
    "Р—РґРµСЃСЊ РїРѕРєР° РЅРёРєРѕРіРѕ РЅРµС‚": "Здесь пока никого нет",
    "РџСЂРёРЅСЏС‚СЊ": "Принять",
    "Р˜СЃС…РѕРґСЏС‰РёР№ Р·Р°РїСЂРѕСЃ": "Исходящий запрос",
    "РЎРѕРѕР±С‰РµРЅРёРµ": "Сообщение",
    "РЈРґР°Р»РёС‚СЊ": "Удалить",
    "РџРѕРёСЃРє": "Поиск",
    "РќРµ РІ СЃРµС‚Рё": "Не в сети",
    "Р’СЃРµ РґСЂСѓР·СЊСЏ": "Все друзья",
    "РћР¶РёРґР°СЋС‰РёРµ": "Ожидающие",
    "Р—Р°РїСЂРѕСЃ РІ РґСЂСѓР·СЊСЏ": "Запрос в друзья",
    "РќР• Р’ РЎР•РўР˜": "НЕ В СЕТИ",
    "Р РµРґР°РєС‚РёСЂРѕРІР°С‚СЊ": "Редактировать",
    "РїСЂРѕС„РёР»СЊ": "профиль",
    "Р”РѕР±Р°РІСЊС‚Рµ СЌРјРѕРґР·Рё": "Добавьте эмодзи",
    "РІ РЅР°С‡Р°Р»Рµ РґР»СЏ РєСЂР°СЃРѕС‚С‹": "в начале для красоты",
    "РћС‚РјРµРЅР°": "Отмена",
    "РЎРѕС…СЂР°РЅРёС‚СЊ": "Сохранить",
    "вњ…": "✅",
    "вќЊ": "❌",
    "рџЋ®": "🎮",
    "РђРІР°С‚Р°СЂ РѕР±РЅРѕРІР»С‘РЅ!": "Аватар обновлён!",
    "РћС€РёР±РєР°": "Ошибка",
    "Р·Р°РіСЂСѓР·РєРё": "загрузки",
    "Р’ РЎР•РўР˜": "В СЕТИ",
    "РџСЂРѕС„РёР»СЊ РѕР±РЅРѕРІР»С‘РЅ!": "Профиль обновлён!",
    "РЎРµСЂРІРµСЂ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ": "Сервер пользователя",
    "РќРђР—Р’РђРќР˜Р• РЎР•Р Р’Р•Р Рђ": "НАЗВАНИЕ СЕРВЕРА",
    "РЎРѕР·РґР°С‚СЊ": "Создать",
    "РќР°Р·Р°Рґ": "Назад",
    "РџРµСЂСЃРѕРЅР°Р»РёР·Р°С†РёСЏ СЃРµСЂРІРµСЂР°": "Персонализация сервера",
    "Р”Р°Р№С‚Рµ РЅРѕРІРѕРјСѓ СЃРµСЂРІРµСЂСѓ РёРјСЏ": "Дайте новому серверу имя",
    "Уже есть приглашение?": "Уже есть приглашение?",
    "Рё Р·РЅР°С‡РѕРє. РС… РјРѕР¶РЅРѕ Р±СѓРґРµС‚ РёР·РјРµРЅРёС‚СЊ РІ Р»СЋР±РѕРµ РІСЂРµРјСЏ.": "и значок. Их можно будет изменить в любое время."
}

for k, v in replacements.items():
    fixed_text = fixed_text.replace(k, v)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(fixed_text)

print(f"Fixed encoding in {changed} lines in {file_path}.")
