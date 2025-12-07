# Команды для загрузки кода на GitHub
# Выполняйте по порядку в PowerShell

# 1. Перейдите в папку проекта
cd C:\Users\kompd\.gemini\antigravity\scratch\discord_bot

# 2. Инициализируйте Git
git init

# 3. Добавьте все файлы
git add .

# 4. Сделайте первый коммит
git commit -m "Initial commit: Bot Dashboard Pro"

# 5. Подключите GitHub репозиторий
# ВАЖНО! Замените ВАШ-GITHUB-ЛОГИН на ваш реальный логин
git remote add origin https://github.com/ВАШ-GITHUB-ЛОГИН/discord-bot-dashboard.git

# 6. Переименуйте ветку в main
git branch -M main

# 7. Загрузите код
git push -u origin main

# При первой загрузке Git попросит ввести логин и пароль от GitHub
# Если просит пароль - используйте Personal Access Token (не обычный пароль!)
# Token создается тут: https://github.com/settings/tokens
