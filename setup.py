from setuptools import setup

setup(name="garminexport",
      version="1.0.0",
      description=("A program that downloads all activities for a given Garmin Connect account "
                   "and stores them locally on the user's computer."),
      long_description=open('README.md').read(),
      long_description_content_type="text/markdown",
      author="Peter Gardfjäll",
      author_email="peter.gardfjall.work@gmail.com",
      install_requires=open('requirements.txt').read(),
      license="Apache Software License",
      url="https://github.com/petergardfjall/garminexport",
      packages=["garminexport"],
      classifiers=[
          'Development Status :: 4 - Beta',
          'Intended Audience :: Developers',
          'Intended Audience :: End Users/Desktop',
          'Natural Language :: English',
          'License :: OSI Approved :: Apache Software License',
          'Programming Language :: Python :: 2.7',
          "Programming Language :: Python :: 3",
          "Programming Language :: Python :: 3.7"
      ])
