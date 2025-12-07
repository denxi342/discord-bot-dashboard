import discord
from discord.utils import utcnow
from datetime import datetime

# Premium Modern Palette
COLOR_BLURPLE = discord.Color.from_rgb(88, 101, 242)   # Офиц. Blurple
COLOR_GREEN = discord.Color.from_rgb(87, 242, 135)     # Офиц. Green
COLOR_RED = discord.Color.from_rgb(237, 66, 69)        # Офиц. Red
COLOR_YELLOW = discord.Color.from_rgb(254, 231, 92)    # Офиц. Yellow
COLOR_DARK = discord.Color.from_rgb(43, 45, 49)        # Темный (для фона)

def create_base_embed(title: str = None, description: str = None, color: discord.Color = COLOR_BLURPLE, ctx = None):
    """
    Создает стильный, чистый Embed.
    """
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=utcnow()
    )
    
    if ctx and ctx.author:
        embed.set_footer(text=f"Requested by {ctx.author.name}", icon_url=ctx.author.display_avatar.url)
    
    return embed

def success(text: str, ctx=None):
    return create_base_embed(title="✅ Success", description=text, color=COLOR_GREEN, ctx=ctx)

def error(text: str, ctx=None):
    return create_base_embed(title="⛔ Error", description=text, color=COLOR_RED, ctx=ctx)

def warning(text: str, ctx=None):
    return create_base_embed(title="⚠️ Warning", description=text, color=COLOR_YELLOW, ctx=ctx)

def info(title: str, text: str, ctx=None):
    return create_base_embed(title=title, description=text, color=COLOR_BLURPLE, ctx=ctx)

def smart_help(ctx, commands_list):
    """
    Генерирует красивое меню помощи.
    """
    embed = discord.Embed(
        title="🤖 Панель управления",
        description="Список доступных команд и их описание.",
        color=COLOR_BLURPLE
    )
    embed.set_thumbnail(url=ctx.bot.user.display_avatar.url)
    
    for cmd in commands_list:
        if cmd.hidden:
            continue
            
        # Формируем красивую строку синтаксиса
        signature = f" {cmd.signature}" if cmd.signature else ""
        cmd_name = f"`!{cmd.name}{signature}`"
        
        # Описание
        desc = cmd.help if cmd.help else "Нет описания."
        
        embed.add_field(name=cmd_name, value=desc, inline=False)
        
    embed.set_footer(text="Используйте команды с умом!", icon_url=ctx.author.display_avatar.url)
    return embed

