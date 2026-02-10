from setuptools import setup, find_packages

setup(
    name="zack-vision",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "discord.py>=2.3.0",
        "aiohttp>=3.8.0",
        "aiosqlite>=0.19.0",
        "beautifulsoup4>=4.12.0",
        "python-dotenv>=1.0.0",
    ],
    python_requires=">=3.10",
)
