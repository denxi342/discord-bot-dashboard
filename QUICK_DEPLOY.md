# 🚀 Быстрая инструкция по деплою

## ✅ Все готово! Осталось 4 шага:

### 1️⃣ Установите Git
https://git-scm.com/download/win

### 2️⃣ Создайте GitHub репозиторий
- Зайдите на https://github.com
- Нажмите "New repository"
- Имя: `discord-bot-dashboard`
- Создайте без README и .gitignore

### 3️⃣ Загрузите код (в PowerShell):
```powershell
cd C:\Users\kompd\.gemini\antigravity\scratch\discord_bot
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/ВАШ-ЛОГИН/discord-bot-dashboard.git
git branch -M main
git push -u origin main
```

### 4️⃣ Деплой на Render:
1. Зайдите на https://render.com
2. "New +" → "Web Service"
3. Подключите GitHub репозиторий
4. Настройки:
   - Build: `pip install -r requirements.txt`
   - Start: `python web.py`
5. Переменные окружения:
   - `CLIENT_ID`: `1211664015646916670`
   - `CLIENT_SECRET`: `ykwvV-Jg6WaWey-bsejTTEPTsho2NiAd`
   - `SECRET_KEY`: `super-secret-key-123`
   - `REDIRECT_URI`: `https://ваш-сайт.onrender.com/callback` ⬅️ скопируете после деплоя
6. "Create Web Service"

### 5️⃣ Обновите Discord OAuth:
1. https://discord.com/developers/applications
2. Ваше приложение → OAuth2 → Redirects
3. Добавьте: `https://ваш-сайт.onrender.com/callback`
4. Сохраните

## 🎉 Готово!

Ваш сайт работает 24/7 по адресу: `https://ваш-сайт.onrender.com`

📖 Подробная инструкция: см. файл `RENDER_DEPLOY_GUIDE.md`