class PaginationView(discord.ui.View):
    def __init__(self, ctx, data, title="Список", items_per_page=5):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.data = data
        self.title = title
        self.items_per_page = items_per_page
        self.current_page = 0
        self.total_pages = (len(data) - 1) // items_per_page + 1

    def create_embed(self):
        start_idx = self.current_page * self.items_per_page
        end_idx = start_idx + self.items_per_page
        page_data = self.data[start_idx:end_idx]

        embed = create_base_embed(title=f"{self.title} (Стр. {self.current_page + 1}/{self.total_pages})", color=COLOR_BLURPLE, ctx=self.ctx)
        
        if not page_data:
            embed.description = "На этой странице нет записей."
            return embed

        for acc in page_data:
            content_preview = (acc['content'][:50] + '..') if len(acc['content']) > 50 else acc['content']
            embed.add_field(
                name=f"🆔 {acc['id']} • {acc['timestamp']}", 
                value=f"```{content_preview}```", 
                inline=False
            )
            
        embed.set_footer(text=f"Всего записей: {len(self.data)}")
        return embed

    def update_buttons(self):
        self.children[0].disabled = self.current_page == 0
        self.children[1].disabled = self.current_page == self.total_pages - 1
        
        # Update Select Menu Options
        start_idx = self.current_page * self.items_per_page
        end_idx = start_idx + self.items_per_page
        page_data = self.data[start_idx:end_idx]
        
        # Find the Select Menu (it's the last item usually, or check type)
        select = self.children[2] 
        select.options = []
        
        if page_data:
            for acc in page_data:
                content_preview = (acc['content'][:25] + '..') if len(acc['content']) > 25 else acc['content']
                select.add_option(
                    label=f"Удалить ID: {acc['id']}",
                    description=f"{content_preview}",
                    value=str(acc['id']),
                    emoji="🗑️"
                )
            select.disabled = False
        else:
            select.add_option(label="Нет записей", value="none") # Placeholder
            select.disabled = True

    @discord.ui.button(label="⬅️ Назад", style=discord.ButtonStyle.primary, row=1)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="Вперед ➡️", style=discord.ButtonStyle.primary, row=1)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.select(placeholder="Выберите запись для удаления...", min_values=1, max_values=1, row=2)
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        account_id = int(select.values[0])
        import utils # Lazy import to avoid circular dependency if any, or just use global
        
        # Delete the account
        if utils.delete_account(account_id):
            # Remove from local data
            self.data = [acc for acc in self.data if acc['id'] != account_id]
            self.total_pages = (len(self.data) - 1) // self.items_per_page + 1
            
            # Adjust current page if needed
            if self.current_page >= self.total_pages and self.total_pages > 0:
                self.current_page = self.total_pages - 1
            
            await interaction.response.send_message(f"✅ Запись **{account_id}** удалена.", ephemeral=True)
            
            # Refresh view
            self.update_buttons()
            await interaction.message.edit(embed=self.create_embed(), view=self)
        else:
            await interaction.response.send_message(f"❌ Не удалось удалить запись {account_id}.", ephemeral=True)

    async def on_timeout(self):
        # Disable all buttons on timeout
        for child in self.children:
            child.disabled = True
        try:
            # We need the message to edit it. 
            # In a real scenario we'd attach the message to the view or fetch it.
            # But here `interaction.message` is available in button callbacks. 
            # For timeout, we might not easily have the message reference if not stored.
            # However, usually we can leave it or try to edit if we saved the message object.
            pass 
        except:
            pass

class SecretView(discord.ui.View):
    def __init__(self, secret_id):
        super().__init__(timeout=None) # No timeout for the button itself, or maybe 24h
        self.secret_id = secret_id

    @discord.ui.button(label="🔐 Прочитать секрет", style=discord.ButtonStyle.danger, custom_id="reveal_secret_btn")
    async def reveal_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        import utils
        
        content = utils.reveal_secret(self.secret_id)
        
        if content:
            # Send ephemeral message with the secret
            await interaction.response.send_message(
                f"🤫 **Секретное сообщение:**\n||{content}||", 
                ephemeral=True
            )
            
            # Disable button and update original message
            button.disabled = True
            button.label = "💥 Уничтожено"
            button.style = discord.ButtonStyle.secondary
            
            await interaction.message.edit(view=self)
            
            # Optionally update the embed to say it's gone
            embed = interaction.message.embeds[0]
            embed.description = "### 💥 Сообщение было уничтожено после прочтения."
            embed.color = COLOR_DARK
            await interaction.message.edit(embed=embed)
            
        else:
            await interaction.response.send_message("❌ Сообщение уже удалено или не найдено.", ephemeral=True)
            # Update button to reflect state
            button.disabled = True
            button.label = "❌ Недействительно"
            await interaction.message.edit(view=self)

def monitor_list(monitors, ctx):
    embed = create_base_embed(title="🌐 Мониторинг Сайтов", description="Статус отслеживаемых ресурсов", color=COLOR_BLURPLE, ctx=ctx)
    
    if not monitors:
        embed.description = "Список отслеживания пуст. Добавьте сайты с помощью `!monitor add <url>`."
        return embed
        
    for m in monitors:
        status_icon = "🟢" if m['status'] == 'online' else "🔴" if m['status'] == 'offline' else "⚪"
        last_check = f"<t:{int(datetime.fromisoformat(m['last_checked']).timestamp())}:R>" if m['last_checked'] else "Никогда"
        
        # Decode error reason if offline
        details = ""
        if m['status'] == 'offline' and m['last_status_code']:
            reasons = {
                0: "Ошибка сети/DNS",
                403: "Forbidden",
                404: "Not Found",
                500: "Server Error",
                502: "Bad Gateway",
                503: "Unavailable",
                504: "Timeout"
            }
            reason = reasons.get(m['last_status_code'], "Ошибка")
            details = f"\n❌ **Причина:** {reason} (Code: {m['last_status_code']})"
        elif m['last_status_code']:
             details = f" (Code: {m['last_status_code']})"

        embed.add_field(
            name=f"{status_icon} {m['name']}",
            value=f"URL: {m['url']}\nСтатус: **{m['status'].upper()}**{details}\nПроверка: {last_check}\nID: `{m['id']}`",
            inline=False
        )
    return embed

