import os
import re
import time
import imaplib
import email
import random
import logging
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def human_delay(a=1.0, b=2.5):
    time.sleep(random.uniform(a, b))


def human_type(el, text):
    el.clear()
    for ch in text:
        el.send_keys(ch)
        time.sleep(random.uniform(0.06, 0.15))


def setup_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1366,768")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--lang=en-IN")
    opts.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    opts.add_experimental_option('useAutomationExtension', False)
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    svc = Service('/usr/bin/chromedriver')
    driver = webdriver.Chrome(service=svc, options=opts)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": """
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins',   { get: () => [1,2,3] });
        Object.defineProperty(navigator, 'languages', { get: () => ['en-IN','en'] });
        window.chrome = { runtime: {} };
    """})
    return driver


# ── GMAIL OTP — SIRF FRESH EMAIL ───────────────────────────────────────────────

def mark_all_naukri_emails_read(gmail_user, gmail_app_password):
    """
    Login se PEHLE saari purani Naukri emails ko SEEN mark karo.
    Isse naya OTP aane pe confusion nahi hoga.
    """
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        mail.login(gmail_user, gmail_app_password)
        mail.select("inbox")
        _, ids = mail.search(None, '(FROM "naukri" UNSEEN)')
        if ids[0]:
            for mid in ids[0].split():
                mail.store(mid, '+FLAGS', '\\Seen')
            logger.info(f"Purani {len(ids[0].split())} Naukri emails SEEN mark ki gayi")
        else:
            logger.info("Koi purani unread Naukri email nahi thi")
        mail.logout()
    except Exception as e:
        logger.warning(f"Mark-read error (ignore kar sakte hain): {e}")


def get_fresh_otp_from_gmail(gmail_user, gmail_app_password, login_time, wait_seconds=90):
    """
    Sirf login ke BAAD aayi email se OTP lo.
    login_time: datetime (UTC) — login button click ka waqt
    """
    logger.info(f"📧 Gmail mein fresh OTP dhundh raha hoon (login time: {login_time.strftime('%H:%M:%S')} UTC)...")

    start = time.time()
    # 2 minute ki window — naukri OTP usually 10 sec mein aata hai
    min_email_time = login_time - timedelta(seconds=30)  # 30 sec buffer

    while time.time() - start < wait_seconds:
        try:
            mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
            mail.login(gmail_user, gmail_app_password)
            mail.select("inbox")

            # Sirf UNSEEN Naukri emails
            _, ids = mail.search(None, '(FROM "naukri" UNSEEN)')

            if ids[0]:
                # Sab emails check karo — sabse naya lo
                all_ids = ids[0].split()
                logger.info(f"Unread Naukri emails: {len(all_ids)}")

                best_otp = None
                best_time = None

                for mid in all_ids:
                    _, data = mail.fetch(mid, "(RFC822)")
                    for part in data:
                        if not isinstance(part, tuple):
                            continue
                        msg = email.message_from_bytes(part[1])

                        # Email time parse karo
                        date_str = msg.get("Date", "")
                        try:
                            email_time = parsedate_to_datetime(date_str)
                            # UTC mein convert karo
                            if email_time.tzinfo is None:
                                email_time = email_time.replace(tzinfo=timezone.utc)
                            else:
                                email_time = email_time.astimezone(timezone.utc)
                        except Exception:
                            email_time = datetime.now(timezone.utc)

                        subject = msg.get("Subject", "")
                        logger.info(f"Email time: {email_time.strftime('%H:%M:%S')} UTC | Subject: {subject}")

                        # Sirf login ke baad wala email
                        if email_time < min_email_time:
                            logger.info(f"  ⏭️ Purana email skip (login se pehle ka) — time: {email_time}")
                            # Purana email SEEN mark karo
                            mail.store(mid, '+FLAGS', '\\Seen')
                            continue

                        # Body se OTP nikalo
                        body = ""
                        if msg.is_multipart():
                            for p in msg.walk():
                                if p.get_content_type() in ("text/plain", "text/html"):
                                    body += p.get_payload(decode=True).decode("utf-8", errors="ignore")
                        else:
                            body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")

                        for pattern in [r'\b(\d{6})\b', r'\b(\d{4})\b',
                                        r'OTP[:\s]+(\d+)', r'code[:\s]+(\d+)']:
                            m = re.search(pattern, body, re.IGNORECASE)
                            if m:
                                otp = m.group(1)
                                # Sabse naya OTP lo
                                if best_time is None or email_time > best_time:
                                    best_otp = otp
                                    best_time = email_time
                                    logger.info(f"  ✅ Fresh OTP mila: {otp} (time: {email_time.strftime('%H:%M:%S')} UTC)")
                                break

                mail.logout()

                if best_otp:
                    return best_otp
            else:
                mail.logout()

        except Exception as e:
            logger.warning(f"Gmail check error: {e}")

        elapsed = int(time.time() - start)
        logger.info(f"OTP nahi mila — 8s baad retry ({elapsed}s elapsed)...")
        time.sleep(8)

    logger.error(f"❌ {wait_seconds}s mein fresh OTP nahi mila!")
    return None


# ── OTP FILL ────────────────────────────────────────────────────────────────────

def fill_otp(driver, otp):
    """6 alag boxes mein OTP fill karo — React-style event dispatch ke saath"""
    logger.info(f"OTP fill kar raha hoon: {otp}")
    time.sleep(1)

    # Method 1: CSS maxlength=1 + JS nativeInputValueSetter (React ke liye)
    try:
        boxes = driver.find_elements(By.CSS_SELECTOR, "input[maxlength='1']")
        if len(boxes) >= len(otp):
            logger.info(f"Method 1 (JS React): {len(boxes)} boxes mile")
            for i, digit in enumerate(otp):
                driver.execute_script("""
                    var nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                        window.HTMLInputElement.prototype, 'value').set;
                    nativeInputValueSetter.call(arguments[0], arguments[1]);
                    arguments[0].dispatchEvent(new Event('input',  { bubbles: true }));
                    arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
                    arguments[0].dispatchEvent(new KeyboardEvent('keyup', { bubbles: true }));
                """, boxes[i], digit)
                time.sleep(0.15)
            logger.info("✅ Method 1 complete!")
            return True
    except Exception as e:
        logger.info(f"Method 1 fail: {e}")

    # Method 2: Click + send_keys har box mein
    try:
        boxes = driver.find_elements(By.CSS_SELECTOR, "input[maxlength='1']")
        if len(boxes) >= len(otp):
            logger.info(f"Method 2 (click+type): {len(boxes)} boxes")
            for i, digit in enumerate(otp):
                b = boxes[i]
                driver.execute_script("arguments[0].focus();", b)
                b.click()
                time.sleep(0.1)
                b.clear()
                b.send_keys(digit)
                time.sleep(0.2)
            logger.info("✅ Method 2 complete!")
            return True
    except Exception as e:
        logger.info(f"Method 2 fail: {e}")

    # Method 3: Pehle box click, phir ActionChains se type
    try:
        boxes = driver.find_elements(By.CSS_SELECTOR, "input[maxlength='1']")
        if boxes:
            logger.info("Method 3 (ActionChains)")
            driver.execute_script("arguments[0].click();", boxes[0])
            time.sleep(0.3)
            ActionChains(driver).send_keys(otp).perform()
            logger.info("✅ Method 3 complete!")
            return True
    except Exception as e:
        logger.info(f"Method 3 fail: {e}")

    # Fallback: inputs debug log
    logger.error("❌ OTP fill nahi hua!")
    try:
        all_inputs = driver.find_elements(By.TAG_NAME, "input")
        logger.info(f"Page inputs ({len(all_inputs)}):")
        for inp in all_inputs:
            logger.info(f"  type={inp.get_attribute('type')} | "
                        f"maxlength={inp.get_attribute('maxlength')} | "
                        f"id={inp.get_attribute('id')} | "
                        f"class={inp.get_attribute('class')[:50] if inp.get_attribute('class') else ''}")
    except Exception:
        pass
    return False


# ── LOGIN ────────────────────────────────────────────────────────────────────────

def login_to_naukri(driver, email, password, gmail_user, gmail_app_password):
    # Login se PEHLE — purani Naukri emails SEEN mark karo
    mark_all_naukri_emails_read(gmail_user, gmail_app_password)

    driver.get("https://www.naukri.com/nlogin/login")
    human_delay(3, 5)
    logger.info(f"Page: {driver.title}")
    driver.save_screenshot("01_login_page.png")

    wait = WebDriverWait(driver, 20)

    # Email
    ef = wait.until(EC.element_to_be_clickable((By.ID, "usernameField")))
    ActionChains(driver).move_to_element(ef).pause(0.5).click().perform()
    human_delay(0.5, 1)
    human_type(ef, email)
    logger.info("✅ Email fill kiya")
    human_delay(0.8, 1.5)

    # Password
    pf = wait.until(EC.element_to_be_clickable((By.ID, "passwordField")))
    ActionChains(driver).move_to_element(pf).pause(0.5).click().perform()
    human_delay(0.5, 1)
    human_type(pf, password)
    logger.info("✅ Password fill kiya")
    human_delay(1, 2)

    # Login button click karne ka EXACT waqt record karo
    login_click_time = datetime.now(timezone.utc)
    logger.info(f"Login click time (UTC): {login_click_time.strftime('%H:%M:%S')}")

    btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@type='submit']")))
    ActionChains(driver).move_to_element(btn).pause(0.8).click().perform()
    logger.info("✅ Login click kiya")
    human_delay(4, 6)

    driver.save_screenshot("02_after_login.png")
    logger.info(f"URL: {driver.current_url}")

    # OTP page check
    if any(k in driver.page_source.lower() for k in ["otp", "one time", "verify your"]):
        logger.info("🔐 OTP page detect hua!")
        driver.save_screenshot("03_otp_page.png")

        # FRESH OTP lo (login ke baad aaya hua)
        otp = get_fresh_otp_from_gmail(gmail_user, gmail_app_password, login_click_time, wait_seconds=90)
        if not otp:
            logger.error("❌ Fresh OTP nahi mila!")
            return False

        logger.info(f"OTP use ho raha hai: {otp}")
        human_delay(1, 2)

        if not fill_otp(driver, otp):
            driver.save_screenshot("03b_fill_failed.png")
            return False

        human_delay(1, 2)
        driver.save_screenshot("04_otp_filled.png")

        # Verify button
        for sel in ["//button[contains(text(),'Verify')]",
                    "//button[contains(text(),'Submit')]",
                    "//button[@type='submit']"]:
            try:
                vb = WebDriverWait(driver, 8).until(EC.element_to_be_clickable((By.XPATH, sel)))
                vb.click()
                logger.info(f"✅ Verify click: {sel}")
                break
            except Exception:
                continue

        human_delay(4, 6)
        driver.save_screenshot("05_after_verify.png")
        logger.info(f"Verify baad URL: {driver.current_url}")

    # Success check
    url = driver.current_url
    if "nlogin" not in url and "login" not in url:
        logger.info(f"✅ Login successful! URL: {url}")
        return True
    elif any(s in url for s in ["mnjuser", "myapplication", "dashboard"]):
        logger.info("✅ Login successful!")
        return True
    else:
        logger.error(f"❌ Login fail. URL: {url}")
        return False


# ── RESUME UPDATE ────────────────────────────────────────────────────────────────

def update_resume(driver, resume_path):
    abs_path = os.path.abspath(resume_path)

    driver.get("https://www.naukri.com/mnjuser/profile")
    human_delay(4, 6)
    logger.info(f"Profile URL: {driver.current_url}")
    driver.save_screenshot("06_profile.png")

    file_inputs = driver.find_elements(By.XPATH, "//input[@type='file']")
    logger.info(f"File inputs: {len(file_inputs)}")

    if file_inputs:
        fi = file_inputs[0]
        driver.execute_script("""
            arguments[0].style.display = 'block';
            arguments[0].style.visibility = 'visible';
            arguments[0].style.opacity = '1';
        """, fi)
        fi.send_keys(abs_path)
        logger.info(f"✅ Resume upload: {abs_path}")
        human_delay(4, 6)
    else:
        for sel in ["//button[contains(text(),'Update Resume')]",
                    "//button[contains(text(),'Upload Resume')]",
                    "//a[contains(text(),'Update Resume')]"]:
            try:
                b = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, sel)))
                b.click()
                human_delay(2, 3)
                fi2 = driver.find_elements(By.XPATH, "//input[@type='file']")
                if fi2:
                    driver.execute_script("arguments[0].style.display='block';", fi2[0])
                    fi2[0].send_keys(abs_path)
                    human_delay(4, 6)
                    logger.info("✅ Resume upload complete!")
                    break
            except Exception:
                continue

    # Save
    for sel in ["//button[contains(text(),'Save')]", "//button[contains(text(),'Confirm')]",
                "//button[contains(text(),'Update')]", "//button[@type='submit']"]:
        try:
            sb = WebDriverWait(driver, 6).until(EC.element_to_be_clickable((By.XPATH, sel)))
            sb.click()
            logger.info(f"✅ Save click: {sel}")
            human_delay(2, 3)
            break
        except Exception:
            continue

    driver.save_screenshot("07_final.png")
    logger.info("✅ Resume update complete!")
    return True


# ── MAIN ─────────────────────────────────────────────────────────────────────────

def main():
    email       = os.environ.get("NAUKRI_EMAIL")
    password    = os.environ.get("NAUKRI_PASSWORD")
    gmail_user  = os.environ.get("GMAIL_USER", email)
    gmail_pass  = os.environ.get("GMAIL_APP_PASSWORD")
    resume_path = os.environ.get("RESUME_PATH", "resume/your_resume.pdf")

    if not email or not password:
        logger.error("❌ NAUKRI_EMAIL / NAUKRI_PASSWORD missing!")
        exit(1)
    if not gmail_pass:
        logger.error("❌ GMAIL_APP_PASSWORD missing!")
        exit(1)
    if not os.path.exists(resume_path):
        logger.error(f"❌ Resume nahi mila: {resume_path}")
        exit(1)

    masked = email[:3] + "***" + email[email.index('@'):]
    logger.info(f"Account: {masked} | Resume: {resume_path}")

    driver = None
    try:
        logger.info("🚀 Naukri Auto-Update shuru...")
        driver = setup_driver()

        if login_to_naukri(driver, email, password, gmail_user, gmail_pass):
            update_resume(driver, resume_path)
            logger.info("🎉 Resume successfully updated!")
        else:
            logger.error("❌ Login fail!")
            exit(1)

    except Exception as e:
        logger.error(f"❌ Fatal: {e}")
        if driver:
            driver.save_screenshot("fatal_error.png")
        exit(1)
    finally:
        if driver:
            driver.quit()
            logger.info("Browser band.")


if __name__ == "__main__":
    main()
