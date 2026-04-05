import os

path = 'web.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
in_bad_block = False
for i, line in enumerate(lines):
    if line.strip() == 'if not text:':
        # Start of bad block
        in_bad_block = True
        new_lines.append(line)
        new_lines.append("        return jsonify({'success': False, 'error': 'Пустой текст'})\\n\\n")
        new_lines.append("    try:\\n")
        new_lines.append("        prompt = f\"\"\"Ты - строгий редактор объявлений СМИ(PRO) на сервере Arizona RP. Отредактируй это: \\\"{text}\\\"\\n")
        new_lines.append("По правилам:\\n")
        new_lines.append("1. Замени сленг (гетто -> опасный район, велик -> в/т Горник).\\n")
        new_lines.append("2. Добавь префиксы (а/м - авто, м/ц - мото).\\n")
        new_lines.append("3. Если цена не указана - пиши \\\"Цена: Договорная\\\".\\n")
        new_lines.append("4. Если бюджет не указан - пиши \\\"Бюджет: Свободный\\\".\\n")
        new_lines.append("5. Формат: [Тип] Текст объявления. Цена/Бюджет: ...\\n")
        new_lines.append("6. Не добавляй \\\"Контакт: ...\\\" в конце, это делает игра сама.\\n\\n")
        new_lines.append("Примеры:\\n")
        new_lines.append("- \\\"продам нрг 500\\\" -> \\\"Продам м/ц NRG-500. Цена: Договорная\\\"\\n")
        new_lines.append("- \\\"куплю дом лс 50кк\\\" -> \\\"Куплю дом в г. Лос-Сантос. Бюджет: 50 млн$\\\"\\n")
        new_lines.append("- \\\"набор в фаму\\\" -> \\\"Идет набор в семью. Просьба связаться.\\\"\\n")
        new_lines.append("- \\\"продам акс попугай\\\" -> \\\"Продам а/с Попугай на плечо. Цена: Договорная\\\"\\n\\n")
        new_lines.append("Верни ТОЛЬКО отредактированный текст.\\\"\"\"\\n")
        continue

    if in_bad_block:
        if 'response = AI_MODEL.generate_content(prompt)' in line:
            in_bad_block = False
            new_lines.append(line)
        continue
    new_lines.append(line)

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Fixed web.py encoding syntax error successfully!")