def monitor_alert(monitor, status_code, ctx=None):
    color = COLOR_RED
    
    # Расшифровка кодов ошибок
    reasons = {
        0: "Ошибка подключения (Возможно DNS, таймаут или блокировка)",
        403: "Доступ запрещен (Forbidden)",
        404: "Страница не найдена (Not Found)",
        500: "Внутренняя ошибка сервера (Internal Server Error)",
        502: "Bad Gateway (Ошибка шлюза)",
        503: "Сервис недоступен (Service Unavailable)",
        504: "Gateway Timeout (Таймаут шлюза)"
    }
    
    reason_text = reasons.get(status_code, "Неизвестная ошибка")
    timestamp = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

    embed = discord.Embed(title="🚨 ВНИМАНИЕ: Сайт УПАЛ!", description=f"Ресурс **{monitor['name']}** перестал отвечать на запросы.", color=color)
    embed.add_field(name="🔗 URL", value=f"[Перейти]({monitor['url']})", inline=False)
    embed.add_field(name="🛑 Код ошибки", value=f"`{status_code}`", inline=True)
    embed.add_field(name="❓ Причина", value=reason_text, inline=True)
    embed.add_field(name="🕒 Время инцидента", value=timestamp, inline=False)
    
    embed.set_footer(text=f"ID монитора: {monitor['id']} • Попробуйте проверить вручную")
    embed.set_thumbnail(url="https://media.discordapp.net/attachments/123/alert_icon.png") # Можно заменить на любую картинку тревоги
    
    return embed

def monitor_recovery_alert(monitor, ctx=None):
    color = COLOR_GREEN
    timestamp = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

    embed = discord.Embed(title="✅ ВОССТАНОВЛЕНИЕ: Сайт доступен!", description=f"Ресурс **{monitor['name']}** снова отвечает на запросы.", color=color)
    embed.add_field(name="🔗 URL", value=f"[Перейти]({monitor['url']})", inline=False)
    embed.add_field(name="🕒 Время восстановления", value=timestamp, inline=False)
    
    embed.set_footer(text=f"ID монитора: {monitor['id']}")
    return embed


# --- Temp Mail UI ---

def temp_email_created(email, ctx=None):
    """Display created temporary email"""
    embed = create_base_embed(
        title="📬 Временный E-mail создан!",
        description=f"Ваш временный адрес электронной почты готов к использованию.",
        color=COLOR_GREEN,
        ctx=ctx
    )
    
    embed.add_field(name="📧 Адрес", value=f"```{email}```", inline=False)
    embed.add_field(name="⏱️ Время жизни", value="Письма хранятся несколько часов", inline=True)
    embed.add_field(name="🔄 Проверка", value="Используйте `!tempmail check` для проверки писем", inline=True)
    
    embed.set_footer(text="💡 Совет: Сохраните адрес, чтобы проверить почту позже!")
    
    return embed

def temp_mail_inbox(email, messages, ctx=None):
    """Display inbox with list of messages"""
    if not messages:
        embed = create_base_embed(
            title=f"📭 Входящие: {email}",
            description="Входящих писем пока нет. Проверьте позже!",
            color=COLOR_YELLOW,
            ctx=ctx
        )
        embed.set_footer(text="Письма появятся здесь автоматически")
        return embed
    
    embed = create_base_embed(
        title=f"📬 Входящие ({len(messages)})",
        description=f"**Почта:** `{email}`\n\n",
        color=COLOR_BLURPLE,
        ctx=ctx
    )
    
    for idx, msg in enumerate(messages[:10], 1):  # Показываем максимум 10
        from_addr = msg.get('from', 'Неизвестно')
        subject = msg.get('subject', 'Без темы')
        date = msg.get('date', '')
        msg_id = msg.get('id', '')
        
        # Truncate long subjects
        if len(subject) > 40:
            subject = subject[:37] + "..."
        
        embed.add_field(
            name=f"📩 #{idx} • {subject}",
            value=f"**От:** {from_addr}\n**Дата:** {date}\n**ID:** `{msg_id}`",
            inline=False
        )
    
    if len(messages) > 10:
        embed.set_footer(text=f"Показано 10 из {len(messages)} писем")
    else:
        embed.set_footer(text=f"Всего писем: {len(messages)}")
    
    return embed

