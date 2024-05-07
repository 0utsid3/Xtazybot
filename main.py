import discord
from discord.ext import commands
from discord.ext.commands import has_permissions
from config import settings, muted_users
import asyncio
import datetime
import yt_dlp


# Определяем intents
intents = discord.Intents.all()

bot = commands.Bot(command_prefix=settings['prefix'], intents=intents)

# Создание объекта клиента Discord
client = discord.Client(intents=intents)


# Начало создания функционала бота
#
#
#
# Функция для записи чат-лога в файл (это можно изменить на отправку в канал Discord)
async def write_chat_log(message):
    with open('chat_log.txt', 'a', encoding='utf-8') as file:
        file.write(f'{message.author.name}: {message.content}\n')


# Обработчик события при получении сообщения
@client.event
async def on_message(message):
    if message.author == client.user:
        return  # Игнорируем сообщения, отправленные ботом самим себе

# Записываем сообщение в чат-лог
    await write_chat_log(message)

# Отправляем сообщение в указанный канал (закомментируйте этот блок, если не хотите отправлять в канал)
    log_channel = client.get_channel(settings['log_channel_id'])
    if log_channel:
        await log_channel.send(f'{message.author.name}: {message.content}')


# Приветствие новых участников
@bot.event
async def on_member_join(member):
    channel = discord.utils.get(member.guild.text_channels, name="welcome")  # Приветственное сообщение в канал Main
    if channel:
        await channel.send(f"Добро пожаловать на сервер, {member.mention}!")


# Прощание со старыми участниками
@bot.event
async def on_member_remove(member):
    channel = discord.utils.get(member.guild.text_channels, name="welcome")  # Прощальное сообщение в канал Main
    if channel:
        await channel.send(f"{member.mention} покинул нас...")


# Команда для бана
@bot.command()
@has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason=None):
    await ctx.message.delete()
    await member.ban(reason=reason)
    await ctx.send(f'{member.mention} был забанен по причине: {reason}')


@bot.command()
@commands.has_permissions(ban_members=True)
async def unban(ctx, member: discord.User, *, reason=None):
    await ctx.message.delete()
    banned_users = ctx.guild.bans()
    banned_users_list = []
    async for ban_entry in banned_users:
        banned_users_list.append(ban_entry.user)
    for banned_user in banned_users_list:
        if banned_user == member:
            await ctx.guild.unban(banned_user, reason=reason)
            await ctx.send(f'{banned_user.mention} был разблокирован.')
            return
    await ctx.send(f'Пользователь {member.mention} не был заблокирован на этом сервере.')

# Команда для мута пользователя в текстовых и голосовых каналах
@bot.command()
async def mute(ctx, member: discord.Member, duration: int, *, reason):
    # Удаляем сообщение с командой
    await ctx.message.delete()
    # Проверяем, имеет ли пользователь разрешения на управление членами сервера
    if ctx.author.guild_permissions.manage_roles:
        # Проверяем, находится ли пользователь в голосовом канале
        if member.voice and member.voice.channel:
            # Замутить микрофон пользователя
            await member.edit(mute=True)

        # Получаем роль для мута в текстовом чате
        muted_role = discord.utils.get(ctx.guild.roles, name="Muted")

        # Проверяем, существует ли роль для мута
        if not muted_role:
            # Создаем роль для мута
            muted_role = await ctx.guild.create_role(name="Muted", reason="Роль для замученных пользователей")

            # Настроим разрешения для роли в текстовых каналах
            for channel in ctx.guild.text_channels:
                await channel.set_permissions(muted_role, send_messages=False)

        # Выдаем роль для мута пользователю
        await member.add_roles(muted_role)
        # Сохраняем информацию о муте пользователя
        muted_users[member.id] = (datetime.datetime.now(), datetime.timedelta(minutes=duration))

        await ctx.send(f"{member.display_name} был замучен по причине: {reason} на {duration} минут(у)")
        await asyncio.sleep(duration * 60)  # Время мута
        await member.remove_roles(muted_role)
        await member.edit(mute=False)
        await ctx.send(f"{member.display_name} был размучен.")
    else:
        await ctx.send("У вас недостаточно прав для выполнения этой команды.")


# Команда для размута пользователя в текстовых и голосовых каналах
@bot.command()
async def unmute(ctx, member: discord.Member):
    # Удаляем сообщение с командой
    await ctx.message.delete()
    # Проверяем, имеет ли пользователь разрешения на управление членами сервера
    if ctx.author.guild_permissions.manage_roles:
        # Проверяем, находится ли пользователь в голосовом канале и замучен ли он
        if member.voice and member.voice.channel and member.voice.mute:
            # Размутить микрофон пользователя
            await member.edit(mute=False)

        # Получаем роль для мута в текстовом чате
        muted_role = discord.utils.get(ctx.guild.roles, name="Muted")

        # Проверяем, существует ли роль для мута и находится ли пользователь под мутом
        if muted_role and muted_role in member.roles:
            # Снимаем роль для мута у пользователя
            await member.remove_roles(muted_role)
        else:
            await ctx.send(f"{member.display_name} не был замучен.")
    else:
        await ctx.send("У вас недостаточно прав для выполнения этой команды.")


# Команда для очистки сообщений
@bot.command(name='clear', help='Удалить сообщения из чата')
async def clear(ctx, amount: int):
    await ctx.channel.purge(limit=amount)


# Команда для проверки времени до конца мута
@bot.command()
async def check_mt(ctx, member: discord.Member):
    if member.id in muted_users:
        start_time, duration = muted_users[member.id]
        remaining_time = start_time + duration - datetime.datetime.now()
        if remaining_time.total_seconds() > 0:
            hours, remainder = divmod(int(remaining_time.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            await ctx.send(f"До конца мута {member.display_name} осталось {hours} часов, {minutes} минут и {seconds} секунд .")
        else:
            await ctx.send(f"Мут для {member.display_name} завершен.")
            del muted_users[member.id]
    else:
        await ctx.send(f"{member.display_name} не замучен.")


# Обработчик события на получение сообщений в каналах
# Тут должен был быть написан код для использования ИИ от OpenAI
# Но мне сказали его удалить


# Youtube
# Функция для воспроизведения аудио из YouTube
async def play_youtube_audio(ctx, url):
    # Создаем объект yt-dlp
    ydl = yt_dlp.YoutubeDL()

    # Получаем информацию о видео с YouTube
    info = ydl.extract_info(url, download=False)

    # Извлекаем ссылку на аудио из информации о видео
    audio_url = info['formats'][0]['url']

    # Подключаемся к голосовому каналу пользователя
    voice_channel = ctx.author.voice.channel
    voice_client = await voice_channel.connect()

    # Воспроизводим аудио из YouTube в голосовом канале
    voice_client.play(discord.FFmpegPCMAudio(audio_url), after=lambda e: print('done', e))

    # Ожидаем завершения воспроизведения аудио и отключаемся от голосового канала
    while voice_client.is_playing():
        await asyncio.sleep(1)
    await voice_client.disconnect()

# Команда для воспроизведения аудио из YouTube
@bot.command()
async def play(ctx, url):
    await play_youtube_audio(ctx, url)

# Запускаем бота с нашим токеном
bot.run(settings['token'])
