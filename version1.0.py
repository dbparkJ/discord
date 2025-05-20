import discord
from discord.ext import commands
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import asyncio
import io

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# 전역 저장소
bot.playwright      = None
bot.browser         = None
bot.price_context   = None
bot.price_page      = None
bot.search_queue    = None
bot.worker          = None

@bot.event
async def on_ready():
    # Playwright 시작 & 브라우저 기동
    bot.playwright    = await async_playwright().start()
    bot.browser       = await bot.playwright.chromium.launch(headless=True)
    # '가격검색' 전용 컨텍스트/페이지 (캐시 활용)
    bot.price_context = await bot.browser.new_context(viewport={"width":1280, "height":800})
    bot.price_page    = await bot.price_context.new_page()
    bot.price_page.set_default_navigation_timeout(2000)
    # 검색 요청 큐 및 워커 생성
    bot.search_queue  = asyncio.Queue()
    bot.worker        = asyncio.create_task(_process_queue())
    print(f"Logged in as {bot.user}. Ready to handle both searches.")

async def _process_queue():
    """큐에 들어온 요청을 순차 처리합니다."""
    while True:
        ctx, kind, item_name = await bot.search_queue.get()

        if kind == 'price':
            # mapleland.gg 가격 검색
            await ctx.send(f"🔍 `{item_name}` 가격 검색을 시작합니다...")
            try:
                page = bot.price_page
                # 1) 메인 페이지 이동 & 0.2초 대기
                await page.goto("https://mapleland.gg/", wait_until="domcontentloaded")
                await page.wait_for_timeout(200)
                # 2) 검색어 입력 & 0.2초 대기
                await page.fill('input[placeholder="검색어를 입력하세요"]', item_name)
                await page.wait_for_timeout(200)
                # 3) 드롭다운 첫 결과 클릭 (최대1초)
                await page.wait_for_selector(
                    f'span.text-sm.truncate:has-text("{item_name}")',
                    timeout=1000
                )
                await page.click(f'span.text-sm.truncate:has-text("{item_name}")')
                # 4) 상세페이지 로딩 준비 1초 대기
                await page.wait_for_timeout(1000)
                # 5) 전체 페이지(full) 스크린샷
                img_bytes = await page.screenshot(full_page=True)
                # 6) 전송
                await ctx.send(f"💰 **{item_name}** 가격입니다")
                await ctx.send(file=discord.File(io.BytesIO(img_bytes), filename=f"{item_name}.png"))
            except PlaywrightTimeoutError:
                await ctx.send(f"❌ `{item_name}` 가격 검색 중 타임아웃이 발생했습니다.")
            except Exception as e:
                await ctx.send(f"❌ 가격 검색 오류: `{e}`")

        elif kind == 'item':
            # mapledb.kr 아이템(장비) 상세 정보 검색
            await ctx.send(f"🔍 `{item_name}` 장비 검색을 시작합니다...")
            try:
                suggestion, details = await _search_mapledb_item(item_name)
                # 입력어와 실제 선택된 이름이 다르면 안내
                if suggestion.lower() != item_name.lower():
                    await ctx.send(
                        f"⚠️ 입력하신 **{item_name}** 과 일치하는 아이템이 없어\n"
                        f"   👉 **{suggestion}**(으)로 대신 검색합니다."
                    )
                # 결과 메시지 구성
                lines = [f"📦 **{suggestion}** 정보입니다:"]
                for k, v in details.items():
                    lines.append(f"• **{k}**: {v}")
                await ctx.send("\n".join(lines))
            except PlaywrightTimeoutError:
                await ctx.send(f"❌ `{item_name}` 장비 검색 중 타임아웃이 발생했습니다.")
            except Exception as e:
                await ctx.send(f"❌ 장비 검색 오류: `{e}`")

        bot.search_queue.task_done()

async def _search_mapledb_item(item_name: str):
    """
    mapledb.kr 에서 장비(아이템) 검색 후:
      1) 드롭다운 첫 결과 클릭
      2) '세부' 헤더 대기
      3) 세부 박스에서 key/value 추출
    반환: (chosen_name, details_dict)
    """
    context = await bot.browser.new_context()
    page    = await context.new_page()
    try:
        # 1) 메인 페이지 이동
        await page.goto('https://mapledb.kr/#google_vignette', wait_until='domcontentloaded')
        # 2) 검색어 입력
        await page.fill('#search_input', item_name)
        # 3) 드롭다운 첫 결과 대기(최대2초) & 클릭
        await page.wait_for_selector(
            '#search_output_item a.search-output-content-data',
            timeout=2000
        )
        first = page.locator('#search_output_item a.search-output-content-data').first
        suggestion = await first.locator('span.search-output-content-data-name').inner_text()
        await first.click()
        # 4) '세부' 헤더 대기(최대3초)
        await page.wait_for_selector(
            'h3.search-page-info-content-box-title:has-text("세부")',
            timeout=3000
        )
        # 5) 디테일 박스에서 모든 key/value 추출
        details = {}
        elems = await page.locator('div.search-page-info-content-box-detail').all()
        for el in elems:
            key = await el.locator('h4').inner_text()
            val = await el.locator('span').inner_text()
            details[key] = val
    finally:
        await context.close()

    return suggestion, details

@bot.command(name="가격")
async def 가격검색(ctx, *, item_name: str):
    """mapleland.gg에서 가격 검색"""
    await ctx.send("✅ 가격 검색 요청이 추가되었습니다. 순서대로 처리됩니다.")
    await bot.search_queue.put((ctx, 'price', item_name))

@bot.command(name="장비")
async def 장비(ctx, *, item_name: str):
    """mapledb.kr에서 장비(아이템) 상세 정보 검색"""
    await ctx.send("✅ 장비 검색 요청이 추가되었습니다. 순서대로 처리됩니다.")
    await bot.search_queue.put((ctx, 'item', item_name))

if __name__ == "__main__":
    bot.run("MTM3Mzg5NjAyNzExNDk2NzEzMQ.G5isLt.8mM4d0r38SnKgT3umu0N5DYB0_msW7hc--rNHk")