def temp_mail_message(email, message, ctx=None):
    """Display full message content"""
    if not message:
        return error("Письмо не найдено или уже удалено.", ctx)
    
    from_addr = message.get('from', 'Неизвестно')
    subject = message.get('subject', 'Без темы')
    date = message.get('date', '')
    body = message.get('textBody', message.get('htmlBody', 'Нет содержимого'))
    
    # Truncate very long messages
    if len(body) > 1500:
        body = body[:1500] + "\n\n... (сообщение обрезано)"
    
    embed = create_base_embed(
        title=f"📧 {subject}",
        description=f"",
        color=COLOR_BLURPLE,
        ctx=ctx
    )
    
    embed.add_field(name="📤 От", value=f"`{from_addr}`", inline=True)
    embed.add_field(name="📥 Кому", value=f"`{email}`", inline=True)
    embed.add_field(name="📅 Дата", value=date, inline=False)
    embed.add_field(name="📃 Содержимое", value=f"```{body}```", inline=False)
    
    # Add attachments info if any
    attachments = message.get('attachments', [])
    if attachments:
        attach_list = "\n".join([f"📎 {a.get('filename', 'file')}" for a in attachments[:5]])
        embed.add_field(name="📎 Вложения", value=attach_list, inline=False)
    
    return embed

def temp_mail_help(ctx=None):
    """Show help for temp mail commands"""
    embed = create_base_embed(
        title="📬 Временная почта • Инструкция",
        description="Создание одноразовых email адресов для регистраций и тестирования",
        color=COLOR_BLURPLE,
        ctx=ctx
    )
    
    embed.add_field(
        name="`!tempmail create`",
        value="Создать новый временный email адрес",
        inline=False
    )
    
    embed.add_field(
        name="`!tempmail check <email>`",
        value="Проверить входящие письма для указанного адреса",
        inline=False
    )
    
    embed.add_field(
        name="`!tempmail read <email> <message_id>`",
        value="Прочитать конкретное письмо по ID",
        inline=False
    )
    
    embed.add_field(
        name="`!tempmail domains`",
        value="Показать доступные домены для создания email",
        inline=False
    )
    
    embed.set_footer(text="💡 Письма хранятся несколько часов, затем автоматически удаляются")
    
    return embed


# --- AI Chat UI ---

def ai_help(ctx=None):
    """Show help for AI commands"""
    embed = create_base_embed(
        title="🤖 AI Ассистент • Инструкция",
        description="Мощный ИИ на базе Google Gemini для ответов на любые вопросы",
        color=COLOR_BLURPLE,
        ctx=ctx
    )
    
    embed.add_field(
        name="💬 `!ai <вопрос>`",
        value="Задать одиночный вопрос без сохранения контекста",
        inline=False
    )
    
    embed.add_field(
        name="🗣️ `!chat <сообщение>`",
        value="Чат с памятью — ИИ помнит ваш диалог",
        inline=False
    )
    
    embed.add_field(
        name="🗑️ `!clear`",
        value="Очистить историю диалога и начать заново",
        inline=False
    )
    
    embed.add_field(
        name="🌍 `!translate <язык> <текст>`",
        value="Перевести текст. Пример: `!translate en Привет мир`",
        inline=False
    )
    
    embed.add_field(
        name="💻 `!code <задача>`",
        value="Написать код. Пример: `!code функция сортировки на Python`",
        inline=False
    )
    
    embed.add_field(
        name="🎨 `!imagine <описание>`",
        value="Получить детальное описание изображения по запросу",
        inline=False
    )
    
    embed.set_footer(text="Powered by Gemini AI • Бесплатно и без ограничений")
    
    return embed


