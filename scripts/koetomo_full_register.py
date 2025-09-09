from __future__ import annotations

import random
import sys
import time
from appium import webdriver
from appium.options.android import UiAutomator2Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


UDID = '127.0.0.1:16932'
APPIUM = 'http://localhost:4725/wd/hub'
EMAIL = 'temp@example.com'
PASSWORD = 'Abc12345!'


def w(drv, by, val, t=10):
    return WebDriverWait(drv, t).until(EC.presence_of_element_located((by, val)))


def main():
    global EMAIL, PASSWORD, UDID, APPIUM
    # Allow overrides via CLI: email [password] [udid] [appium]
    # python koetomo_full_register.py email@example.com MyPass 127.0.0.1:16932 http://localhost:4725/wd/hub
    import sys
    if len(sys.argv) > 1:
        EMAIL = sys.argv[1]
    if len(sys.argv) > 2:
        PASSWORD = sys.argv[2]
    if len(sys.argv) > 3:
        UDID = sys.argv[3]
    if len(sys.argv) > 4:
        APPIUM = sys.argv[4]
    opts = UiAutomator2Options()
    opts.platform_name = 'Android'
    opts.automation_name = 'UiAutomator2'
    opts.udid = UDID
    opts.auto_grant_permissions = True
    opts.new_command_timeout = 240
    opts.app_package = 'jp.co.meetscom.koetomo'
    opts.app_activity = 'jp.co.meetscom.koetomo.controller.top.RootViewActivity'

    drv = webdriver.Remote(APPIUM, options=opts)
    try:
        # Top screen → tap mail sign up
        try:
            btn = w(drv, By.ID, 'jp.co.meetscom.koetomo:id/mail_signup_button', 8)
            btn.click()
        except Exception:
            pass

        # Email/password screen
        try:
            mail = w(drv, By.ID, 'jp.co.meetscom.koetomo:id/mail_input', 8)
            mail.clear(); mail.send_keys(EMAIL)
            pw = w(drv, By.ID, 'jp.co.meetscom.koetomo:id/password_input', 5)
            pw.clear(); pw.send_keys(PASSWORD)
            submit = w(drv, By.ID, 'jp.co.meetscom.koetomo:id/mail_signup_button', 5)
            if submit.is_enabled():
                submit.click()
        except Exception:
            pass

        # Profile screen
        name = f'forusan{random.randint(10,99)}'
        try:
            nm = w(drv, By.ID, 'jp.co.meetscom.koetomo:id/userName', 10)
            nm.clear(); nm.send_keys(name)
        except Exception:
            pass

        try:
            sex = w(drv, By.ID, 'jp.co.meetscom.koetomo:id/sexText', 5)
            sex.click(); sex.clear(); sex.send_keys('男性')
        except Exception:
            pass

        try:
            bd = w(drv, By.ID, 'jp.co.meetscom.koetomo:id/birthday_field', 5)
            bd.click(); bd.clear(); bd.send_keys('1998/01/01')
        except Exception:
            pass

        try:
            create = w(drv, By.ID, 'jp.co.meetscom.koetomo:id/create_button', 8)
            if create.is_enabled():
                create.click()
        except Exception:
            pass

        time.sleep(2)
    finally:
        try:
            drv.quit()
        except Exception:
            pass


if __name__ == '__main__':
    sys.exit(main())
