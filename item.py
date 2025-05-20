import discord
from discord.ext import commands
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import asyncio

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# 전역 변수
bot.playwright    = None
bot.browser       = None
bot.search_queue  = None
bot.worker        = None

@bot.event
async def on_ready():
    bot.playwright = await async_playwright().start()
    bot.browser    = await bot.playwright.chromium.launch(headless=True)
    bot.search_queue = asyncio.Queue()
    bot.worker       = asyncio.create_task(_process_queue())
    print(f"Logged in as {bot.user}. Ready.")

async def _process_queue():
    while True:
        ctx, raw_name = await bot.search_queue.get()
        item_name = raw_name.strip()
        await ctx.send(f"🔍 `{item_name}` 검색 시작…")
        try:
            suggestion, details = await _search_mapledb_item(item_name)
            # 이름 불일치 안내
            if suggestion.lower() != item_name.lower():
                await ctx.send(
                    f"⚠️ 입력하신 **{item_name}** 과 일치하는 아이템이 없어\n"
                    f"   👉 **{suggestion}**(으)로 대신 검색합니다."
                )
            # 결과 출력
            lines = [f"📦 **{suggestion}** 정보입니다:"]
            for k, v in details.items():
                lines.append(f"• **{k}**: {v}")
            await ctx.send("\n".join(lines))
        except PlaywrightTimeoutError:
            await ctx.send(f"❌ `{item_name}` 검색 실패 이름을 다시 확인해 주세요.")
        except Exception as e:
            await ctx.send(f"❌ 오류 발생: `{e}`")
        finally:
            bot.search_queue.task_done()

async def _search_mapledb_item(item_name: str):
    """
    MapleDB에서 아이템 검색 후:
     1) 드롭다운 첫 결과 클릭
     2) '세부' 헤더 대기
     3) 세부 디테일 긁어오기
    """
    context = await bot.browser.new_context()
    page    = await context.new_page()
    try:
        # 1) 검색창에 입력
        await page.goto('https://mapledb.kr/#google_vignette', wait_until='domcontentloaded')
        await page.fill('#search_input', item_name)
        # 2) 드롭다운 첫 결과 대기(최대2초) & 클릭
        await page.wait_for_selector('#search_output_item a.search-output-content-data', timeout=2000)
        first = page.locator('#search_output_item a.search-output-content-data').first
        suggestion = await first.locator('span.search-output-content-data-name').inner_text()
        await first.click()

        # 3) “세부” 헤더가 뜰 때까지 대기(최대3초)
        await page.wait_for_selector(
            'h3.search-page-info-content-box-title:has-text("세부")',
            timeout=3000
        )

        # 4) 실제 디테일 박스들이 있는 컨테이너 내부에서 긁어오기
        #    (클래스명이 변경되지 않는 한 이 셀렉터로 모두 잡힙니다)
        elems = await page.locator('div.search-page-info-content-box-detail').all()
        details = {}
        for el in elems:
            key = await el.locator('h4').inner_text()
            val = await el.locator('span').inner_text()
            details[key] = val

    finally:
        await context.close()

    return suggestion, details

@bot.command(name='장비')
async def 아이템(ctx, *, item_name: str):
    await ctx.send("✅ 검색 요청이 추가되었습니다. 순서대로 처리됩니다.")
    await bot.search_queue.put((ctx, item_name))

if __name__ == '__main__':
    bot.run("MTM3Mzg5NjAyNzExNDk2NzEzMQ.G5isLt.8mM4d0r38SnKgT3umu0N5DYB0_msW7hc--rNHk")

