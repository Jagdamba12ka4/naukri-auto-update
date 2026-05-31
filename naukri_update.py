import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def setup_driver():
    """Headless Chrome driver setup"""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    
    service = Service('/usr/bin/chromedriver')
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return driver

def login_to_naukri(driver, email, password):
    """Naukri.com pe login karo"""
    logger.info("Naukri.com pe ja raha hoon...")
    driver.get("https://www.naukri.com/nlogin/login")
    wait = WebDriverWait(driver, 20)
    
    # Email field
    logger.info("Email enter kar raha hoon...")
    email_field = wait.until(
        EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Enter your active Email ID / Username']"))
    )
    email_field.clear()
    email_field.send_keys(email)
    time.sleep(1)
    
    # Password field
    logger.info("Password enter kar raha hoon...")
    password_field = driver.find_element(By.XPATH, "//input[@placeholder='Enter your password']")
    password_field.clear()
    password_field.send_keys(password)
    time.sleep(1)
    
    # Login button click
    logger.info("Login button click kar raha hoon...")
    login_btn = wait.until(
        EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Login')]"))
    )
    login_btn.click()
    time.sleep(5)
    
    # Login verify karo
    if "nlogin" not in driver.current_url:
        logger.info("✅ Login successful!")
        return True
    else:
        logger.error("❌ Login fail hua!")
        return False

def update_resume(driver, resume_path):
    """Resume update karo"""
    wait = WebDriverWait(driver, 30)
    
    logger.info("Profile page pe ja raha hoon...")
    driver.get("https://www.naukri.com/mnjuser/profile")
    time.sleep(4)
    
    try:
        # Resume section dhundo
        logger.info("Resume upload section dhundh raha hoon...")
        
        # Upload button ya file input dhundo
        upload_input = wait.until(
            EC.presence_of_element_located(
                (By.XPATH, "//input[@type='file']")
            )
        )
        
        # Resume file ka absolute path
        abs_resume_path = os.path.abspath(resume_path)
        logger.info(f"Resume upload ho raha hai: {abs_resume_path}")
        
        # File send karo
        upload_input.send_keys(abs_resume_path)
        time.sleep(5)
        
        # Confirm/Save button check karo
        try:
            save_btn = wait.until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//button[contains(text(),'Save') or contains(text(),'Upload') or contains(text(),'Update')]")
                )
            )
            save_btn.click()
            logger.info("✅ Save button click kiya!")
            time.sleep(3)
        except Exception:
            logger.info("ℹ️ Auto-save ho gaya (no save button found)")
        
        logger.info("✅ Resume successfully update ho gaya!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Resume update fail: {str(e)}")
        # Screenshot save karo debugging ke liye
        driver.save_screenshot("error_screenshot.png")
        return False

def main():
    # Secrets se credentials lo
    email = os.environ.get("NAUKRI_EMAIL")
    password = os.environ.get("NAUKRI_PASSWORD")
    resume_path = os.environ.get("RESUME_PATH", "resume/your_resume.pdf")
    
    if not email or not password:
        logger.error("❌ NAUKRI_EMAIL aur NAUKRI_PASSWORD environment variables set nahi hain!")
        exit(1)
    
    if not os.path.exists(resume_path):
        logger.error(f"❌ Resume file nahi mili: {resume_path}")
        exit(1)
    
    driver = None
    try:
        logger.info("🚀 Naukri Resume Auto-Update start ho raha hai...")
        driver = setup_driver()
        
        if login_to_naukri(driver, email, password):
            success = update_resume(driver, resume_path)
            if success:
                logger.info("🎉 Resume update complete!")
            else:
                logger.error("❌ Resume update fail hua!")
                exit(1)
        else:
            logger.error("❌ Login fail - credentials check karo!")
            exit(1)
            
    except Exception as e:
        logger.error(f"❌ Unexpected error: {str(e)}")
        if driver:
            driver.save_screenshot("error_screenshot.png")
        exit(1)
        
    finally:
        if driver:
            driver.quit()
            logger.info("Browser band ho gaya.")

if __name__ == "__main__":
    main()
