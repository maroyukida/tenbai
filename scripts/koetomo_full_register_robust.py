from __future__ import annotations

import random
import sys
import time
from appium import webdriver
from appium.options.android import UiAutomator2Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def wait(drv, by, val, t=10):
    return WebDriverWait(drv, t).until(EC.presence_of_element_located((by, val)))


def run(email: str, password: str, udid: str, appium_url: str = 'http://localhost:4725/wd/hub') -> None:
    opts = UiAutomator2Options()
    opts.platform_name = 'Android'
    opts.automation_name = 'UiAutomator2'
    opts.udid = udid
    opts.auto_grant_permissions = True
    opts.new_command_timeout = 240
    opts.app_package = 'jp.co.meetscom.koetomo'
    opts.app_activity = 'jp.co.meetscom.koetomo.controller.top.RootViewActivity'

    drv = webdriver.Remote(appium_url, options=opts)
    try:
        def scroll(direction: str = 'down', percent: float = 0.85, tries: int = 2):
            for _ in range(tries):
                try:
                    drv.execute_script(
                        'mobile: scrollGesture',
                        {
                            'left': 0,
                            'top': 0,
                            'width': 900,
                            'height': 1600,
                            'direction': direction,
                            'percent': percent,
                        },
                    )
                except Exception:
                    pass

        # Close common popups
        for _ in range(2):
            for txt in ['OK', '閉じる', '許可', '同意', '続行', '次へ']:
                try:
                    el = WebDriverWait(drv, 1).until(EC.element_to_be_clickable((By.XPATH, f"//*[@text='{txt}']")))
                    el.click()
                except Exception:
                    pass

        # Top -> tap mail sign up
        tapped = False
        for _ in range(3):
            try:
                el = WebDriverWait(drv, 4).until(
                    EC.element_to_be_clickable((By.ID, 'jp.co.meetscom.koetomo:id/mail_signup_button'))
                )
                el.click(); tapped = True; break
            except Exception:
                for xp in [
                    "//*[@text='メールアドレスで登録']",
                    "//*[contains(@text,'メール') and contains(@text,'登録')]",
                    "//*[@text='Sign up' or @text='Create account']",
                ]:
                    try:
                        el = WebDriverWait(drv, 2).until(EC.element_to_be_clickable((By.XPATH, xp)))
                        el.click(); tapped = True; break
                    except Exception:
                        continue
                if tapped:
                    break
                scroll('down')

        # Email/password
        try:
            try:
                mail = wait(drv, By.ID, 'jp.co.meetscom.koetomo:id/mail_input', 8)
            except Exception:
                try:
                    mail = wait(drv, By.XPATH, "//android.widget.EditText[@text='メールアドレス' or contains(@text,'mail') or contains(@content-desc,'mail')]")
                except Exception:
                    scroll('down'); mail = wait(drv, By.ID, 'jp.co.meetscom.koetomo:id/mail_input', 5)
            mail.clear(); mail.send_keys(email)

            try:
                pw = wait(drv, By.ID, 'jp.co.meetscom.koetomo:id/password_input', 5)
            except Exception:
                pw = wait(drv, By.XPATH, "//android.widget.EditText[@password='true' or contains(@text,'パスワード')]")
            pw.clear(); pw.send_keys(password)

            try:
                submit = wait(drv, By.ID, 'jp.co.meetscom.koetomo:id/mail_signup_button', 5)
            except Exception:
                submit = wait(drv, By.XPATH, "//*[@text='このメールアドレスで登録' or @text='登録' or @text='Sign up' or @text='Submit']")
            if submit.is_enabled():
                submit.click()
        except Exception:
            pass

        # Profile
        try:
            nm = wait(drv, By.ID, 'jp.co.meetscom.koetomo:id/userName', 6)
            nm.clear(); nm.send_keys(f'forusan{random.randint(10,99)}')
        except Exception:
            pass
        try:
            sx = wait(drv, By.ID, 'jp.co.meetscom.koetomo:id/sexText', 3)
            sx.click(); sx.clear(); sx.send_keys('男性')
        except Exception:
            pass
        try:
            bd = wait(drv, By.ID, 'jp.co.meetscom.koetomo:id/birthday_field', 3)
            bd.click(); bd.clear(); bd.send_keys('1998/01/01')
        except Exception:
            pass
        try:
            create = wait(drv, By.ID, 'jp.co.meetscom.koetomo:id/create_button', 5)
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
    email = sys.argv[1] if len(sys.argv) > 1 else 'temp@example.com'
    password = sys.argv[2] if len(sys.argv) > 2 else 'Abc12345!'
    udid = sys.argv[3] if len(sys.argv) > 3 else '127.0.0.1:16932'
    appium = sys.argv[4] if len(sys.argv) > 4 else 'http://localhost:4725/wd/hub'
    run(email, password, udid, appium)

