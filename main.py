import discord
import os
from discord.ext import commands, tasks
import aiohttp
from dotenv import load_dotenv
import utils
import ui

# Google Gemini AI
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("[!] google-generativeai not installed. AI features disabled.")

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Настройка Gemini AI
if GEMINI_AVAILABLE and GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    AI_MODEL = genai.GenerativeModel('gemini-2.0-flash')
    print("[+] Gemini AI initialized successfully!")
else:
    AI_MODEL = None

# Хранилище истории чатов для каждого пользователя
AI_CHAT_HISTORY = {}

# Настройка интентов
intents = discord.Intents.default()
intents.message_content = True

def get_prefix_func(bot, message):
    if not message.guild: return '!'
    p = utils.get_prefix(message.author.id) 
    return p if p else '!'

# Отключаем стандартный help, чтобы сделать свой красивый
bot = commands.Bot(command_prefix=get_prefix_func, intents=intents, help_command=None)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(embed=ui.error(f"Missing argument!\nUsage: `{ctx.prefix}{ctx.command.name} {ctx.command.signature}`", ctx))
    elif isinstance(error, commands.CommandNotFound):
        print(f"DEBUG: Command not found - {ctx.message.content}")
        pass 
    else:
        print(f"Ignoring exception: {error}")

@bot.event
async def on_ready():
    print(f'--------------------------------------------------')
    print(f'PREMIUM BOT V2.0 STARTED: {bot.user.name}')
    print(f'--------------------------------------------------')
    await bot.change_presence(activity=discord.Game(name="!help | Secure Archive"))
    if not monitor_task.is_running():
        monitor_task.start()

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    print(f"Message from {message.author}: {message.content}")
    await bot.process_commands(message)


# --- Background Monitor Task ---
@tasks.loop(minutes=5)
async def monitor_task():
    monitors = utils.get_monitors()
    if not monitors:
        return

    # Assuming we want to notify a specific channel or the owner. 
    # For simplicity, we'll try to find a channel named 'alerts' or 'monitoring', or DM the owner.
    # Since we don't store a config for "alert channel" yet, let's just print to console 
    # and if we can find a context from a cached variable (tricky), we notify.
    # BETTER APPROACH: Just print status for now, or notify all channels where 'monitor' command was last used?
    # Let's save a "notify_channel_id" in a simple var if user sets it.
    
    # Simple Async Request Code
    # Add User-Agent to mimic a browser and avoid blocking
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    async with aiohttp.ClientSession() as session:
        for m in monitors:
            try:
                # Use headers and disable ssl verify if needed (though dangerous, sometimes needed for self-signed)
                # But better to just use headers first.
                async with session.get(m['url'], headers=headers, timeout=15) as resp:
                    new_status = 'online' if resp.status == 200 else 'offline'
                    code = resp.status
            except Exception as e:
                print(f"DEBUG: Monitor failed for {m['url']} - Error: {e}")
                new_status = 'offline'
                code = 0
            
            # Update DB only if changed
            if m['status'] != new_status:
                utils.update_monitor_status(m['id'], new_status, code)
                print(f"[Monitor] Site {m['name']} is now {new_status} (Code: {code})")
                
                # Notification Logic
                if new_status == 'offline':
                    # Try to find a channel to notify
                    # Option 1: Hardcode ID (Replace with your ID) -> channel = bot.get_channel(123456789)
                    # Option 2: Find channel by name "monitoring" or "general"
                    channel = discord.utils.get(bot.get_all_channels(), name='monitoring')
                    if not channel:
                         channel = discord.utils.get(bot.get_all_channels(), name='general')
                    
                    if channel:
                        await channel.send(embed=ui.monitor_alert(m, code))
                    else:

                        print("Create a channel named 'monitoring' to receive alerts!")
                
                elif new_status == 'online' and m['status'] != 'unknown':
                     # Notify about recovery (but ignore first check from unknown)
                    channel = discord.utils.get(bot.get_all_channels(), name='monitoring')
                    if not channel:
                         channel = discord.utils.get(bot.get_all_channels(), name='general')
                    
                    if channel:
                        await channel.send(embed=ui.monitor_recovery_alert(m))
            else:
                # Still update checked time
                utils.update_monitor_status(m['id'], new_status, code)


# --- Custom Help Command ---
@bot.command(name='help')
async def help_command(ctx):
    """Показать это меню помощи"""
    embed = ui.smart_help(ctx, bot.commands)
    await ctx.send(embed=embed)

@bot.command(name='add')
async def add_account(ctx, *, content: str):
    """Добавить запись. Формат: текст"""
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass

    account_id = utils.save_account(content, ctx.author)
    
    embed = ui.success(f"Запись успешно сохранена.\n**ID:** `{account_id}`", ctx)
    # Футер уже ставится внутри ui.success
    await ctx.send(embed=embed)

@bot.command(name='list')
async def list_accounts(ctx):
    """Показать все записи (с пагинацией)"""
    accounts = utils.get_all_accounts()
    
    if not accounts:
        await ctx.send(embed=ui.info("📂 Архив", "База данных пуста.", ctx))
        return

    # Sort by ID descending (newest first)
    accounts = sorted(accounts, key=lambda x: x['id'], reverse=True)

    view = ui.PaginationView(ctx, accounts, title="📂 Сохраненные записи", items_per_page=5)
    
    # If there's only 1 page, we don't need buttons, but let's keep it consistent or disable them
    view.update_buttons()
    
    # Send the first page
    message = await ctx.send(embed=view.create_embed(), view=view)
    # Store message in view if needed for timeout updates, though simple timeout handling is enough


