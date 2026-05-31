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

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# GMAIL SE OTP PADHNA
# ─────────────────────────────────────────────

def get_otp_from_gmail(gmail_user, gmail_app_password, wait_seconds=60):
    """
    Gmail IMAP se Naukri OTP read karo.
    wait_seconds: kitni der tak OTP email ka wait karein
    """
    logger.info("📧 Gmail mein Naukri OTP dhundh raha hoon...")

    start_time = time.time()
    otp_received_after = datetime.now(timezone.utc)

    while time.time() - start_time < wait_seconds:
        try:
            # Gmail IMAP connect karo
            mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
            mail.login(gmail_user, gmail_app_password)
            mail.select("inbox")

            # Naukri ke emails dhundo (last 2 minutes ke)
            search_criteria = '(FROM "naukri" UNSEEN)'
            _, message_ids = mail.search(None, search_criteria)

            if message_ids[0]:
                ids = message_ids[0].split()
                # Sabse naya email lo
                latest_id = ids[-1]
                _, msg_data = mail.fetch(latest_id, "(RFC822)")

                for response in msg_data:
                    if isinstance(response, tuple):
                        msg = email.message_from_bytes(response[1])

                        # Email receive time check karo
                        email_date_str = msg.get("Date", "")
                        logger.info(f"Email subject: {msg.get('Subject', 'No subject')}")

                        # Email body se OTP nikalo
                        body = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                if part.get_content_type() == "text/plain":
                                    body += part.get_payload(decode=True).decode("utf-8", errors="ignore")
                                elif part.get_content_type() == "text/html":
                                    body += part.get_payload(decode=True).decode("utf-8", errors="ignore")
                        else:
                            body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")

                        # OTP pattern dhundo (4 ya 6 digit)
                        otp_patterns = [
                            r'\b(\d{6})\b',   # 6 digit OTP
                            r'\b(\d{4})\b',   # 4 digit OTP
                            r'OTP[:\s]+(\d+)',
                            r'code[:\s]+(\d+)',
                            r'One.?Time.?Password[:\s]+(\d+)',
                        ]

                        for pattern in otp_patterns:
                            match = re.search(pattern, body, re.IGNORECASE)
                            if match:
                                otp = match.group(1)
                                logger.info(f"✅ OTP mila: {otp}")
                                mail.logout()
                                return otp

                        logger.info("Email mila par OTP nahi mila — retry...")

            mail.logout()

        except Exception as e:
            logger.warning(f"Gmail check error: {e}")

        logger.info(f"OTP nahi mila — 10 second baad retry ({int(time.time() - start_time)}s elapsed)...")
        time.sleep(10)

    logger.error(f"❌ {wait_seconds} seconds mein OTP nahi mila!")
    return None


def fill_otp(driver, otp):
    """OTP boxes mein OTP fill karo"""
    wait = WebDriverWait(driver, 15)
    logger.info(f"OTP fill kar raha hoon: {otp}")

    # Method 1: 6 alag alag input boxes
    try:
        otp_inputs = driver.find_elements(By.XPATH, "//input[@maxlength='1' and @type='text']")
        if len(otp_inputs) >= len(otp):
            for i, digit in enumerate(otp):
                otp_inputs[i].click()
                otp_inputs[i].send_keys(digit)
                time.sleep(0.2)
            logger.info("✅ OTP individual boxes mein fill kiya!")
            return True
    except Exception:
        pass

    # Method 2: Single OTP input box
    try:
        otp_selectors = [
            "//input[@type='text' and contains(@placeholder,'OTP')]",
            "//input[contains(@name,'otp')]",
            "//input[contains(@id,'otp')]",
            "//input[@maxlength='6']",
            "//input[@maxlength='4']",
        ]
        for sel in otp_selectors:
            try:
                otp_field = wait.until(EC.element_to_be_clickable((By.XPATH, sel)))
                otp_field.clear()
                otp_field.send_keys(otp)
                logger.info(f"✅ OTP single box mein fill kiya: {sel}")
                return True
            except Exception:
                continue
    except Exception:
        pass

    logger.error("❌ OTP input field nahi mila!")
    return False


# ─────────────────────────────────────────────
# CHROME DRIVER
# ─────────────────────────────────────────────

def human_delay(min_s=1.0, max_s=2.5):
    time.sleep(random.uniform(min_s, max_s))


def human_type(element, text):
    element.clear()
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.06, 0.15))


