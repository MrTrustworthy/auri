from setuptools import setup

VERSION = '0.1.8'

setup(
    name='auri',
    version=VERSION,
    packages=['auri'],
    url='https://github.com/MrTrustworthy/auri',
    download_url=f'https://github.com/MrTrustworthy/auri/archive/{VERSION}.tar.gz',
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