@bot.command(name='search')
async def search(ctx, *, query: str):
    """Найти запись. Пример: !search google"""
    results = utils.search_accounts(query)
    
    if not results:
        await ctx.send(embed=ui.warning(f"По запросу `{query}` ничего не найдено.", ctx))
        return

    embed = ui.create_base_embed(title=f"🔍 Результаты: {query}", color=ui.COLOR_BLURPLE, ctx=ctx)
    
    for acc in results[-10:]:
        embed.add_field(
            name=f"🆔 {acc['id']}", 
            value=f"```{acc['content']}```", 
            inline=False
        )
        
    await ctx.send(embed=embed)

@bot.command(name='delete')
async def delete(ctx, account_id: int):
    """Удалить запись по ID"""
    success = utils.delete_account(account_id)
    if success:
        await ctx.send(embed=ui.success(f"Запись **{account_id}** удалена.", ctx))
    else:
        await ctx.send(embed=ui.error(f"Запись **{account_id}** не найдена.", ctx))

@bot.command(name='edit')
async def edit(ctx, account_id: int, *, new_content: str):
    """Изменить запись. Пример: !edit 1 новый текст"""
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass

    success = utils.edit_account(account_id, new_content)
    if success:
        await ctx.send(embed=ui.success(f"Запись **{account_id}** обновлена.", ctx))
    else:
        await ctx.send(embed=ui.error(f"Запись **{account_id}** не найдена.", ctx))

@bot.command(name='genpass')
async def genpass(ctx, length: int = 12):
    """Генератор паролей"""
    if length > 50:
        await ctx.send(embed=ui.error("Слишком длинный пароль (макс 50).", ctx))
        return
    
    password = utils.generate_password(length)
    
    # Используем Yellow/Gold для важных данных
    embed = ui.create_base_embed(title="🔑 Генератор", description=f"||`{password}`||", color=ui.COLOR_YELLOW, ctx=ctx)
    embed.add_field(name="Подсказка", value="Нажмите на скрытый текст, чтобы скопировать.")
    await ctx.send(embed=embed)

@bot.command(name='backup', aliases=['export'])
async def backup_data(ctx):
    """Отправить бэкап базы данных в ЛС"""
    if os.path.exists(utils.DATA_FILE):
        try:
            embed = ui.success("Файл базы данных отправлен вам в ЛС.", ctx)
            await ctx.author.send(file=discord.File(utils.DATA_FILE))
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send(embed=ui.error("Не могу отправить сообщение в ЛС. Откройте личные сообщения.", ctx))
    else:
        await ctx.send(embed=ui.warning("База данных еще не создана.", ctx))



@bot.command(name='secret')
async def secret(ctx, *, content: str):
    """Создать самоуничтожающееся сообщение"""
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass
        
    secret_id = utils.create_secret(content)
    view = ui.SecretView(secret_id)
    
    embed = ui.create_base_embed(title="🕵️ Секретное сообщение", description="Это сообщение уничтожится после первого прочтения.", color=ui.COLOR_DARK, ctx=ctx)
    embed.add_field(name="ID", value=f"`{secret_id}`")
    
    await ctx.send(embed=embed, view=view)

@bot.command(name='stats')
async def stats(ctx):
    """Показать статистику сервера"""
    # Top users
    top_users = utils.get_user_stats()
    top_text = ""
    for idx, (user, count) in enumerate(top_users, 1):
        medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else "🔸"
        top_text += f"{medal} **{user}**: {count} записей\n"
        
    if not top_text:
        top_text = "Нет данных."

    # Graph
    chart_file = utils.generate_activity_chart()
    file = discord.File(chart_file, filename="activity.png") if chart_file else None
    
    embed = ui.create_base_embed(title="📊 Статистика", color=ui.COLOR_BLURPLE, ctx=ctx)
    embed.add_field(name="🏆 Топ активных", value=top_text, inline=False)
    
    if file:
        embed.set_image(url="attachment://activity.png")
        await ctx.send(embed=embed, file=file)
    else:
        embed.set_footer(text="Недостаточно данных для графика")
        await ctx.send(embed=embed)

@bot.group(name='monitor', invoke_without_command=True)
async def monitor(ctx):
    """Система мониторинга сайтов."""
    await ctx.send(embed=ui.info("🌐 Мониторинг", "Используйте:\n`!monitor add <url>` - добавить\n`!monitor remove <id>` - удалить\n`!monitor list` - список", ctx))

@monitor.command(name='add')
async def monitor_add(ctx, url: str, *, name: str = None):
    """Добавить сайт для отслеживания"""
    success, result = utils.add_monitor(url, name)
    if success:
        await ctx.send(embed=ui.success(f"Сайт **{result['name']}** добавлен в мониторинг.", ctx))
        # Trigger an immediate check?
        # For simplicity, wait for next loop or user generic check
    else:
        await ctx.send(embed=ui.warning(result, ctx))

@monitor.command(name='list')
async def monitor_list_cmd(ctx):
    """Показать список сайтов и их статус"""
    monitors = utils.get_monitors()
    embed = ui.monitor_list(monitors, ctx)
    await ctx.send(embed=embed)

@monitor.command(name='remove')
async def monitor_remove(ctx, monitor_id: str):
    """Удалить сайт из мониторинга по ID или имени"""
    success = utils.remove_monitor(monitor_id)
    if success:
        await ctx.send(embed=ui.success("Сайт удален из отслеживания.", ctx))
    else:
        await ctx.send(embed=ui.error("Сайт не найден.", ctx))

