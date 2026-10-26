"""Hand-written copy of the files `npx cap add android` (Capacitor 7) generates that the patch script touches.
Written from memory of the Capacitor 7 template, NOT taken from a real generated project (the sandbox could not reach npm).
If the real template differs, `node scripts/patch-android.mjs --check` in the workflow will say so."""
import os, sys
def make(root, target_sdk=35):
    w = lambda rel, txt: (os.makedirs(os.path.dirname(os.path.join(root, rel)), exist_ok=True), open(os.path.join(root, rel), "w").write(txt))
    w("android/app/src/main/AndroidManifest.xml", '''<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">

    <application
        android:allowBackup="true"
        android:icon="@mipmap/ic_launcher"
        android:label="@string/app_name"
        android:roundIcon="@mipmap/ic_launcher_round"
        android:supportsRtl="true"
        android:theme="@style/AppTheme">

        <activity
            android:configChanges="orientation|keyboardHidden|keyboard|screenSize|locale|smallestScreenSize|screenLayout|uiMode|navigation"
            android:name=".MainActivity"
            android:label="@string/title_activity_main"
            android:theme="@style/AppTheme.NoActionBarLaunch"
            android:launchMode="singleTask"
            android:exported="true">

            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>

        </activity>

        <provider
            android:name="androidx.core.content.FileProvider"
            android:authorities="${applicationId}.fileprovider"
            android:exported="false"
            android:grantUriPermissions="true">
            <meta-data
                android:name="android.support.FILE_PROVIDER_PATHS"
                android:resource="@xml/file_paths"></meta-data>
        </provider>
    </application>

    <!-- Permissions -->

    <uses-permission android:name="android.permission.INTERNET" />
</manifest>
''')
    w("android/app/src/main/res/values/styles.xml", '''<?xml version="1.0" encoding="utf-8" ?>
<resources>

    <!-- Base application theme. -->
    <style name="AppTheme" parent="Theme.AppCompat.Light.DarkActionBar">
        <!-- Customize your theme here. -->
        <item name="colorPrimary">@color/colorPrimary</item>
        <item name="colorPrimaryDark">@color/colorPrimaryDark</item>
        <item name="colorAccent">@color/colorAccent</item>
    </style>

    <style name="AppTheme.NoActionBar" parent="Theme.AppCompat.DayNight.NoActionBar">
        <item name="windowActionBar">false</item>
        <item name="windowNoTitle">true</item>
        <item name="android:background">@null</item>
    </style>


    <style name="AppTheme.NoActionBarLaunch" parent="Theme.SplashScreen">
        <item name="android:background">@drawable/splash</item>
    </style>
</resources>
''')
    w("android/app/src/main/res/xml/file_paths.xml", '''<?xml version="1.0" encoding="utf-8"?>
<paths xmlns:android="http://schemas.android.com/apk/res/android">
    <external-path name="my_images" path="." />
    <cache-path name="my_cache_images" path="." />
</paths>
''')
    w("android/variables.gradle", '''ext {
    minSdkVersion = 23
    compileSdkVersion = 35
    targetSdkVersion = %d
    androidxActivityVersion = '1.9.2'
    androidxAppCompatVersion = '1.7.0'
    coreSplashScreenVersion = '1.0.1'
}''' % target_sdk)
    w("android/app/build.gradle", '''apply plugin: 'com.android.application'

android {
    namespace = "com.recallrush.app"
    compileSdk = rootProject.ext.compileSdkVersion
    defaultConfig {
        applicationId "com.recallrush.app"
        minSdkVersion rootProject.ext.minSdkVersion
        targetSdkVersion rootProject.ext.targetSdkVersion
        versionCode 1
        versionName "1.0"
    }
    buildTypes {
        release {
            minifyEnabled false
            proguardFiles getDefaultProguardFile('proguard-android.txt'), 'proguard-rules.pro'
        }
    }
}
''')
if __name__ == "__main__": make(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 35)
