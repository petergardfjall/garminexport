"""Setup information for the Garmin Connect activity exporter."""

from setuptools import setup, Extension
from os import path
# needed for Python 2.7 (ensures open() defaults to text mode with universal
# newlines, and accepts an argument to specify the text encoding.
from io import open

here = path.abspath(path.dirname(__file__))

with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

requires = [
    'requests>=2.0,<3',
    'python-dateutil~=2.4',
    'cloudscraper~=1.2.0',
]

test_requires = [
    'nose~=1.3',
    'coverage~=4.2',
    'mock~=2.0',
]

setup(name='garminexport',
      version='0.4.0',
      description='Garmin Connect activity exporter and backup tool',
      long_description=long_description,
      long_description_content_type='text/markdown',
      author='Peter Gardfjäll',
      author_email='peter.gardfjall.work@gmail.com',

      classifiers=[
          'Development Status :: 4 - Beta',
          'Intended Audience :: Developers',
          'Intended Audience :: End Users/Desktop',
          'Intended Audience :: Developers',
          'Natural Language :: English',
          'License :: OSI Approved :: Apache Software License',
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.5',
          'Programming Language :: Python :: 3.6',
          'Programming Language :: Python :: 3.7',
          'Programming Language :: Python :: 3.8',
      ],
      keywords='garmin export backup',
      url='https://github.com/petergardfjall/garminexport',
      license='Apache License 2.0',

      project_urls={
          'Source': 'https://github.com/petergardfjall/garminexport.git',
          'Tracker': 'https://github.com/petergardfjall/garminexport/issues',
      },

      packages=[
          'garminexport',
          'garminexport.cli',
      ],

      python_requires='>=3.5.*, <4',
      install_requires=requires,
      test_requires=test_requires,
      entry_points={
        'console_scripts': [
            'garmin-backup = garminexport.cli.backup:main',
            'garmin-get-activity = garminexport.cli.get_activity:main',
            'garmin-upload-activity = garminexport.cli.upload_activity:main',
        ],
      },
)
