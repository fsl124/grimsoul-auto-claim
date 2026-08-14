import os
import re
import json
import datetime
from playwright.sync_api import sync_playwright

ACCOUNT_ID = os.environ.get("GRIMSOUL_ACCOUNT_ID")
DAILY_URL = "https://grimsoul.com/zh/daily-rewards"
STORE_URL = "https://grimsoul.com/zh/store"

DAILY_TEXTS = ["领取奖励", "领取", "领奖", "Claim reward", "Claim"]
STORE_TEXTS = ["10塔勒", "塔勒", "免费硬币", "领取免费硬币", "领取免费", "免费", "Free coins", "Claim free", "Claim"]
SKIP_TEXTS = ["已领取", "已签到", "明日再来", "明天再来", "Claimed", "Come back tomorrow", "Already claimed"]
SUCCESS_TEXTS = ["恭喜", "获得", "成功", "领取成功", "奖励", "You got", "Received", "Success", "Congratulations"]
ALREADY_TEXTS = ["已领取", "已经领取", "已签到", "Already claimed", "Claimed", "Come back tomorrow"]

def log(msg):
    print(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}")

def handle_cookie_banner(page):
    dialog_selectors = [
        'div[class*="termly"]', 'div[class*="cookie"]', 'div[class*="consent"]',
        'div[id*="termly"]', 'div[id*="cookie"]', 'div[id*="consent"]',
        '[role="dialog"]', '.modal', '.popup', '.dialog'
    ]
    primary_buttons = ["Allow All", "允许所有", "全部允许", "Decline All", "拒绝所有", "全部拒绝"]
    secondary_buttons = ["Accept All", "Accept", "同意", "接受", "允许"]

    container = None
    for sel in dialog_selectors:
        try:
            loc = page.locator(sel).first
            if loc.is_visible():
                container = loc
                log(f"找到 Cookie 弹窗容器：{sel}")
                break
        except:
            continue

    if container:
        for text in primary_buttons:
            try:
                btn = container.locator(f'button:has-text("{text}")').first
                if btn.is_visible() and btn.is_enabled():
                    btn.click(timeout=2000)
                    log(f"在弹窗内点击按钮：{text}")
                    page.wait_for_timeout(1000)  # 缩短等待
                    if not container.is_visible():
                        log("Cookie 弹窗已关闭")
                        return True
            except:
                continue
        for text in secondary_buttons:
            try:
                btn = container.locator(f'button:has-text("{text}")').first
                if btn.is_visible() and btn.is_enabled():
                    btn.click(timeout=2000)
                    log(f"在弹窗内点击按钮：{text}")
                    page.wait_for_timeout(1000)
                    if not container.is_visible():
                        log("Cookie 弹窗已关闭")
                        return True
            except:
                continue

    for text in primary_buttons + secondary_buttons:
        try:
            btn = page.locator(f'button:has-text("{text}")').first
            if btn.is_visible() and btn.is_enabled():
                btn.click(timeout=2000)
                log(f"全局点击按钮：{text}")
                page.wait_for_timeout(1000)
                return True
        except:
            continue

    for text in primary_buttons:
        try:
            loc = page.get_by_text(text, exact=True).first
            if loc.is_visible() and loc.is_enabled():
                tag = loc.evaluate("el => el.tagName.toLowerCase()")
                if tag in ["button", "a", "div", "span"]:
                    loc.click(timeout=2000)
                    log(f"通过精确文本点击：{text}")
                    page.wait_for_timeout(1000)
                    return True
        except:
            pass
    return False

def has_countdown(page):
    try:
        result = page.evaluate("""
            () => {
                const regex = /^\\d{1,2}:\\d{2}:\\d{2}$/;
                const all = document.querySelectorAll('body *');
                for (const el of all) {
                    if (el instanceof HTMLElement) {
                        const style = window.getComputedStyle(el);
                        if (style.display !== 'none' && style.visibility !== 'hidden' && el.offsetWidth > 0) {
                            const text = el.innerText.trim();
                            if (text && regex.test(text)) return text;
                        }
                    }
                }
                return null;
            }
        """)
        if result:
            log(f"检测到倒计时文本：'{result}'")
            return True
        return False
    except Exception as e:
        log(f"倒计时检测出错：{e}")
        return False