@monitor.command(name='check')
async def monitor_check_now(ctx):
    """Принудительно проверить все сайты сейчас"""
    msg = await ctx.send("🔄 Проверяю статусы...")
    await monitor_task() # Run once
    monitors = utils.get_monitors()
    await msg.edit(content=None, embed=ui.monitor_list(monitors, ctx))


# --- Temp Mail Commands ---

@bot.group(name='tempmail', aliases=['tm', 'mail'], invoke_without_command=True)
async def tempmail(ctx):
    """Временная почта для регистраций"""
    await ctx.send(embed=ui.temp_mail_help(ctx))

# Store temp mail tokens in memory
TEMP_MAIL_TOKENS = {}

@tempmail.command(name='create', aliases=['new', 'gen'])
async def tempmail_create(ctx, count: int = 1):
    """Создать временный email адрес"""
    if count < 1 or count > 10:
        await ctx.send(embed=ui.error("Количество должно быть от 1 до 10.", ctx))
        return
    
    msg = await ctx.send("🔄 Генерирую временный email...")
    
    async with aiohttp.ClientSession() as session:
        emails = await utils.get_temp_email(session, count)
        
        if not emails:
            await msg.edit(content=None, embed=ui.error("Не удалось создать временный email. Попробуйте позже.", ctx))
            return
            
        # Store tokens
        for item in emails:
            TEMP_MAIL_TOKENS[item['email']] = item['token']
        
        if count == 1:
            await msg.edit(content=None, embed=ui.temp_email_created(emails[0]['email'], ctx))
        else:
            # Multiple emails
            email_list = "\n".join([f"📧 `{e['email']}`" for e in emails])
            embed = ui.create_base_embed(
                title=f"📬 Создано временных адресов: {len(emails)}",
                description=email_list,
                color=ui.COLOR_GREEN,
                ctx=ctx
            )
            embed.set_footer(text="Используйте !tempmail check <email> для проверки почты")
            await msg.edit(content=None, embed=embed)

@tempmail.command(name='check', aliases=['inbox', 'messages'])
async def tempmail_check(ctx, email: str):
    """Проверить входящие письма"""
    if '@' not in email:
        await ctx.send(embed=ui.error("Неверный формат email адреса.", ctx))
        return
        
    token = TEMP_MAIL_TOKENS.get(email)
    if not token:
        await ctx.send(embed=ui.error("Email не найден в активной сессии бота (или устарел). Создайте новый.", ctx))
        return
    
    msg = await ctx.send("📬 Проверяю почту...")
    
    async with aiohttp.ClientSession() as session:
        messages = await utils.get_temp_mail_messages(session, token)
        
        await msg.edit(content=None, embed=ui.temp_mail_inbox(email, messages, ctx))

@tempmail.command(name='read', aliases=['open', 'view'])
async def tempmail_read(ctx, email: str, message_id: str):
    """Прочитать письмо по ID"""
    if '@' not in email:
        await ctx.send(embed=ui.error("Неверный формат email адреса.", ctx))
        return

    token = TEMP_MAIL_TOKENS.get(email)
    if not token:
        await ctx.send(embed=ui.error("Email не найден в активной сессии бота.", ctx))
        return
        
    async with aiohttp.ClientSession() as session:
        message = await utils.read_temp_mail_message(session, token, message_id)
        if message:
            await ctx.send(embed=ui.temp_mail_message(email, message, ctx))
        else:
             await ctx.send(embed=ui.error("Письмо не найдено или ошибка загрузки.", ctx))
    
    msg = await ctx.send("📖 Открываю письмо...")
    
    async with aiohttp.ClientSession() as session:
        message = await utils.read_temp_mail_message(session, email, message_id)
        
        await msg.edit(content=None, embed=ui.temp_mail_message(email, message, ctx))

@tempmail.command(name='domains', aliases=['domain', 'list'])
async def tempmail_domains(ctx):
    """Показать доступные домены"""
    msg = await ctx.send("🔄 Загружаю список доменов...")
    
    async with aiohttp.ClientSession() as session:
        domains = await utils.get_temp_mail_domains(session)
        
        if not domains:
            await msg.edit(content=None, embed=ui.error("Не удалось загрузить список доменов.", ctx))
            return
        
        # Show domains in chunks
        domain_list = "\n".join([f"• `{domain}`" for domain in domains[:30]])
        
        embed = ui.create_base_embed(
            title="🌐 Доступные домены для создания email",
            description=domain_list,
            color=ui.COLOR_BLURPLE,
            ctx=ctx
        )
        
        if len(domains) > 30:
            embed.set_footer(text=f"Показано 30 из {len(domains)} доменов")
        else:
            embed.set_footer(text=f"Всего доступно доменов: {len(domains)}")
        
        await msg.edit(content=None, embed=embed)


# --- AI Chat Commands ---

@bot.command(name='ai')
async def ai_single(ctx, *, question: str):
    """Задать вопрос ИИ (одиночный запрос без памяти)"""
    if not AI_MODEL:
        await ctx.send(embed=ui.error("❌ AI не настроен! Добавьте GEMINI_API_KEY в .env", ctx))
        return
    
    # Показываем что бот печатает
    async with ctx.typing():
        try:
            response = AI_MODEL.generate_content(question)
            answer = response.text
            
            # Обрезаем если слишком длинный
            if len(answer) > 4000:
                answer = answer[:4000] + "...\n\n*[Ответ обрезан]*"
            
            embed = ui.create_base_embed(
                title="🤖 AI Ответ",
                description=answer,
                color=ui.COLOR_BLURPLE,
                ctx=ctx
            )
            embed.add_field(name="❓ Вопрос", value=f"```{question[:200]}```", inline=False)
            embed.set_footer(text="Powered by Gemini AI • Одиночный запрос")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(embed=ui.error(f"Ошибка AI: {str(e)[:200]}", ctx))


