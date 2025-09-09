from appium import webdriver
from appium.options.android import UiAutomator2Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time, sys

UDID = sys.argv[1]
EMAIL = sys.argv[2]
PW = sys.argv[3]
APPIUM = 'http://localhost:4725/wd/hub'

opts = UiAutomator2Options()
opts.platform_name='Android'; opts.automation_name='UiAutomator2'; opts.udid=UDID
opts.auto_grant_permissions=True; opts.new_command_timeout=240
opts.app_package='jp.co.meetscom.koetomo'
opts.app_activity='jp.co.meetscom.koetomo.controller.top.RootViewActivity'

drv = webdriver.Remote(APPIUM, options=opts)
wait = WebDriverWait(drv, 10)

logs=[]

def log(s):
    logs.append(s)
    print(s)

try:
    # Ensure we are on top screen
    time.sleep(1)
    try:
        btn = wait.until(EC.presence_of_element_located((By.ID, 'jp.co.meetscom.koetomo:id/mail_signup_button')))
        btn.click(); log('Tapped mail_signup_button')
    except Exception:
        log('mail_signup_button not visible; continuing')

    # Fill email/pw
    try:
        mail = WebDriverWait(drv, 8).until(EC.presence_of_element_located((By.ID, 'jp.co.meetscom.koetomo:id/mail_input')))
        mail.clear(); mail.send_keys(EMAIL); log('Filled email')
        pw = WebDriverWait(drv, 5).until(EC.presence_of_element_located((By.ID, 'jp.co.meetscom.koetomo:id/password_input')))
        pw.clear(); pw.send_keys(PW); log('Filled password')
        submit = WebDriverWait(drv, 5).until(EC.presence_of_element_located((By.ID, 'jp.co.meetscom.koetomo:id/mail_signup_button')))
        if submit.is_enabled(): submit.click(); log('Clicked submit')
        else: log('Submit not enabled')
    except Exception as e:
        log(f'Email/PW screen not found: {e}')

    time.sleep(2)
    # Report where we are
    try:
        log('current package='+drv.current_package)
        log('current activity='+drv.current_activity)
    except Exception:
        pass

    # If profile screen
    try:
        uname = WebDriverWait(drv, 5).until(EC.presence_of_element_located((By.ID, 'jp.co.meetscom.koetomo:id/userName')))
        uname.clear(); uname.send_keys('forusan77'); log('Filled userName')
    except Exception:
        log('userName not found')

    try:
        sex = drv.find_element(By.ID, 'jp.co.meetscom.koetomo:id/sexText')
        sex.click(); sex.clear(); sex.send_keys('男性'); log('Filled sex')
    except Exception:
        log('sexText not found')

    try:
        bd = drv.find_element(By.ID, 'jp.co.meetscom.koetomo:id/birthday_field')
        bd.click(); bd.clear(); bd.send_keys('1998/01/01'); log('Filled birthday')
    except Exception:
        log('birthday_field not found')

    try:
        create = drv.find_element(By.ID, 'jp.co.meetscom.koetomo:id/create_button')
        if create.is_enabled(): create.click(); log('Clicked create_button')
        else: log('create_button disabled')
    except Exception:
        log('create_button not found')

    time.sleep(1)
finally:
    try:
        drv.quit()
    except Exception:
        pass
