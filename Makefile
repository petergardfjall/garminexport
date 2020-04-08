
venv:
	pipenv install

clean:
	find -name '*~' -exec rm {} \;
	find -name '*pyc' -exec rm {} \;

test:
	nosetests --verbose --with-coverage --cover-package=garminexport --cover-branches