@bot.command(name='chat')
async def ai_chat(ctx, *, message: str):
    """Чат с ИИ с памятью разговора"""
    if not AI_MODEL:
        await ctx.send(embed=ui.error("❌ AI не настроен! Добавьте GEMINI_API_KEY в .env", ctx))
        return
    
    user_id = str(ctx.author.id)
    
    # Создаем или получаем сессию чата
    if user_id not in AI_CHAT_HISTORY:
        AI_CHAT_HISTORY[user_id] = AI_MODEL.start_chat(history=[])
    
    chat = AI_CHAT_HISTORY[user_id]
    
    async with ctx.typing():
        try:
            response = chat.send_message(message)
            answer = response.text
            
            if len(answer) > 4000:
                answer = answer[:4000] + "...\n\n*[Ответ обрезан]*"
            
            # Считаем сообщения в истории
            msg_count = len(chat.history) // 2
            
            embed = ui.create_base_embed(
                title="💬 AI Чат",
                description=answer,
                color=0x10B981,  # Зеленый для чата
                ctx=ctx
            )
            embed.set_footer(text=f"Сообщений в диалоге: {msg_count} • !clear чтобы начать заново")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(embed=ui.error(f"Ошибка AI: {str(e)[:200]}", ctx))


@bot.command(name='clear', aliases=['reset', 'newchat'])
async def ai_clear(ctx):
    """Очистить историю диалога с ИИ"""
    user_id = str(ctx.author.id)
    
    if user_id in AI_CHAT_HISTORY:
        del AI_CHAT_HISTORY[user_id]
        await ctx.send(embed=ui.success("🗑️ История диалога очищена! Начинаем с чистого листа.", ctx))
    else:
        await ctx.send(embed=ui.info("💬 Чат", "У вас еще нет активного диалога.", ctx))


@bot.command(name='imagine', aliases=['img', 'draw'])
async def ai_imagine(ctx, *, prompt: str):
    """Описать как бы выглядела картинка (Gemini не генерирует изображения)"""
    if not AI_MODEL:
        await ctx.send(embed=ui.error("❌ AI не настроен!", ctx))
        return
    
    async with ctx.typing():
        try:
            enhanced_prompt = f"""Ты художник. Опиши максимально детально и красочно, 
            как бы выглядела картина/изображение по запросу: "{prompt}"
            Опиши цвета, композицию, освещение, настроение, стиль."""
            
            response = AI_MODEL.generate_content(enhanced_prompt)
            answer = response.text
            
            if len(answer) > 4000:
                answer = answer[:4000] + "..."
            
            embed = ui.create_base_embed(
                title="🎨 Визуализация",
                description=answer,
                color=0xF59E0B,  # Оранжевый для креатива
                ctx=ctx
            )
            embed.add_field(name="🖼️ Запрос", value=f"`{prompt[:100]}`", inline=False)
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(embed=ui.error(f"Ошибка: {str(e)[:200]}", ctx))


@bot.command(name='translate', aliases=['tr'])
async def ai_translate(ctx, lang: str, *, text: str):
    """Перевести текст. Пример: !translate en Привет мир"""
    if not AI_MODEL:
        await ctx.send(embed=ui.error("❌ AI не настроен!", ctx))
        return
    
    async with ctx.typing():
        try:
            prompt = f"Переведи следующий текст на язык '{lang}'. Дай только перевод без пояснений:\n\n{text}"
            response = AI_MODEL.generate_content(prompt)
            translation = response.text.strip()
            
            embed = ui.create_base_embed(
                title="🌍 Перевод",
                color=0x8B5CF6,
                ctx=ctx
            )
            embed.add_field(name="📝 Оригинал", value=f"```{text[:500]}```", inline=False)
            embed.add_field(name=f"🔄 Перевод ({lang.upper()})", value=f"```{translation[:500]}```", inline=False)
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(embed=ui.error(f"Ошибка: {str(e)[:200]}", ctx))


@bot.command(name='code', aliases=['программа', 'код'])
async def ai_code(ctx, *, task: str):
    """Написать код. Пример: !code напиши функцию сортировки на Python"""
    if not AI_MODEL:
        await ctx.send(embed=ui.error("❌ AI не настроен!", ctx))
        return
    
    async with ctx.typing():
        try:
            prompt = f"""Напиши код для следующей задачи. 
            Дай только код с комментариями, без лишних объяснений.
            Задача: {task}"""
            
            response = AI_MODEL.generate_content(prompt)
            code = response.text
            
            if len(code) > 4000:
                code = code[:4000] + "\n# ... (обрезано)"
            
            embed = ui.create_base_embed(
                title="💻 Код",
                description=code,
                color=0x3B82F6,
                ctx=ctx
            )
            embed.add_field(name="📋 Задача", value=f"`{task[:100]}`", inline=False)
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(embed=ui.error(f"Ошибка: {str(e)[:200]}", ctx))


# ============================================================
# 🎮 ARIZONA RP AI ASSISTANT - ГЛОБАЛЬНАЯ СИСТЕМА
# ============================================================

import arizona_rules

