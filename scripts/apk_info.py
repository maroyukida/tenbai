from __future__ import annotations

"""
Print basic APK metadata (package, version, sdk).

Usage:
  python scripts/apk_info.py "E:\\path\\app.apk"

Requires: pip install apkutils-patch
"""

import sys
from apkutils2 import APK


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/apk_info.py <apk_path>")
        return 2
    apk_path = sys.argv[1]
    apk = APK(apk_path)
    man = apk.get_manifest()
    pkg = man.get("@package") or man.get("package")
    ver_name = man.get("@android:versionName") or man.get("versionName")
    ver_code = man.get("@android:versionCode") or man.get("versionCode")
    uses_sdk = man.get("uses-sdk", {})
    min_sdk = uses_sdk.get("@android:minSdkVersion")
    tgt_sdk = uses_sdk.get("@android:targetSdkVersion")
    print(f"package: {pkg}")
    print(f"versionName: {ver_name}")
    print(f"versionCode: {ver_code}")
    print(f"minSdk: {min_sdk}")
    print(f"targetSdk: {tgt_sdk}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

