from setuptools import setup

setup(
    name='auri',
    version='0.1.6',
    packages=['auri'],
    url='https://github.com/MrTrustworthy/auri',
    download_url='https://github.com/MrTrustworthy/auri/archive/0.1.0.tar.gz',
    license='MIT',
    install_requires=['requests', 'colorama', 'pillow', 'jsonschema', 'click'],
    author='MrTrustworthy',
    author_email='tinywritingmakesmailhardtoread@gmail.com',
    description='An Aurora Nanoleaf CLI',
    keywords=['smarthome', 'cli'],
    classifiers=[],
    entry_points={
        'console_scripts': ['auri=auri:cli'],
    }
)