# ============================================================
# 🎮 ARIZONA RP ASSISTANT UI
# ============================================================

def arizona_main_menu(ctx=None):
    """Главное меню Arizona RP Assistant"""
    embed = create_base_embed(
        title="🎮 Arizona RP Assistant",
        description="""**Добро пожаловать в AI-ассистент Arizona RP!**

Я помогу вам разобраться в правилах сервера, терминологии и игровых ситуациях.

**🔥 Возможности:**
• Поиск по правилам сервера
• Объяснение терминов (DM, RK, PG...)
• Калькулятор наказаний
• AI-чат с памятью диалога
• Помощь с жалобами

**Выберите действие ниже или используйте команды:**""",
        color=0xFF6B35,  # Оранжевый Arizona
        ctx=ctx
    )
    
    embed.add_field(
        name="📝 Быстрые команды",
        value="""
`!az rules <запрос>` — поиск правил
`!az ask <вопрос>` — задать вопрос AI
`!az penalty <нарушение>` — узнать наказание
`!az terms` — терминология
`!az help` — все команды
        """,
        inline=False
    )
    
    embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1234/arizona_logo.png")  # Placeholder
    embed.set_footer(text="Arizona RP Assistant • Powered by Gemini AI")
    
    return embed


def arizona_help(ctx=None):
    """Показать все команды Arizona Assistant"""
    embed = create_base_embed(
        title="🎮 Arizona RP Assistant — Команды",
        description="Полный список доступных команд",
        color=0xFF6B35,
        ctx=ctx
    )
    
    embed.add_field(
        name="📖 `!az rules [запрос]`",
        value="Поиск по правилам. Без аргумента — список разделов",
        inline=False
    )
    
    embed.add_field(
        name="❓ `!az ask <вопрос>`",
        value="Задать вопрос AI-ассистенту (одиночный)",
        inline=False
    )
    
    embed.add_field(
        name="💬 `!az chat <сообщение>`",
        value="Чат с AI с памятью диалога",
        inline=False
    )
    
    embed.add_field(
        name="🔄 `!az reset`",
        value="Сбросить историю диалога с AI",
        inline=False
    )
    
    embed.add_field(
        name="⚖️ `!az penalty <нарушение>`",
        value="Калькулятор наказаний",
        inline=False
    )
    
    embed.add_field(
        name="📚 `!az terms`",
        value="Показать терминологию Arizona RP",
        inline=False
    )
    
    embed.add_field(
        name="📝 `!az report`",
        value="Как подать жалобу",
        inline=False
    )
    
    embed.add_field(
        name="💡 Алиасы",
        value="`!arizona`, `!az`, `!ари`, `!аризона` — все работают одинаково",
        inline=False
    )
    
    return embed


class ArizonaMainMenu(discord.ui.View):
    """Интерактивное главное меню Arizona Assistant"""
    
    def __init__(self, ctx):
        super().__init__(timeout=120)
        self.ctx = ctx
    
    @discord.ui.button(label="📖 Правила", style=discord.ButtonStyle.primary, row=0)
    async def rules_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Показать категории правил"""
        embed = create_base_embed(
            title="📖 Категории правил Arizona RP",
            description="Выберите категорию для просмотра:",
            color=COLOR_BLURPLE,
            ctx=self.ctx
        )
        
        categories = [
            ("🎮 Игровой процесс", "`!az rules dm` • `!az rules rk` • `!az rules pg`"),
            ("💬 Правила чата", "`!az rules чат` • `!az rules voice`"),
            ("🛡️ Читы и моды", "`!az rules читы`"),
            ("⚔️ Капты и мероприятия", "`!az rules капт` • `!az rules мероприятие`"),
            ("👮 Силовые структуры", "`!az rules полиция`"),
            ("💰 Экономика", "`!az rules бизнес`"),
            ("📝 Жалобы", "`!az rules жалоба`"),
        ]
        
        for name, value in categories:
            embed.add_field(name=name, value=value, inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="📚 Термины", style=discord.ButtonStyle.secondary, row=0)
    async def terms_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Показать терминологию"""
        import arizona_rules
        terms = arizona_rules.ARIZONA_RULES.get("термины", {})
        
        embed = create_base_embed(
            title="📚 Терминология Arizona RP",
            description=terms.get("content", "Не найдено")[:4000],
            color=COLOR_BLURPLE,
            ctx=self.ctx
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="⚖️ Наказания", style=discord.ButtonStyle.danger, row=0)
    async def penalty_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Показать информацию о наказаниях"""
        embed = create_base_embed(
            title="⚖️ Калькулятор наказаний",
            description="""**Используйте команду:**
