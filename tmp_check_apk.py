from apkutils2 import APK
import sys
apk_path = r"E:\hdd\chromeダウンロード\koetomo-meetscom-inc.apk"
apk = APK(apk_path)
man = apk.get_manifest()
print(man)
print(type(man))
