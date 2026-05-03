from setuptools import setup, find_packages

setup(
    name="nuclei-template-generator",
    version="1.0.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "pyyaml>=6.0",
        "jinja2>=3.1.0",
        "requests>=2.28.0",
        "pydantic>=2.0.0",
        "click>=8.1.0",
        "rich>=13.0.0",
    ],
    entry_points={
        "console_scripts": [
            "nuclei-gen=nuclei_generator.cli:main",
        ],
    },
    python_requires=">=3.8",
)