# Системный промпт для Octave
ARIZONA_AI_SYSTEM_PROMPT = """Ты — официальный AI-ассистент сервера Arizona RP (GTA SAMP).

ТВОИ ЗАДАЧИ:
1. Отвечать на вопросы по правилам Arizona RP
2. Объяснять терминологию (DM, RK, PG, MG, NonRP и т.д.)
3. Помогать понять, какое наказание грозит за нарушение
4. Давать советы по игре и RP-ситуациям
5. Помогать с жалобами и апелляциями

ВАЖНЫЕ ПРАВИЛА ДЛЯ ТЕБЯ:
- Всегда отвечай на русском языке
- Используй терминологию Arizona RP
- Ссылайся на конкретные правила когда возможно
- Будь дружелюбным но профессиональным
- Если не уверен в правиле — скажи об этом
- НЕ придумывай правила которых нет

БАЗА ПРАВИЛ КОТОРУЮ ТЫ ЗНАЕШЬ:
{rules_context}

Отвечай кратко и по делу. Используй эмодзи для наглядности."""

# Хранилище сессий Octave
ARIZONA_AI_SESSIONS = {}


@bot.group(name='arizona', aliases=['az', 'ари', 'аризона'], invoke_without_command=True)
async def arizona(ctx):
    """🎮 Arizona RP Assistant - главное меню"""
    view = ui.ArizonaMainMenu(ctx)
    embed = ui.arizona_main_menu(ctx)
    await ctx.send(embed=embed, view=view)


@arizona.command(name='rules', aliases=['правила', 'rule', 'р'])
async def arizona_rules_cmd(ctx, *, query: str = None):
    """Поиск по правилам Arizona RP"""
    if not query:
        # Показать список всех разделов
        sections = arizona_rules.get_all_rules_list()
        embed = ui.create_base_embed(
            title="📋 Правила Arizona RP",
            description=sections + "\n\n💡 Используйте `!arizona rules <запрос>` для поиска",
            color=ui.COLOR_BLURPLE,
            ctx=ctx
        )
        await ctx.send(embed=embed)
        return
    
    # Поиск по правилам
    result = arizona_rules.search_rules(query)
    
    if result:
        # Обрезаем если слишком длинно
        if len(result) > 4000:
            result = result[:4000] + "\n\n*...результат обрезан*"
        
        embed = ui.create_base_embed(
            title=f"📖 Правила: {query}",
            description=result,
            color=ui.COLOR_GREEN,
            ctx=ctx
        )
    else:
        embed = ui.create_base_embed(
            title="🔍 Ничего не найдено",
            description=f"По запросу `{query}` правила не найдены.\n\n💡 Попробуйте другие ключевые слова:\n`dm`, `rk`, `pg`, `капт`, `полиция`, `читы`, `жалоба`",
            color=ui.COLOR_YELLOW,
            ctx=ctx
        )
    
    await ctx.send(embed=embed)


@arizona.command(name='ask', aliases=['вопрос', 'спросить', 'q'])
async def arizona_ask(ctx, *, question: str):
    """Задать вопрос AI-ассистенту Arizona RP"""
    if not AI_MODEL:
        await ctx.send(embed=ui.error("❌ AI не настроен! Добавьте GEMINI_API_KEY в .env", ctx))
        return
    
    user_id = str(ctx.author.id)
    
    async with ctx.typing():
        try:
            # Сначала ищем в базе правил
            rules_context = arizona_rules.search_rules(question)
            if not rules_context:
                # Берём общий контекст
                rules_context = "Используй свои знания о правилах Arizona RP"
            
            # Создаём prompt с контекстом правил
            full_prompt = ARIZONA_AI_SYSTEM_PROMPT.format(rules_context=rules_context[:3000])
            full_prompt += f"\n\nВОПРОС ИГРОКА: {question}\n\nОТВЕТ:"
            
            response = AI_MODEL.generate_content(full_prompt)
            answer = response.text
            
            if len(answer) > 4000:
                answer = answer[:4000] + "\n\n*...ответ обрезан*"
            
            embed = ui.create_base_embed(
                title="🎮 Arizona RP Assistant",
                description=answer,
                color=0xFF6B35,  # Оранжевый Arizona
                ctx=ctx
            )
            embed.add_field(name="❓ Ваш вопрос", value=f"```{question[:200]}```", inline=False)
            embed.set_footer(text="Octave • Ответ основан на правилах сервера")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(embed=ui.error(f"Ошибка AI: {str(e)[:200]}", ctx))


@arizona.command(name='chat', aliases=['чат', 'диалог'])
async def arizona_chat(ctx, *, message: str):
    """Чат с Octave с памятью диалога"""
    if not AI_MODEL:
        await ctx.send(embed=ui.error("❌ AI не настроен!", ctx))
        return
    
    user_id = str(ctx.author.id)
    
    # Создаём или получаем сессию
    if user_id not in ARIZONA_AI_SESSIONS:
        # Создаём чат с системным промптом
        rules_summary = "\n".join([f"• {r['title']}" for r in arizona_rules.ARIZONA_RULES.values()])
        system_prompt = ARIZONA_AI_SYSTEM_PROMPT.format(rules_context=rules_summary)
        
        ARIZONA_AI_SESSIONS[user_id] = AI_MODEL.start_chat(history=[
            {"role": "user", "parts": [system_prompt]},
            {"role": "model", "parts": ["Понял! Я готов помогать игрокам Arizona RP. Задавайте вопросы по правилам, терминологии или игровым ситуациям. 🎮"]}
        ])
    
    chat = ARIZONA_AI_SESSIONS[user_id]
    
    async with ctx.typing():
        try:
            # Добавляем контекст правил если вопрос про конкретное правило
            rules_context = arizona_rules.search_rules(message)
            if rules_context:
                enhanced_message = f"[Контекст из правил: {rules_context[:1000]}]\n\nВопрос игрока: {message}"
            else:
                enhanced_message = message
            
            response = chat.send_message(enhanced_message)
            answer = response.text
            
            if len(answer) > 4000:
                answer = answer[:4000] + "\n\n*...ответ обрезан*"
            
            msg_count = len(chat.history) // 2
            
            embed = ui.create_base_embed(
                title="💬 Octave Chat",
                description=answer,
                color=0xFF6B35,
                ctx=ctx
            )
            embed.set_footer(text=f"Сообщений: {msg_count} • !arizona reset для нового диалога")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(embed=ui.error(f"Ошибка: {str(e)[:200]}", ctx))


