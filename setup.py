from setuptools import setup, find_packages

setup(
    name="crypto_hft_tool",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "fastapi>=0.68.0",
        "uvicorn>=0.15.0",
        "pandas>=1.3.0",
        "pydantic>=1.8.0",
        "python-dotenv>=0.19.0",
        "websockets>=10.0",
        "numpy>=1.21.0",
        "ccxt>=1.60.0"
    ],
    python_requires=">=3.9",
    author="Your Name",
    author_email="your.email@example.com",
    description="A High-Frequency Trading Tool for Cryptocurrency Markets",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/flowistic-ai/high-frequency-trading",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Financial and Insurance Industry",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.9",
    ],
)
