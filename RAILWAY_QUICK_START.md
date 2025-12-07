# 🚂 Railway - Быстрая инструкция

## ✅ Всего 3 простых шага!

---

### 1️⃣ Загрузите код на GitHub

**Если Git не установлен:** https://git-scm.com/download/win

**Создайте репозиторий на GitHub:**
- https://github.com → "New repository"
- Name: `discord-bot-dashboard`
- Создайте без README

**Загрузите код (PowerShell):**
```powershell
cd C:\Users\kompd\.gemini\antigravity\scratch\discord_bot
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/ВАШ-ЛОГИН/discord-bot-dashboard.git
git branch -M main
git push -u origin main
```

---

### 2️⃣ Разверните на Railway

1. **Зайдите:** https://railway.app
2. **Login with GitHub**
3. **New Project** → **Deploy from GitHub repo**
4. Выберите `discord-bot-dashboard`
5. Ждите 2-3 минуты - деплой автоматический!

---

### 3️⃣ Настройте

**Переменные окружения (Variables):**
- `CLIENT_ID`: `1211664015646916670`
- `CLIENT_SECRET`: `ykwvV-Jg6WaWey-bsejTTEPTsho2NiAd`
- `SECRET_KEY`: `super-secret-key-123`

**Получите URL:**
- Settings → Networking → Generate Domain
- Скопируйте: `https://ваш-проект.up.railway.app`

**Обновите REDIRECT_URI:**
- Variables → `REDIRECT_URI` → `https://ваш-домен.up.railway.app/callback`

**Discord OAuth:**
- https://discord.com/developers/applications
- Ваше приложение → OAuth2 → Redirects
- Добавьте: `https://ваш-домен.up.railway.app/callback`

---

## 🎉 Готово!

Сайт работает: `https://ваш-домен.up.railway.app`

**Фичи Railway:**
✅ $5 кредитов в месяц (бесплатно)
✅ ~500 часов работы
✅ Не засыпает!
✅ Автодеплой при git push

---

📖 **Подробная инструкция:** `RAILWAY_DEPLOY_GUIDE.md`
