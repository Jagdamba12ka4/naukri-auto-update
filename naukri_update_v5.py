import os
import re
import time
import imaplib
import email
import random
import logging
from datetime import datetime, timezone
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


# ── GMAIL OTP ──────────────────────────────────────────────────────────────────

def get_otp_from_gmail(gmail_user, gmail_app_password, wait_seconds=90):
    logger.info("📧 Gmail se OTP le raha hoon...")
    start = time.time()

    while time.time() - start < wait_seconds:
        try:
            mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
            mail.login(gmail_user, gmail_app_password)
            mail.select("inbox")

            _, ids = mail.search(None, '(FROM "naukri" UNSEEN)')
            if ids[0]:
                latest = ids[0].split()[-1]
                _, data = mail.fetch(latest, "(RFC822)")
                for part in data:
                    if isinstance(part, tuple):
                        msg = email.message_from_bytes(part[1])
                        logger.info(f"Email subject: {msg.get('Subject')}")
                        body = ""
                        if msg.is_multipart():
                            for p in msg.walk():
                                ct = p.get_content_type()
                                if ct in ("text/plain", "text/html"):
                                    body += p.get_payload(decode=True).decode("utf-8", errors="ignore")
                        else:
                            body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")

                        for pattern in [r'\b(\d{6})\b', r'\b(\d{4})\b',
                                        r'OTP[:\s]+(\d+)', r'code[:\s]+(\d+)']:
                            m = re.search(pattern, body, re.IGNORECASE)
                            if m:
                                otp = m.group(1)
                                logger.info(f"✅ OTP mila: {otp}")
                                mail.logout()
                                return otp
            mail.logout()
        except Exception as e:
            logger.warning(f"Gmail error: {e}")

        logger.info(f"OTP nahi mila abhi — 8s baad retry ({int(time.time()-start)}s)...")
        time.sleep(8)

    return None


# ── OTP FILL — 5 METHODS ───────────────────────────────────────────────────────

