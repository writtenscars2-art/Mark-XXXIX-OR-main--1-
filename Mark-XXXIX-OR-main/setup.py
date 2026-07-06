import subprocess
import sys
import os

# Ensure we run relative to this script's directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

print("Installing requirements...")
subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)

print("Installing Playwright browsers...")
subprocess.run([sys.executable, "-m", "playwright", "install"], check=True)

print("\n✅ Setup complete! Run 'python main.py' to start MARK XXV.")