def page_has_skip_text(page):
    try:
        body = page.inner_text("body").lower()
        for t in SKIP_TEXTS:
            if t.lower() in body:
                log(f"检测到跳过文本：'{t}'")
                return True
        return False
    except:
        return False

def get_visible_text(page, selector='body'):
    try:
        return page.inner_text(selector)
    except:
        return ""

def click_claim_button(page, texts):
    for text in texts:
        for selector in ["button", "a", "[role=button]", "div", "span"]:
            try:
                locs = page.locator(selector, has_text=text)
                count = locs.count()
                for i in range(count):
                    loc = locs.nth(i)
                    if loc.is_visible() and loc.is_enabled():
                        tag = loc.evaluate("el => el.tagName.toLowerCase()")
                        cls = loc.evaluate("el => el.className || ''")
                        text_content = (loc.inner_text() or '').strip()
                        if tag in ["button", "a"] or "btn" in cls.lower() or "claim" in cls.lower() or "button" in cls.lower():
                            loc.click(timeout=3000)
                            log(f"点击成功：{text}（标签 {tag}，class: {cls}）")
                            return True
                        elif "领取" in text_content or "claim" in text_content.lower():
                            loc.click(timeout=3000)
                            log(f"点击成功：{text}（标签 {tag}）")
                            return True
            except:
                continue
        try:
            loc = page.get_by_text(text, exact=False).first
            if loc.is_visible() and loc.is_enabled():
                loc.click(timeout=3000)
                log(f"点击成功（文本兜底）：{text}")
                return True
        except:
            pass
    return False

def wait_and_check_popup(page, timeout=8000):
    popup_selectors = ['.modal', '.popup', '.dialog', '[role="dialog"]', '.toast', '.notification',
                       'div[class*="modal"]', 'div[class*="popup"]', 'div[class*="dialog"]']
    try:
        page.wait_for_selector(popup_selectors[0], timeout=timeout)
    except:
        page.wait_for_timeout(timeout)
    visible_text = get_visible_text(page).lower()
    if any(t.lower() in visible_text for t in ALREADY_TEXTS):
        log("弹窗提示：已领取")
        return 'already'
    if any(t.lower() in visible_text for t in SUCCESS_TEXTS):
        log("弹窗提示：领取成功")
        return 'success'
    log("弹窗内容未知，可能已领取或领取成功")
    return 'unknown'

