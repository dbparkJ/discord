import discord
from discord.ext import commands
from playwright.async_api import async_playwright

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

bot.playwright = None
bot.browser = None

@bot.event
async def on_ready():
    bot.playwright = await async_playwright().start()
    bot.browser = await bot.playwright.chromium.launch(headless=True)
    print(f"Logged in as {bot.user}. Browser launched.")

async def get_item_detail_screenshot(item_name: str, ctx):
    context = await bot.browser.new_context()
    page = await context.new_page()

    # 1) 검색
    await page.goto("https://mapleland.gg/")
    await page.fill('input[placeholder="검색어를 입력하세요"]', item_name)

    # 2) 검색된 span 클릭
    await page.wait_for_selector(
        f'span.text-sm.truncate:has-text("{item_name}")',
        timeout=10000
    )
    await page.click(f'span.text-sm.truncate:has-text("{item_name}")')

    # 3) (디버깅용 스크린샷 제거) → 바로 로딩 대기
    await page.wait_for_timeout(500)

    # 4) 최종 스크린샷만 찍어서 전송
    final_path = f"item_{item_name}.png"
    await page.screenshot(path=final_path, full_page=True)
    await ctx.send(file=discord.File(final_path))

    await context.close()

@bot.command(name="가격검색")
async def 가격검색(ctx, *, item_name: str):
    await ctx.send(f"🔍 `{item_name}` 상세 페이지를 가져옵니다...")
    try:
        await get_item_detail_screenshot(item_name, ctx)
    except Exception as e:
        await ctx.send(f"❌ 오류 발생: `{e}`")

if __name__ == "__main__":
    #bot.run("YOUR_DISCORD_BOT_TOKEN")



    bot.run("MTM3Mzg5NjAyNzExNDk2NzEzMQ.G5isLt.8mM4d0r38SnKgT3umu0N5DYB0_msW7hc--rNHk")