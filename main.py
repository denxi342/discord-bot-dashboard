import discord
import os
from discord.ext import commands, tasks
import aiohttp
from dotenv import load_dotenv
import utils
import ui

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

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


if __name__ == "__main__":
    if not TOKEN:
        print("Error: DISCORD_TOKEN not found in .env")
    else:
        bot.run(TOKEN)