@arizona.command(name='reset', aliases=['сброс', 'новый'])
async def arizona_reset(ctx):
    """Сбросить диалог с Octave"""
    user_id = str(ctx.author.id)
    
    if user_id in ARIZONA_AI_SESSIONS:
        del ARIZONA_AI_SESSIONS[user_id]
        await ctx.send(embed=ui.success("🔄 Диалог с Octave сброшен! Начинаем с чистого листа.", ctx))
    else:
        await ctx.send(embed=ui.info("💬 Octave", "У вас нет активного диалога.", ctx))


@arizona.command(name='penalty', aliases=['наказание', 'штраф', 'срок'])
async def arizona_penalty(ctx, *, violation: str):
    """Калькулятор наказаний - узнай срок за нарушение"""
    # Поиск в правилах
    result = arizona_rules.search_rules(violation)
    
    if result:
        embed = ui.create_base_embed(
            title=f"⚖️ Наказание за: {violation}",
            description=result,
            color=ui.COLOR_RED,
            ctx=ctx
        )
        embed.set_footer(text="⚠️ Точное наказание определяет администратор")
    else:
        # Если не нашли — спрашиваем AI
        if AI_MODEL:
            async with ctx.typing():
                try:
                    prompt = f"""Ты эксперт по правилам Arizona RP. 
                    Игрок спрашивает какое наказание за: "{violation}"
                    
                    Ответь кратко:
                    1. Какое это нарушение (DM, RK, PG и т.д.)
                    2. Примерное наказание (деморган/варн/бан)
                    3. От чего зависит срок
                    
                    Если не уверен — скажи что нужно уточнить у администрации."""
                    
                    response = AI_MODEL.generate_content(prompt)
                    answer = response.text
                    
                    embed = ui.create_base_embed(
                        title=f"⚖️ Возможное наказание: {violation}",
                        description=answer,
                        color=ui.COLOR_YELLOW,
                        ctx=ctx
                    )
                    embed.set_footer(text="⚠️ AI оценка • Точное наказание определяет администратор")
                    
                except Exception as e:
                    embed = ui.error(f"Ошибка: {str(e)[:100]}", ctx)
        else:
            embed = ui.warning(f"Не найдено правило для `{violation}`.\n\nПопробуйте: `dm`, `rk`, `pg`, `читы`", ctx)
    
    await ctx.send(embed=embed)


@arizona.command(name='terms', aliases=['термины', 'терминология', 'словарь'])
async def arizona_terms(ctx):
    """Показать все термины Arizona RP"""
    terms = arizona_rules.ARIZONA_RULES.get("термины", {})
    
    embed = ui.create_base_embed(
        title="📚 Терминология Arizona RP",
        description=terms.get("content", "Термины не найдены"),
        color=ui.COLOR_BLURPLE,
        ctx=ctx
    )
    
    # Добавляем быстрые ссылки на популярные правила
    embed.add_field(
        name="🔗 Быстрый поиск",
        value="`!az rules dm` • `!az rules rk` • `!az rules pg` • `!az rules капт`",
        inline=False
    )
    
    await ctx.send(embed=embed)


@arizona.command(name='report', aliases=['жалоба', 'репорт'])
async def arizona_report(ctx):
    """Информация о подаче жалобы"""
    result = arizona_rules.search_rules("жалоба")
    
    embed = ui.create_base_embed(
        title="📝 Как подать жалобу на Arizona RP",
        description=result if result else "Информация не найдена",
        color=ui.COLOR_BLURPLE,
        ctx=ctx
    )
    
    embed.add_field(
        name="🔗 Ссылки",
        value="• [Форум Arizona](https://forum.arizona-rp.com/)\n• [Правила сервера](https://arizona-rp.com/rules)",
        inline=False
    )
    
    await ctx.send(embed=embed)


@arizona.command(name='help', aliases=['помощь', 'хелп'])
async def arizona_help(ctx):
    """Показать все команды Arizona Assistant"""
    embed = ui.arizona_help(ctx)
    await ctx.send(embed=embed)


# ============================================================
# 💬 РАСШИРЕННЫЕ СООБЩЕНИЯ
# ============================================================

@bot.group(name='msg', aliases=['message', 'сообщение'], invoke_without_command=True)
async def msg_group(ctx):
    """Расширенные функции сообщений"""
    embed = ui.create_base_embed(
        title="💬 Расширенные сообщения",
        description=(
            "**Доступные команды:**\n\n"
            "📩 `!msg reply <ID> <текст>` — Ответить на сообщение\n"
            "📌 `!msg pin <ID>` — Закрепить сообщение\n"
            "📌 `!msg unpin <ID>` — Открепить сообщение\n"
            "😀 `!msg react <ID> <эмодзи>` — Добавить реакцию\n"
            "✏️ `!msg edit <ID> <текст>` — Редактировать сообщение бота\n"
            "🗑️ `!msg delete <ID>` — Удалить сообщение\n\n"
            "**Как получить ID сообщения:**\n"
            "ПКМ на сообщение → Копировать ID\n"
            "(Нужен режим разработчика в настройках Discord)"
        ),
        color=ui.COLOR_BLURPLE,
        ctx=ctx
    )
    await ctx.send(embed=embed)


