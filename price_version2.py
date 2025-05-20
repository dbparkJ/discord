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
    # 네비게이션 최대 대기 시간을 2초로 단축
    bot.page.set_default_navigation_timeout(2000)

    # 검색 요청 큐 및 워커 생성
    bot.search_queue = asyncio.Queue()
    bot.worker       = asyncio.create_task(_process_queue())

    print(f"Logged in as {bot.user}. Browser & queue worker ready.")

async def _process_queue():
    """큐에 들어온 요청을 순차 처리합니다."""
    while True:
        ctx, item_name = await bot.search_queue.get()
        # 작업 시작 알림
        await ctx.send(f"🔍 `{item_name}` 검색을 시작합니다...")
        await _capture_item_page(item_name, ctx)
        bot.search_queue.task_done()

async def _capture_item_page(item_name: str, ctx):
    """아이템 검색 → 드롭다운 선택 → 상세페이지 스크린샷 → 전송"""
    page = bot.page

    try:
        # 1) 메인 페이지 이동 & 0.2초 대기
        await page.goto("https://mapleland.gg/", wait_until="domcontentloaded")
        await page.wait_for_timeout(200)

        # 2) 검색어 입력 & 0.2초 대기
        await page.fill('input[placeholder="검색어를 입력하세요"]', item_name)
        await page.wait_for_timeout(200)

        # 3) 드롭다운 항목 대기 (최대 1초) & 리스트 가져오기
        await page.wait_for_selector('span.text-sm.truncate', timeout=1000)
        suggestions = await page.eval_on_selector_all(
            'span.text-sm.truncate',
            'els => els.map(e => e.innerText.trim())'
        )

        if not suggestions:
            await ctx.send(f"❌ `{item_name}` 결과를 찾을 수 없습니다.")
            return

        # 4) 일치 항목이 없으면 첫 번째로 대체
        if item_name in suggestions:
            chosen = item_name
        else:
            chosen = suggestions[0]
            await ctx.send(
                f"⚠️ 입력하신 **{item_name}**과 일치하는 아이템이 없어\n"
                f"   👉 **{chosen}**으로 검색합니다"
            )

        # 5) 드롭다운 선택
        await page.click(f'span.text-sm.truncate:has-text("{chosen}")')

    except PlaywrightTimeoutError:
        await ctx.send("❌ 검색 과정에서 타임아웃이 발생했습니다.")
        return

    # 6) 상세 페이지 로드 준비 1초 대기
    await page.wait_for_timeout(1000)

    # 7) 전체 페이지 스크린샷 (full page)
    img_bytes = await page.screenshot(full_page=True)

    # 8) 가격 메시지 + 스크린샷 전송
    await ctx.send(f"💰 **{chosen}** 가격입니다")
    discord_file = discord.File(io.BytesIO(img_bytes), filename=f"{chosen}.png")
    await ctx.send(file=discord_file)

@bot.command(name="가격검색")
async def 가격검색(ctx, *, item_name: str):
    # 큐에 검색 요청 추가 & 사용자에게 알림
    await ctx.send("✅ 검색 요청이 추가되었습니다. 순서대로 처리됩니다.")
    await bot.search_queue.put((ctx, item_name))

if __name__ == "__main__":
    bot.run("MTM3Mzg5NjAyNzExNDk2NzEzMQ.G5isLt.8mM4d0r38SnKgT3umu0N5DYB0_msW7hc--rNHk")
