# СРОЧНОЕ РЕШЕНИЕ: Кнопки не работают из-за Edge Tracking Prevention

## Проблема
Edge блокирует ВСЕ внешние ресурсы (CSS, JS, шрифты) из-за настроек приватности.
Даже твой собственный сайт на Render блокируется.

## Решение 1: Используй Chrome/Firefox (БЫСТРО)
1. Открой Chrome или Firefox
2. Зайди на https://discord-bot-dashboard-5l70.onrender.com/dashboard
3. Кнопки будут работать

## Решение 2: Отключи Tracking Prevention в Edge
1. Открой Edge Settings (три точки → Settings)
2. Privacy, search, and services
3. Tracking prevention → выбери "Balanced" или "Basic"
4. Перезагрузи страницу (Ctrl+Shift+R)

## Решение 3: Добавь сайт в исключения
1. В Edge, на странице сайта, кликни на иконку замка слева от URL
2. Tracking prevention for this site → Off
3. Перезагрузи страницу

## Почему это происходит?
Edge считает, что твой сайт на Render использует трекеры, и блокирует:
- Font Awesome (иконки)
- Google Fonts (шрифты)
- Твой собственный CSS/JS

Это НЕ проблема кода — это настройки браузера.

## Проверка
Если откроешь в Chrome/Firefox — всё будет работать сразу.
