import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def setup_driver():
    """Headless Chrome driver setup"""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")  # New headless mode
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--remote-debugging-port=9222")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )

    service = Service('/usr/bin/chromedriver')
    driver = webdriver.Chrome(service=service, options=chrome_options)

    # Bot detection bypass
    driver.execute_cdp_cmd('Network.setUserAgentOverride', {
        "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                     "AppleWebKit/537.36 (KHTML, like Gecko) "
                     "Chrome/124.0.0.0 Safari/537.36"
    })
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return driver


def safe_find_and_fill(driver, wait, locators, value, field_name):
    """
    Multiple XPath try karo — jo pehle mile use karo.
    Naukri ka UI frequently change hota hai, isliye fallback list zaroori hai.
    """
    for by, selector in locators:
        try:
            element = wait.until(EC.presence_of_element_located((by, selector)))
            driver.execute_script("arguments[0].scrollIntoView(true);", element)
            time.sleep(0.5)
            element.click()
            element.clear()
            element.send_keys(value)
            logger.info(f"✅ {field_name} fill hua: {selector}")
            return element
        except Exception:
            continue
    raise Exception(f"❌ {field_name} ka koi bhi locator kaam nahi kiya!")


def login_to_naukri(driver, email, password):
    """Naukri.com pe login karo — multiple fallback selectors ke saath"""
    logger.info("Naukri login page pe ja raha hoon...")
    driver.get("https://www.naukri.com/nlogin/login")
    time.sleep(4)

    wait = WebDriverWait(driver, 25)

    # Page title log karo
    logger.info(f"Page title: {driver.title}")
    logger.info(f"Current URL: {driver.current_url}")

    # ── EMAIL FIELD ──────────────────────────────────────────────
    email_locators = [
        (By.ID, "usernameField"),
        (By.XPATH, "//input[@id='usernameField']"),
        (By.XPATH, "//input[@type='text' and contains(@placeholder,'Email')]"),
        (By.XPATH, "//input[@type='text' and contains(@placeholder,'email')]"),
        (By.XPATH, "//input[@name='username']"),
        (By.XPATH, "//input[contains(@class,'ginput') and @type='text']"),
        (By.CSS_SELECTOR, "input[placeholder*='Email']"),
        (By.CSS_SELECTOR, "input[placeholder*='email']"),
        (By.CSS_SELECTOR, "#usernameField"),
        (By.XPATH, "(//input[@type='text'])[1]"),
    ]
    safe_find_and_fill(driver, wait, email_locators, email, "Email field")
    time.sleep(1)

    # ── PASSWORD FIELD ───────────────────────────────────────────
    password_locators = [
        (By.ID, "passwordField"),
        (By.XPATH, "//input[@id='passwordField']"),
        (By.XPATH, "//input[@type='password']"),
        (By.XPATH, "//input[contains(@placeholder,'password')]"),
        (By.XPATH, "//input[contains(@placeholder,'Password')]"),
        (By.CSS_SELECTOR, "input[type='password']"),
        (By.CSS_SELECTOR, "#passwordField"),
    ]
    safe_find_and_fill(driver, wait, password_locators, password, "Password field")
    time.sleep(1)

    # ── LOGIN BUTTON ─────────────────────────────────────────────
    login_btn_locators = [
        (By.XPATH, "//button[@type='submit']"),
        (By.XPATH, "//button[contains(text(),'Login')]"),
        (By.XPATH, "//button[contains(text(),'login')]"),
        (By.XPATH, "//button[contains(text(),'Sign in')]"),
        (By.XPATH, "//input[@type='submit']"),
        (By.CSS_SELECTOR, "button[type='submit']"),
        (By.XPATH, "//div[contains(@class,'login')]//button"),
    ]

    login_btn = None
    for by, selector in login_btn_locators:
        try:
            login_btn = wait.until(EC.element_to_be_clickable((by, selector)))
            logger.info(f"✅ Login button mila: {selector}")
            break
        except Exception:
            continue

    if not login_btn:
        raise Exception("❌ Login button nahi mila!")

    login_btn.click()
    logger.info("Login button click kiya, wait kar raha hoon...")
    time.sleep(6)

    # ── LOGIN VERIFY ─────────────────────────────────────────────
    current_url = driver.current_url
    logger.info(f"Login ke baad URL: {current_url}")

    # Error message check karo
    try:
        error_msg = driver.find_element(
            By.XPATH, "//*[contains(@class,'error') or contains(@class,'Error')]"
        )
        if error_msg.is_displayed():
            logger.error(f"Login error message: {error_msg.text}")
    except Exception:
        pass

    if "nlogin" not in current_url and "login" not in current_url:
        logger.info("✅ Login successful!")
        return True
    elif "myapplication" in current_url or "mnjuser" in current_url:
        logger.info("✅ Login successful — profile page pe hain!")
        return True
    else:
        # Screenshot lo debugging ke liye
        driver.save_screenshot("login_failed.png")
        logger.error(f"❌ Login fail hua. URL: {current_url}")
        return False


