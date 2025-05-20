import discord
from discord.ext import commands
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import io
import asyncio

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# 전역에 Playwright, Browser, Context, Page, 그리고 검색 큐/워커 저장
bot.playwright = None
bot.browser = None
bot.context = None
bot.page = None
bot.search_queue = None
bot.worker = None

@bot.event
async def on_ready():
    # Playwright 시작 & 브라우저 기동
    bot.playwright = await async_playwright().start()
    bot.browser   = await bot.playwright.chromium.launch(headless=True)
    # 캐시 활용을 위해 한 번만 컨텍스트/페이지 생성
    bot.context   = await bot.browser.new_context(viewport={"width":1280, "height":800})
    bot.page      = await bot.context.new_page()
    bot.page.set_default_navigation_timeout(2000)

    # 검색 요청 큐 및 워커 생성
    bot.search_queue = asyncio.Queue()
    bot.worker = asyncio.create_task(_process_queue())

    print(f"Logged in as {bot.user}. Browser & queue worker ready.")

async def _process_queue():
    """큐에 들어온 요청을 순차 처리합니다."""
    while True:
        ctx, item_name = await bot.search_queue.get()
        try:
            await _capture_item_page(item_name, ctx)
        except PlaywrightTimeoutError as e:
            await ctx.send(f"❌ 타임아웃: `{e}`")
        except Exception as e:
            await ctx.send(f"❌ 오류 발생: `{e}`")
        finally:
            bot.search_queue.task_done()

async def _capture_item_page(item_name: str, ctx):
    """아이템 상세 페이지로 이동해 1초 뒤 전체 스크린샷을 찍고 전송합니다."""
    page = bot.page

    # 1) 메인 페이지로 이동 & 0.2초 대기
    await page.goto("https://mapleland.gg/", wait_until="domcontentloaded")
    await page.wait_for_timeout(200)

    # 2) 검색어 입력 & 0.2초 대기
    await page.fill('input[placeholder="검색어를 입력하세요"]', item_name)
    await page.wait_for_timeout(200)

    # 3) 검색 결과 span 최대 1초 대기 후 클릭
    await page.wait_for_selector(
        f'span.text-sm.truncate:has-text("{item_name}")',
        timeout=1000
    )
    await page.click(f'span.text-sm.truncate:has-text("{item_name}")')

    # 4) 상세 페이지 로드 준비 1초 대기
    await page.wait_for_timeout(1000)

    # 5) 전체 페이지(full_page) 스크린샷 획득
    img_bytes = await page.screenshot(full_page=True)

    # 6) “[아이템] 가격입니다” 텍스트와 함께 스크린샷 전송
    await ctx.send(f"{item_name} 가격입니다")
    discord_file = discord.File(io.BytesIO(img_bytes), filename=f"{item_name}.png")
    await ctx.send(file=discord_file)

@bot.command(name="가격검색")
async def 가격검색(ctx, *, item_name: str):
    # 큐에 검색 요청 추가 & 사용자에게 알림
    await ctx.send("✅ 검색 요청이 추가되었습니다. 순서대로 처리됩니다.")
    await bot.search_queue.put((ctx, item_name))

if __name__ == "__main__":
    #bot.run("YOUR_DISCORD_BOT_TOKEN")
    bot.run("MTM3Mzg5NjAyNzExNDk2NzEzMQ.G5isLt.8mM4d0r38SnKgT3umu0N5DYB0_msW7hc--rNHk")
