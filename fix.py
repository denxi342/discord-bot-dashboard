import os

file_path = "static/js/dashboard.js"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# exact replacements for the remaining errors
content = content.replace("Р’ СЃРµС‚и", "В сети")
content = content.replace("Р”РћР‘РђР’Р˜РўР¬ Р’ Р”Р РЈР—Р¬РЇ", "ДОБАВИТЬ В ДРУЗЬЯ")
content = content.replace("Р’С‹ РјРѕР¶РµС‚Рµ РґРѕР±Р°РІиС‚СЊ РґСЂСѓР·РµР№ РїРѕ иРјРµРЅи РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ.", "Вы можете добавить друзей по имени пользователя.")

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Fixed remaining strings!")
