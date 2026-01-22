#!/usr/bin/env python3
"""
Build script for SecureLocal Chat
Creates single executable with PyInstaller
"""

import os
import shutil
import sys
from pathlib import Path

def create_build():
    """Create PyInstaller build"""
    
    # Clean previous builds
    for dir_name in ['build', 'dist']:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
    
    # Create spec file
    spec_content = f'''
# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('static', 'static'),
    ],
    hiddenimports=[
        'flask',
        'cryptography',
        'netifaces',
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=2,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='SecureLocalChat',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SecureLocalChat',
)
'''
    
    # Write spec file
    with open('SecureLocalChat.spec', 'w') as f:
        f.write(spec_content)
    
    # Run PyInstaller
    os.system('pyinstaller --clean --onefile --windowed SecureLocalChat.spec')
    
    print("\n" + "="*50)
    print("Build completed successfully!")
    print("="*50)
    print("\nExecutable location: dist/SecureLocalChat.exe")
    print("\nFile size should be approximately 8-12MB")
    print("\nRequirements for distribution:")
    print("1. Single .exe file: dist/SecureLocalChat.exe")
    print("2. Optional: Include README.txt in a .zip archive")
    print("3. No installer needed - runs directly!")
    print("\nTest the executable by double-clicking it.")
    print("="*50)

if __name__ == '__main__':
    # Check required files
    required_files = [
        'app.py',
        'security.py',
        'database.py',
        'network.py',
        'templates/setup.html',
        'templates/login.html',
        'templates/chat.html',
        'static/style.css',
        'app.ico'
    ]
    
    missing_files = []
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)
    
    if missing_files:
        print("Error: Missing required files:")
        for file in missing_files:
            print(f"  - {file}")
        print("\nPlease ensure all files are in place before building.")
        sys.exit(1)
    
    create_build()