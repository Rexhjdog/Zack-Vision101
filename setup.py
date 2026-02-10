#!/usr/bin/env python3
"""
Quick setup script for the Stock Alert Bot
"""
import os
import sys
import subprocess

def check_python_version():
    """Check if Python 3.8+ is installed"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        sys.exit(1)
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detected")

def install_dependencies():
    """Install required packages"""
    print("\n📦 Installing dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Dependencies installed successfully")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        sys.exit(1)

def setup_env_file():
    """Create .env file if it doesn't exist"""
    if os.path.exists('.env'):
        print("✅ .env file already exists")
        return
    
    print("\n📝 Creating .env file...")
    
    print("\n🔑 You need a Discord bot token to run this bot.")
    print("Get one at: https://discord.com/developers/applications")
    print("Create a new application → Bot → Add Bot → Copy Token")
    
    token = input("\nEnter your Discord bot token: ").strip()
    
    if not token:
        print("❌ Token is required")
        sys.exit(1)
    
    print("\n📢 You need a channel ID where alerts will be sent.")
    print("In Discord: Right-click channel → Copy Channel ID (enable Developer Mode in settings)")
    
    channel_id = input("Enter channel ID: ").strip()
    
    if not channel_id:
        print("❌ Channel ID is required")
        sys.exit(1)
    
    with open('.env', 'w') as f:
        f.write(f"DISCORD_TOKEN={token}\n")
        f.write(f"DISCORD_CHANNEL_ID={channel_id}\n")
    
    print("✅ .env file created")

def create_database():
    """Initialize the database"""
    print("\n🗄️  Initializing database...")
    try:
        from database import Database
        db = Database()
        print("✅ Database initialized")
    except Exception as e:
        print(f"❌ Failed to initialize database: {e}")
        sys.exit(1)

def main():
    """Main setup function"""
    print("🎴 Setting up Pokémon/One Piece Stock Alert Bot...\n")
    
    check_python_version()
    install_dependencies()
    setup_env_file()
    create_database()
    
    print("\n" + "="*50)
    print("✅ Setup complete!")
    print("="*50)
    print("\nTo start the bot, run:")
    print("  python bot.py")
    print("\nThe bot will:")
    print("  • Check stock every 2 minutes")
    print("  • Send alerts to your Discord channel")
    print("  • Track product history in the database")
    print("\nUse /help_bot in Discord to see available commands")
    print("="*50)

if __name__ == '__main__':
    main()
