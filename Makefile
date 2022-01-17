
venv:
	pipenv install

clean:
	find -name '*~' -exec rm {} \;
	find -name '*pyc' -exec rm {} \;
	rm -rf build dist garminexport.egg-info

test:
	nosetests --verbose --with-coverage --cover-package=garminexport --cover-branches

wheel:
	python setup.py bdist_wheel
	@echo "wheel found at:"
	find . -type f -name \*.whl

reinstall:	wheel
	pip install `find . -type f -name \*.whl` --force-reinstall