def fill_otp(driver, otp):
    """
    Naukri ke OTP boxes screenshot mein 6 separate boxes hain.
    5 alag methods try karte hain — jo pehle kaam kare.
    """
    wait = WebDriverWait(driver, 10)
    logger.info(f"OTP fill karne ki koshish: {otp}")

    # DEBUG: page ka OTP-related HTML log karo
    try:
        body_html = driver.find_element(By.TAG_NAME, "body").get_attribute("innerHTML")
        # OTP section dhundo
        otp_section_match = re.search(r'.{200}otp.{200}', body_html, re.IGNORECASE | re.DOTALL)
        if otp_section_match:
            logger.info(f"OTP HTML snippet: {otp_section_match.group()[:300]}")
    except Exception:
        pass

    # ── METHOD 1: maxlength=1 inputs (6 separate boxes) ──────────
    try:
        boxes = driver.find_elements(By.CSS_SELECTOR, "input[maxlength='1']")
        if len(boxes) >= len(otp):
            logger.info(f"Method 1: {len(boxes)} single-char boxes mile")
            for i, digit in enumerate(otp):
                b = boxes[i]
                driver.execute_script("arguments[0].focus();", b)
                b.click()
                b.send_keys(digit)
                time.sleep(0.25)
            logger.info("✅ Method 1 kaam kiya!")
            return True
    except Exception as e:
        logger.info(f"Method 1 fail: {e}")

    # ── METHOD 2: type="number" inputs ───────────────────────────
    try:
        boxes = driver.find_elements(By.CSS_SELECTOR, "input[type='number']")
        if len(boxes) >= len(otp):
            logger.info(f"Method 2: {len(boxes)} number inputs mile")
            for i, digit in enumerate(otp):
                driver.execute_script("arguments[0].focus();", boxes[i])
                boxes[i].click()
                boxes[i].send_keys(digit)
                time.sleep(0.25)
            logger.info("✅ Method 2 kaam kiya!")
            return True
    except Exception as e:
        logger.info(f"Method 2 fail: {e}")

    # ── METHOD 3: JavaScript se value set karo (React apps ke liye) ──
    try:
        boxes = driver.find_elements(By.CSS_SELECTOR, "input[maxlength='1']")
        if not boxes:
            boxes = driver.find_elements(By.CSS_SELECTOR, "input[type='number']")
        if len(boxes) >= len(otp):
            logger.info(f"Method 3: JS nativeInputValueSetter try kar raha hoon")
            for i, digit in enumerate(otp):
                driver.execute_script("""
                    var nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                        window.HTMLInputElement.prototype, 'value').set;
                    nativeInputValueSetter.call(arguments[0], arguments[1]);
                    arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
                    arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
                """, boxes[i], digit)
                time.sleep(0.2)
            logger.info("✅ Method 3 kaam kiya!")
            return True
    except Exception as e:
        logger.info(f"Method 3 fail: {e}")

    # ── METHOD 4: Pehle box pe click, phir poora OTP type ────────
    try:
        # Pehla OTP box dhundo
        first_box_selectors = [
            "input[maxlength='1']",
            "input[type='number']",
            "input[data-index='0']",
            ".otpContainer input",
            "[class*='otp'] input",
            "[id*='otp'] input",
            "[class*='OTP'] input",
        ]
        for sel in first_box_selectors:
            boxes = driver.find_elements(By.CSS_SELECTOR, sel)
            if boxes:
                logger.info(f"Method 4: selector '{sel}' se {len(boxes)} elements mile")
                driver.execute_script("arguments[0].click();", boxes[0])
                time.sleep(0.5)
                # Poora OTP type karo — browser automatically next box pe jaata hai
                ActionChains(driver).send_keys(otp).perform()
                logger.info("✅ Method 4 kaam kiya!")
                return True
    except Exception as e:
        logger.info(f"Method 4 fail: {e}")

    # ── METHOD 5: Single OTP input field ─────────────────────────
    try:
        single_selectors = [
            "input[name*='otp']",
            "input[id*='otp']",
            "input[placeholder*='OTP']",
            "input[placeholder*='otp']",
            "input[maxlength='6']",
            "input[maxlength='4']",
            "input[name*='code']",
        ]
        for sel in single_selectors:
            try:
                el = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, sel)))
                el.clear()
                el.send_keys(otp)
                logger.info(f"✅ Method 5 kaam kiya: {sel}")
                return True
            except Exception:
                continue
    except Exception as e:
        logger.info(f"Method 5 fail: {e}")

    # Koi method kaam nahi kiya — HTML dump karo
    logger.error("❌ Koi bhi OTP fill method kaam nahi kiya!")
    try:
        all_inputs = driver.find_elements(By.TAG_NAME, "input")
        logger.info(f"Page pe kul inputs: {len(all_inputs)}")
        for inp in all_inputs:
            logger.info(f"  Input → type={inp.get_attribute('type')} | "
                        f"id={inp.get_attribute('id')} | "
                        f"name={inp.get_attribute('name')} | "
                        f"maxlength={inp.get_attribute('maxlength')} | "
                        f"class={inp.get_attribute('class')}")
    except Exception:
        pass
    return False


# ── LOGIN ──────────────────────────────────────────────────────────────────────

def login_to_naukri(driver, email, password, gmail_user, gmail_app_password):
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

    # Login button
    btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@type='submit']")))
    ActionChains(driver).move_to_element(btn).pause(0.8).click().perform()
    logger.info("✅ Login click kiya")
    human_delay(4, 6)

    driver.save_screenshot("02_after_login.png")
    logger.info(f"URL: {driver.current_url}")

    # OTP page check
    page_src = driver.page_source.lower()
    if any(k in page_src for k in ["otp", "one time", "verify your"]):
        logger.info("🔐 OTP page detect hua!")
        driver.save_screenshot("03_otp_page.png")

        otp = get_otp_from_gmail(gmail_user, gmail_app_password, wait_seconds=90)
        if not otp:
            logger.error("❌ Gmail se OTP nahi mila!")
            return False

        human_delay(1, 2)  # OTP fill se pehle thoda wait

        if not fill_otp(driver, otp):
            driver.save_screenshot("03b_otp_fill_failed.png")
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
        logger.info(f"Verify ke baad URL: {driver.current_url}")

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


# ── RESUME UPDATE ──────────────────────────────────────────────────────────────

def update_resume(driver, resume_path):
    abs_path = os.path.abspath(resume_path)
    wait = WebDriverWait(driver, 30)

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
                    logger.info("✅ Upload button ke baad resume diya!")
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


# ── MAIN ───────────────────────────────────────────────────────────────────────

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