@msg_group.command(name='reply', aliases=['ответ', 'ответить'])
async def msg_reply(ctx, message_id: int, *, content: str):
    """Ответить на конкретное сообщение"""
    try:
        # Ищем сообщение в текущем канале
        target_message = await ctx.channel.fetch_message(message_id)
        
        embed = ui.create_base_embed(
            title="💬 Ответ",
            description=content,
            color=ui.COLOR_GREEN,
            ctx=ctx
        )
        
        # Отправляем с reply
        await target_message.reply(embed=embed, mention_author=False)
        
        # Удаляем команду пользователя
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass
            
    except discord.NotFound:
        await ctx.send(embed=ui.error("❌ Сообщение не найдено. Проверьте ID.", ctx))
    except discord.Forbidden:
        await ctx.send(embed=ui.error("❌ Нет прав для отправки ответа.", ctx))
    except Exception as e:
        await ctx.send(embed=ui.error(f"Ошибка: {str(e)[:100]}", ctx))


@msg_group.command(name='pin', aliases=['закрепить', 'пин'])
async def msg_pin(ctx, message_id: int):
    """Закрепить сообщение"""
    try:
        target_message = await ctx.channel.fetch_message(message_id)
        await target_message.pin()
        
        await ctx.send(embed=ui.success(f"📌 Сообщение закреплено!", ctx))
        
    except discord.NotFound:
        await ctx.send(embed=ui.error("❌ Сообщение не найдено.", ctx))
    except discord.Forbidden:
        await ctx.send(embed=ui.error("❌ Нет прав для закрепления сообщений.", ctx))
    except discord.HTTPException as e:
        if "Maximum number of pins" in str(e):
            await ctx.send(embed=ui.error("❌ Достигнут лимит закреплённых сообщений (50).", ctx))
        else:
            await ctx.send(embed=ui.error(f"Ошибка: {str(e)[:100]}", ctx))


@msg_group.command(name='unpin', aliases=['открепить', 'анпин'])
async def msg_unpin(ctx, message_id: int):
    """Открепить сообщение"""
    try:
        target_message = await ctx.channel.fetch_message(message_id)
        await target_message.unpin()
        
        await ctx.send(embed=ui.success(f"📌 Сообщение откреплено!", ctx))
        
    except discord.NotFound:
        await ctx.send(embed=ui.error("❌ Сообщение не найдено.", ctx))
    except discord.Forbidden:
        await ctx.send(embed=ui.error("❌ Нет прав для открепления сообщений.", ctx))


@msg_group.command(name='pins', aliases=['закреплённые', 'пины'])
async def msg_pins(ctx):
    """Показать все закреплённые сообщения"""
    try:
        pinned = await ctx.channel.pins()
        
        if not pinned:
            await ctx.send(embed=ui.info("📌 Закреплённые", "В этом канале нет закреплённых сообщений.", ctx))
            return
        
        embed = ui.create_base_embed(
            title=f"📌 Закреплённые сообщения ({len(pinned)})",
            color=ui.COLOR_BLURPLE,
            ctx=ctx
        )
        
        for i, msg in enumerate(pinned[:10], 1):
            content = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
            if not content:
                content = "*[Embed или медиа]*"
            embed.add_field(
                name=f"{i}. От {msg.author.display_name}",
                value=f"ID: `{msg.id}`\n{content}",
                inline=False
            )
        
        if len(pinned) > 10:
            embed.set_footer(text=f"Показано 10 из {len(pinned)} закреплённых")
        
        await ctx.send(embed=embed)
        
    except discord.Forbidden:
        await ctx.send(embed=ui.error("❌ Нет доступа к закреплённым сообщениям.", ctx))


@msg_group.command(name='react', aliases=['реакция', 'эмодзи'])
async def msg_react(ctx, message_id: int, emoji: str):
    """Добавить реакцию на сообщение"""
    try:
        target_message = await ctx.channel.fetch_message(message_id)
        await target_message.add_reaction(emoji)
        
        await ctx.send(embed=ui.success(f"✅ Реакция {emoji} добавлена!", ctx))
        
        # Удаляем команду
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass
            
    except discord.NotFound:
        await ctx.send(embed=ui.error("❌ Сообщение не найдено.", ctx))
    except discord.HTTPException:
        await ctx.send(embed=ui.error("❌ Неверный эмодзи или ошибка Discord.", ctx))
    except discord.Forbidden:
        await ctx.send(embed=ui.error("❌ Нет прав для добавления реакций.", ctx))


@msg_group.command(name='unreact', aliases=['удалитьреакцию'])
async def msg_unreact(ctx, message_id: int, emoji: str):
    """Удалить реакцию бота с сообщения"""
    try:
        target_message = await ctx.channel.fetch_message(message_id)
        await target_message.remove_reaction(emoji, ctx.bot.user)
        
        await ctx.send(embed=ui.success(f"✅ Реакция {emoji} удалена!", ctx))
        
    except discord.NotFound:
        await ctx.send(embed=ui.error("❌ Сообщение не найдено.", ctx))
    except discord.HTTPException:
        await ctx.send(embed=ui.error("❌ Реакция не найдена или ошибка.", ctx))