def login(page):
    page.goto("https://grimsoul.com/zh", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(2000)  # 原3000
    handle_cookie_banner(page)

    login_clicked = False
    for text in ["登录", "登入", "Login", "Sign in"]:
        try:
            loc = page.get_by_text(text, exact=False).first
            if loc.is_visible():
                loc.click(timeout=3000)
                log(f"点击登录按钮：{text}")
                login_clicked = True
                break
        except:
            continue
    if not login_clicked:
        for sel in ['button:has-text("登录")', 'a:has-text("登录")', '[data-testid="login"]', '.login-btn', '#loginBtn']:
            try:
                loc = page.locator(sel).first
                if loc.is_visible():
                    loc.click(timeout=3000)
                    log(f"点击登录按钮（选择器：{sel}）")
                    login_clicked = True
                    break
            except:
                continue
    if not login_clicked:
        log("警告：未找到登录按钮，请检查页面结构")
        return False

    page.wait_for_timeout(2000)  # 原3000

    input_found = False
    input_selectors = ['input[type="text"]', 'input[type="email"]', 'input:not([type="hidden"])',
                       'input[placeholder*="账号"]', 'input[placeholder*="ID"]',
                       'input[placeholder*="Account"]', 'input[placeholder*="id"]', 'input[placeholder*="账户"]']
    for sel in input_selectors:
        try:
            loc = page.locator(sel).first
            if loc.is_visible() and loc.is_enabled():
                loc.fill(ACCOUNT_ID)
                log(f"已填写账号 ID 到输入框（选择器：{sel}）")
                input_found = True
                break
        except:
            continue
    if not input_found:
        log("错误：未找到账号输入框")
        return False

    submit_clicked = False
    for text in ["确认", "提交", "进入", "登录", "OK", "Submit", "Confirm", "Enter"]:
        try:
            loc = page.get_by_text(text, exact=False).first
            if loc.is_visible() and loc.is_enabled():
                loc.click(timeout=3000)
                log(f"点击确认按钮：{text}")
                submit_clicked = True
                break
        except:
            continue
    if not submit_clicked:
        try:
            page.keyboard.press("Enter")
            log("已按回车键提交登录")
            submit_clicked = True
        except:
            pass
    if not submit_clicked:
        log("错误：未找到确认按钮")
        return False

    page.wait_for_timeout(3000)  # 原5000
    log("登录完成")
    return True

def main():
    if not ACCOUNT_ID:
        log("错误：未找到 GRIMSOUL_ACCOUNT_ID 环境变量")
        return

    log("===== 开始执行自动领取 =====")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale="zh-CN")
        context.add_init_script(
            "try { localStorage.setItem('TERMLY_COOKIE_CONSENT', '{\"essential\":true,\"functional\":true,\"performance\":true,\"advertising\":true}'); } catch(e) {}"
        )
        page = context.new_page()

        if not login(page):
            log("登录失败，脚本终止")
            browser.close()
            return

        log("访问每日奖励页面")
        page.goto(DAILY_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)  # 原5000
        handle_cookie_banner(page)

        try:
            body_preview = page.inner_text("body")[:200]
            log(f"页面文本预览：{body_preview}")
        except:
            pass

        has_cd = has_countdown(page)
        has_skip = page_has_skip_text(page)
        log(f"倒计时检测结果：{has_cd}，跳过文本检测结果：{has_skip}")
        if has_cd or has_skip:
            log("每日奖励：检测到倒计时或已领取文本，跳过")
        else:
            if click_claim_button(page, DAILY_TEXTS):
                log("每日奖励：已点击领取按钮，等待弹窗...")
                result = wait_and_check_popup(page)
                if result == 'success':
                    log("每日奖励：领取成功！")
                elif result == 'already':
                    log("每日奖励：今天已领取过，无需重复操作")
                else:
                    log("每日奖励：弹窗内容未知，请手动检查")
            else:
                log("每日奖励：未找到可点击的领取按钮")

        log("访问商店页面")
        page.goto(STORE_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)  # 原5000
        handle_cookie_banner(page)

        try:
            body_preview = page.inner_text("body")[:200]
            log(f"页面文本预览：{body_preview}")
        except:
            pass

        has_cd = has_countdown(page)
        has_skip = page_has_skip_text(page)
        log(f"倒计时检测结果：{has_cd}，跳过文本检测结果：{has_skip}")
        if has_cd or has_skip:
            log("商店：检测到倒计时或已领取文本，跳过")
        else:
            if click_claim_button(page, STORE_TEXTS):
                log("商店：已点击领取按钮，等待弹窗...")
                result = wait_and_check_popup(page)
                if result == 'success':
                    log("商店：免费硬币领取成功！")
                elif result == 'already':
                    log("商店：今天已领取过，无需重复操作")
                else:
                    log("商店：弹窗内容未知，请手动检查")
            else:
                log("商店：未找到可点击的领取按钮")

        try:
            page.screenshot(path="/tmp/grimsoul_result.png")
            log("已保存截图到 /tmp/grimsoul_result.png")
        except:
            pass

        browser.close()

    log("===== 任务结束 =====")

if __name__ == "__main__":
    main()