def update_resume(driver, resume_path):
    """Resume update karo Naukri profile page pe"""
    wait = WebDriverWait(driver, 30)
    abs_resume_path = os.path.abspath(resume_path)

    logger.info("Profile page pe ja raha hoon...")
    driver.get("https://www.naukri.com/mnjuser/profile")
    time.sleep(5)

    logger.info(f"Profile URL: {driver.current_url}")
    driver.save_screenshot("profile_page.png")

    # ── FILE INPUT DHUNDO ─────────────────────────────────────────
    file_input_locators = [
        (By.XPATH, "//input[@type='file']"),
        (By.CSS_SELECTOR, "input[type='file']"),
        (By.XPATH, "//input[@type='file' and contains(@class,'fileUpload')]"),
        (By.XPATH, "//input[@type='file' and contains(@name,'resume')]"),
        (By.CSS_SELECTOR, "input[type='file'][accept*='pdf']"),
    ]

    file_input = None
    for by, selector in file_input_locators:
        try:
            # File input hidden bhi ho sakta hai — directly interact karo
            elements = driver.find_elements(by, selector)
            if elements:
                file_input = elements[0]
                logger.info(f"✅ File input mila: {selector}")
                break
        except Exception:
            continue

    if file_input:
        logger.info(f"Resume upload ho raha hai: {abs_resume_path}")
        # JavaScript se visible banao (hidden inputs ke liye)
        driver.execute_script("arguments[0].style.display = 'block';", file_input)
        driver.execute_script("arguments[0].style.visibility = 'visible';", file_input)
        file_input.send_keys(abs_resume_path)
        logger.info("✅ File input mein resume path diya!")
        time.sleep(5)
    else:
        # Fallback: Upload button click karo pehle
        logger.info("File input nahi mila — Upload button dhundh raha hoon...")
        upload_btn_locators = [
            (By.XPATH, "//button[contains(text(),'Update Resume')]"),
            (By.XPATH, "//button[contains(text(),'Upload Resume')]"),
            (By.XPATH, "//a[contains(text(),'Update Resume')]"),
            (By.XPATH, "//a[contains(text(),'Upload Resume')]"),
            (By.XPATH, "//*[contains(@class,'upload') and contains(@class,'resume')]"),
            (By.CSS_SELECTOR, "[class*='resumeUpload']"),
            (By.XPATH, "//label[contains(text(),'Resume')]"),
        ]

        for by, selector in upload_btn_locators:
            try:
                btn = wait.until(EC.element_to_be_clickable((by, selector)))
                btn.click()
                logger.info(f"Upload button click kiya: {selector}")
                time.sleep(3)

                # Ab file input dhundo
                file_inputs = driver.find_elements(By.XPATH, "//input[@type='file']")
                if file_inputs:
                    driver.execute_script(
                        "arguments[0].style.display = 'block';", file_inputs[0]
                    )
                    file_inputs[0].send_keys(abs_resume_path)
                    logger.info("✅ Upload button ke baad file input mila aur file di!")
                    time.sleep(5)
                    break
            except Exception:
                continue
        else:
            driver.save_screenshot("upload_failed.png")
            raise Exception("❌ Koi bhi upload method kaam nahi kiya!")

    # ── SAVE/CONFIRM BUTTON ───────────────────────────────────────
    save_locators = [
        (By.XPATH, "//button[contains(text(),'Save')]"),
        (By.XPATH, "//button[contains(text(),'Confirm')]"),
        (By.XPATH, "//button[contains(text(),'Update')]"),
        (By.XPATH, "//button[contains(text(),'Done')]"),
        (By.CSS_SELECTOR, "button.saveBtn"),
        (By.XPATH, "//button[@type='submit']"),
    ]

    for by, selector in save_locators:
        try:
            save_btn = WebDriverWait(driver, 8).until(
                EC.element_to_be_clickable((by, selector))
            )
            save_btn.click()
            logger.info(f"✅ Save button click kiya: {selector}")
            time.sleep(3)
            break
        except Exception:
            continue

    # Success verify karo
    driver.save_screenshot("after_upload.png")
    logger.info("✅ Resume update process complete!")
    return True


def main():
    email = os.environ.get("NAUKRI_EMAIL")
    password = os.environ.get("NAUKRI_PASSWORD")
    resume_path = os.environ.get("RESUME_PATH", "resume/your_resume.pdf")

    if not email or not password:
        logger.error("❌ NAUKRI_EMAIL aur NAUKRI_PASSWORD set nahi hain!")
        exit(1)

    if not os.path.exists(resume_path):
        logger.error(f"❌ Resume file nahi mili: {resume_path}")
        exit(1)

    logger.info(f"Resume path: {resume_path}")

    driver = None
    try:
        logger.info("🚀 Naukri Resume Auto-Update start ho raha hai...")
        driver = setup_driver()

        if login_to_naukri(driver, email, password):
            update_resume(driver, resume_path)
            logger.info("🎉 Resume update complete!")
        else:
            logger.error("❌ Login fail — credentials check karo!")
            exit(1)

    except Exception as e:
        logger.error(f"❌ Error: {str(e)}")
        if driver:
            driver.save_screenshot("error_screenshot.png")
        exit(1)

    finally:
        if driver:
            driver.quit()
            logger.info("Browser band ho gaya.")


if __name__ == "__main__":
    main()