@msg_group.command(name='edit', aliases=['изменить', 'редактировать'])
async def msg_edit(ctx, message_id: int, *, new_content: str):
    """Редактировать сообщение бота"""
    try:
        target_message = await ctx.channel.fetch_message(message_id)
        
        # Проверяем что это сообщение бота
        if target_message.author != ctx.bot.user:
            await ctx.send(embed=ui.error("❌ Можно редактировать только сообщения бота!", ctx))
            return
        
        # Редактируем
        old_content = target_message.content or "*[Embed]*"
        await target_message.edit(content=new_content)
        
        embed = ui.create_base_embed(
            title="✏️ Сообщение отредактировано",
            color=ui.COLOR_GREEN,
            ctx=ctx
        )
        embed.add_field(name="Было", value=f"```{old_content[:200]}```", inline=False)
        embed.add_field(name="Стало", value=f"```{new_content[:200]}```", inline=False)
        
        await ctx.send(embed=embed)
        
    except discord.NotFound:
        await ctx.send(embed=ui.error("❌ Сообщение не найдено.", ctx))
    except discord.Forbidden:
        await ctx.send(embed=ui.error("❌ Нет прав для редактирования.", ctx))


@msg_group.command(name='delete', aliases=['удалить', 'удали'])
async def msg_delete(ctx, message_id: int):
    """Удалить сообщение"""
    try:
        target_message = await ctx.channel.fetch_message(message_id)
        
        # Проверяем права
        is_bot_message = target_message.author == ctx.bot.user
        has_manage_messages = ctx.author.guild_permissions.manage_messages if ctx.guild else False
        
        if not is_bot_message and not has_manage_messages:
            await ctx.send(embed=ui.error("❌ Можно удалять только сообщения бота или нужны права на управление сообщениями!", ctx))
            return
        
        await target_message.delete()
        
        confirm = await ctx.send(embed=ui.success("🗑️ Сообщение удалено!", ctx))
        
        # Автоудаление подтверждения через 5 секунд
        import asyncio
        await asyncio.sleep(5)
        try:
            await confirm.delete()
            await ctx.message.delete()
        except:
            pass
        
    except discord.NotFound:
        await ctx.send(embed=ui.error("❌ Сообщение не найдено.", ctx))
    except discord.Forbidden:
        await ctx.send(embed=ui.error("❌ Нет прав для удаления сообщений.", ctx))


@msg_group.command(name='quote', aliases=['цитата', 'цитировать'])
async def msg_quote(ctx, message_id: int, *, comment: str = None):
    """Процитировать сообщение"""
    try:
        target_message = await ctx.channel.fetch_message(message_id)
        
        content = target_message.content or "*[Embed или медиа]*"
        if len(content) > 500:
            content = content[:500] + "..."
        
        embed = ui.create_base_embed(
            title="💬 Цитата",
            description=f"> {content}",
            color=ui.COLOR_BLURPLE,
            ctx=ctx
        )
        embed.set_author(
            name=target_message.author.display_name,
            icon_url=target_message.author.avatar.url if target_message.author.avatar else None
        )
        embed.add_field(name="📅 Дата", value=target_message.created_at.strftime("%d.%m.%Y %H:%M"), inline=True)
        embed.add_field(name="🔗 Ссылка", value=f"[Перейти]({target_message.jump_url})", inline=True)
        
        if comment:
            embed.add_field(name="💭 Комментарий", value=comment, inline=False)
        
        await ctx.send(embed=embed)
        
    except discord.NotFound:
        await ctx.send(embed=ui.error("❌ Сообщение не найдено.", ctx))


@msg_group.command(name='info', aliases=['инфо'])
async def msg_info(ctx, message_id: int):
    """Показать информацию о сообщении"""
    try:
        target_message = await ctx.channel.fetch_message(message_id)
        
        embed = ui.create_base_embed(
            title="ℹ️ Информация о сообщении",
            color=ui.COLOR_BLURPLE,
            ctx=ctx
        )
        
        embed.add_field(name="👤 Автор", value=f"{target_message.author.mention}", inline=True)
        embed.add_field(name="🆔 ID", value=f"`{target_message.id}`", inline=True)
        embed.add_field(name="📅 Создано", value=target_message.created_at.strftime("%d.%m.%Y %H:%M:%S"), inline=True)
        
        if target_message.edited_at:
            embed.add_field(name="✏️ Изменено", value=target_message.edited_at.strftime("%d.%m.%Y %H:%M:%S"), inline=True)
        
        embed.add_field(name="📌 Закреплено", value="✅ Да" if target_message.pinned else "❌ Нет", inline=True)
        
        # Реакции
        if target_message.reactions:
            reactions_str = " ".join([f"{r.emoji} ({r.count})" for r in target_message.reactions])
            embed.add_field(name="😀 Реакции", value=reactions_str, inline=False)
        
        # Вложения
        if target_message.attachments:
            attachments_str = "\n".join([f"📎 {a.filename}" for a in target_message.attachments[:5]])
            embed.add_field(name="📁 Вложения", value=attachments_str, inline=False)
        
        embed.add_field(name="🔗 Ссылка", value=f"[Перейти к сообщению]({target_message.jump_url})", inline=False)
        
        await ctx.send(embed=embed)
        
    except discord.NotFound:
        await ctx.send(embed=ui.error("❌ Сообщение не найдено.", ctx))


if __name__ == "__main__":
    if not TOKEN:
        print("Error: DISCORD_TOKEN not found in .env")
    else:
        bot.run(TOKEN)