`!az penalty <нарушение>`

**Примеры:**
• `!az penalty dm` — узнать срок за DM
• `!az penalty читы` — наказание за читы
• `!az penalty флуд` — наказание за флуд

**Шкала наказаний:**
🟡 **Мут** — ограничение чата (10-300 мин)
🟠 **Деморган** — изоляция (20-1200 мин)
🔴 **Варн** — предупреждение (3 варна = бан)
⛔ **Бан** — блокировка (1-2000 дней)
☠️ **ЧСС/ЧСП** — полный запрет""",
            color=COLOR_RED,
            ctx=self.ctx
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="🤖 AI Чат", style=discord.ButtonStyle.success, row=1)
    async def ai_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Информация об AI чате"""
        embed = create_base_embed(
            title="🤖 Arizona AI Assistant",
            description="""**Два режима общения с AI:**

**1️⃣ Одиночный вопрос** — `!az ask <вопрос>`
AI ответит на вопрос без сохранения контекста.
Пример: `!az ask что такое DM?`

**2️⃣ Чат с памятью** — `!az chat <сообщение>`
AI запомнит ваш диалог и будет учитывать контекст.
Сброс диалога: `!az reset`

**💡 AI знает:**
• Все правила Arizona RP
• Терминологию сервера
• Наказания за нарушения
• Игровые механики""",
            color=0x10B981,
            ctx=self.ctx
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="📝 Жалоба", style=discord.ButtonStyle.secondary, row=1)
    async def report_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Информация о жалобах"""
        import arizona_rules
        result = arizona_rules.search_rules("жалоба")
        
        embed = create_base_embed(
            title="📝 Как подать жалобу",
            description=result[:4000] if result else "Информация не найдена",
            color=COLOR_BLURPLE,
            ctx=self.ctx
        )
        
        embed.add_field(
            name="🔗 Полезные ссылки",
            value="• [Форум Arizona](https://forum.arizona-rp.com/)\n• [Правила](https://arizona-rp.com/rules)",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class ArizonaRulesSelect(discord.ui.View):
    """Селект-меню для выбора категории правил"""
    
    def __init__(self, ctx):
        super().__init__(timeout=60)
        self.ctx = ctx
    
    @discord.ui.select(
        placeholder="Выберите категорию правил...",
        options=[
            discord.SelectOption(label="DM (DeathMatch)", value="dm", emoji="💀"),
            discord.SelectOption(label="RK (RevengeKill)", value="rk", emoji="🔄"),
            discord.SelectOption(label="PG (PowerGaming)", value="pg", emoji="💪"),
            discord.SelectOption(label="MG (MetaGaming)", value="mg", emoji="🧠"),
            discord.SelectOption(label="NonRP поведение", value="nonrp", emoji="🚫"),
            discord.SelectOption(label="Правила чата", value="чат", emoji="💬"),
            discord.SelectOption(label="Читы и моды", value="читы", emoji="🛡️"),
            discord.SelectOption(label="Капты", value="капт", emoji="⚔️"),
            discord.SelectOption(label="Полиция/ФБР", value="полиция", emoji="👮"),
            discord.SelectOption(label="Жалобы", value="жалоба", emoji="📝"),
        ]
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        import arizona_rules
        
        selected = select.values[0]
        result = arizona_rules.search_rules(selected)
        
        if result:
            embed = create_base_embed(
                title=f"📖 Правила: {selected.upper()}",
                description=result[:4000],
                color=COLOR_GREEN,
                ctx=self.ctx
            )
        else:
            embed = warning(f"Правила для `{selected}` не найдены", self.ctx)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


