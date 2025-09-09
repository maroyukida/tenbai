from appium import webdriver
from appium.options.android import UiAutomator2Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import random, sys
udid = '127.0.0.1:16932'
opts = UiAutomator2Options()
opts.platform_name = 'Android'
opts.automation_name = 'UiAutomator2'
opts.udid = udid
opts.auto_grant_permissions = True
opts.new_command_timeout = 240
opts.app_package = 'jp.co.meetscom.koetomo'
opts.app_activity = 'jp.co.meetscom.koetomo.controller.top.RootViewActivity'
drv = webdriver.Remote('http://localhost:4725/wd/hub', options=opts)
wait = WebDriverWait(drv, 10)
try:
    # Ensure on profile screen; if not, try navigate by clicking mail sign-up first
    # Fill user name
    name = f'forusan{random.randint(10,99)}'
    try:
        el = wait.until(EC.presence_of_element_located((By.ID, 'jp.co.meetscom.koetomo:id/userName')))
    except Exception:
        # maybe still on email screen; bail gracefully
        sys.exit(0)
    el.clear(); el.send_keys(name)
    # Set gender
    try:
        g = drv.find_element(By.ID, 'jp.co.meetscom.koetomo:id/sexText')
        g.click(); g.clear(); g.send_keys('男性')
    except Exception:
        pass
    # Set birthday
    try:
        b = drv.find_element(By.ID, 'jp.co.meetscom.koetomo:id/birthday_field')
        b.click(); b.clear(); b.send_keys('1998/01/01')
    except Exception:
        pass
    # Submit
    try:
        btn = drv.find_element(By.ID, 'jp.co.meetscom.koetomo:id/create_button')
        if btn.is_enabled():
            btn.click()
    except Exception:
        pass
finally:
    try:
        drv.quit()
    except Exception:
        pass