def setup_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1366,768")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--lang=en-IN")
    options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )

    service = Service('/usr/bin/chromedriver')
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-IN', 'en'] });
            window.chrome = { runtime: {} };
        """
    })
    return driver


# ─────────────────────────────────────────────
# LOGIN
# ─────────────────────────────────────────────

def login_to_naukri(driver, email, password, gmail_user, gmail_app_password):
    logger.info("Naukri login page pe ja raha hoon...")
    driver.get("https://www.naukri.com/nlogin/login")
    human_delay(3, 5)

    logger.info(f"Page: {driver.title}")
    driver.save_screenshot("01_login_page.png")

    wait = WebDriverWait(driver, 20)

    # Email
    try:
        ef = wait.until(EC.element_to_be_clickable((By.ID, "usernameField")))
        ActionChains(driver).move_to_element(ef).pause(0.5).click().perform()
        human_delay(0.5, 1)
        human_type(ef, email)
        logger.info("✅ Email fill kiya")
    except Exception as e:
        logger.error(f"Email field error: {e}")
        driver.save_screenshot("email_error.png")
        return False

    human_delay(0.8, 1.5)

    # Password
    try:
        pf = wait.until(EC.element_to_be_clickable((By.ID, "passwordField")))
        ActionChains(driver).move_to_element(pf).pause(0.5).click().perform()
        human_delay(0.5, 1)
        human_type(pf, password)
        logger.info("✅ Password fill kiya")
    except Exception as e:
        logger.error(f"Password field error: {e}")
        driver.save_screenshot("pass_error.png")
        return False

    human_delay(1, 2)

    # Login button
    try:
        btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@type='submit']")))
        ActionChains(driver).move_to_element(btn).pause(0.8).click().perform()
        logger.info("✅ Login button click kiya")
    except Exception as e:
        logger.error(f"Login button error: {e}")
        return False

    human_delay(4, 6)
    driver.save_screenshot("02_after_login_click.png")
    logger.info(f"URL: {driver.current_url}")

    # ── OTP PAGE CHECK ────────────────────────────
    otp_keywords = ["otp", "one time", "verify", "verification"]
    page_lower = driver.page_source.lower()

    if any(k in page_lower for k in otp_keywords):
        logger.info("🔐 OTP page detect hua!")
        driver.save_screenshot("03_otp_page.png")

        # Gmail se OTP lo
        otp = get_otp_from_gmail(gmail_user, gmail_app_password, wait_seconds=90)

        if not otp:
            logger.error("❌ OTP nahi mila Gmail se!")
            return False

        # OTP fill karo
        if not fill_otp(driver, otp):
            logger.error("❌ OTP fill nahi hua!")
            return False

        human_delay(1, 2)

        # Verify button click karo
        verify_selectors = [
            "//button[contains(text(),'Verify')]",
            "//button[contains(text(),'Submit')]",
            "//button[@type='submit']",
            "//input[@type='submit']",
        ]
        for sel in verify_selectors:
            try:
                vbtn = WebDriverWait(driver, 8).until(
                    EC.element_to_be_clickable((By.XPATH, sel))
                )
                vbtn.click()
                logger.info(f"✅ Verify button click: {sel}")
                break
            except Exception:
                continue

        human_delay(4, 6)
        driver.save_screenshot("04_after_otp.png")
        logger.info(f"OTP ke baad URL: {driver.current_url}")

    # ── LOGIN SUCCESS CHECK ───────────────────────
    current_url = driver.current_url
    if "nlogin" not in current_url and "login" not in current_url:
        logger.info(f"✅ Login successful! URL: {current_url}")
        return True
    elif any(s in current_url for s in ["mnjuser", "myapplication", "dashboard"]):
        logger.info("✅ Login successful!")
        return True
    else:
        logger.error(f"❌ Login fail. URL: {current_url}")
        return False


# ─────────────────────────────────────────────
# RESUME UPDATE
# ─────────────────────────────────────────────

def update_resume(driver, resume_path):
    abs_path = os.path.abspath(resume_path)
    wait = WebDriverWait(driver, 30)

    logger.info("Profile page pe ja raha hoon...")
    driver.get("https://www.naukri.com/mnjuser/profile")
    human_delay(4, 6)

    logger.info(f"Profile URL: {driver.current_url}")
    driver.save_screenshot("05_profile_page.png")

    # File input
    file_inputs = driver.find_elements(By.XPATH, "//input[@type='file']")
    logger.info(f"File inputs mile: {len(file_inputs)}")

    if file_inputs:
        fi = file_inputs[0]
        driver.execute_script("""
            arguments[0].style.display = 'block';
            arguments[0].style.visibility = 'visible';
            arguments[0].style.opacity = '1';
        """, fi)
        fi.send_keys(abs_path)
        logger.info(f"✅ Resume path diya: {abs_path}")
        human_delay(4, 6)
    else:
        # Upload button dhundo
        for sel in [
            "//button[contains(text(),'Update Resume')]",
            "//button[contains(text(),'Upload Resume')]",
            "//a[contains(text(),'Update Resume')]",
            "//*[@id='lazyResumeHead']//button",
        ]:
            try:
                btn = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, sel)))
                btn.click()
                human_delay(2, 3)
                fi2 = driver.find_elements(By.XPATH, "//input[@type='file']")
                if fi2:
                    driver.execute_script("arguments[0].style.display='block';", fi2[0])
                    fi2[0].send_keys(abs_path)
                    human_delay(4, 6)
                    logger.info("✅ Upload button ke baad file di!")
                    break
            except Exception:
                continue

    # Save button
    for sel in ["//button[contains(text(),'Save')]", "//button[contains(text(),'Confirm')]",
                "//button[contains(text(),'Update')]", "//button[@type='submit']"]:
        try:
            btn = WebDriverWait(driver, 6).until(EC.element_to_be_clickable((By.XPATH, sel)))
            btn.click()
            logger.info(f"✅ Save click: {sel}")
            human_delay(2, 3)
            break
        except Exception:
            continue

    driver.save_screenshot("06_final.png")
    logger.info("✅ Resume update complete!")
    return True


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    email        = os.environ.get("NAUKRI_EMAIL")
    password     = os.environ.get("NAUKRI_PASSWORD")
    gmail_user   = os.environ.get("GMAIL_USER", email)   # Same email ya alag
    gmail_pass   = os.environ.get("GMAIL_APP_PASSWORD")
    resume_path  = os.environ.get("RESUME_PATH", "resume/your_resume.pdf")

    if not email or not password:
        logger.error("❌ NAUKRI_EMAIL aur NAUKRI_PASSWORD set karo!")
        exit(1)
    if not gmail_pass:
        logger.error("❌ GMAIL_APP_PASSWORD set karo (Gmail App Password, normal password nahi)!")
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
