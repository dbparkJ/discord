import discord

intents = discord.Intents.all()
client = discord.Client(intents=intents)

notification = "아직 등록된 공지가 없습니다."

@client.event
async def on_message(message):
    global notification
    if message.author == client.user:
        return

    # !공지 출력
    if message.content == "!공지":
        await message.channel.send(notification)
        return

    # !공지업데이트 새 공지내용
    if message.content.startswith("!공지업데이트 "):
        new_content = message.content[len("!공지업데이트 "):].strip()  # 공백 제거
        if new_content:
            notification = new_content
            await message.channel.send(f"공지 업데이트 완료!\n새 공지: {notification}")
        else:
            await message.channel.send("업데이트할 공지 내용을 입력해 주세요.")
        return

client.run("MTM3Mzg5NjAyNzExNDk2NzEzMQ.G5isLt.8mM4d0r38SnKgT3umu0N5DYB0_msW7hc--rNHk")