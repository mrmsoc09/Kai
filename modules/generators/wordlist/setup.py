from setuptools import setup, find_packages

setup(
    name="custom-wordlist-generator",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "aiohttp>=3.13.4",
        "beautifulsoup4>=4.11.0",
        "lxml>=4.9.0",
        "tldextract>=3.4.0",
        "pydantic>=2.0.0",
        "rich>=13.0.0",
        "asyncio-throttle>=1.0.0",
    ],
    entry_points={
        "console_scripts": [
            "wordlist-gen=wordlist_generator.cli:main",
        ],
    },
    python_requires=">=3.9",
)
