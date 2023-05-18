SHELL := /bin/bash
# directory to hold virtualenv
VENV_DIR?=${PWD}/.venv
VENV_ACTIVATE=$(VENV_DIR)/bin/activate

# creates the virtualenv unless it already exists
$(VENV_DIR):
	python -m venv $(VENV_DIR)
	(source $(VENV_DIR)/bin/activate ; pip install pip-tools)

venv: $(VENV_DIR)

# install pinned dependencies and package itself in editable mode
dep-sync: $(VENV_DIR)
	(source $(VENV_ACTIVATE); pip install -r requirements-dev.txt ; pip install -e . --no-deps)

# creates a virtualenv with development dependencies installed
dev-init: dep-sync
	@echo
	@echo "Development virtualenv prepared! Activate with:"
	@echo "  source $(VENV_ACTIVATE)"

# update pinned versions of abstract dependencies from setup.py
dep-update:
	(source $(VENV_ACTIVATE) ; pip-compile --upgrade --resolver=backtracking -o requirements.txt)
	(source $(VENV_ACTIVATE) ; pip-compile --upgrade --resolver=backtracking --extra test -o requirements-dev.txt)


# build release under 'dist/'
dist:
	python setup.py sdist bdist_wheel

# push release archives to PyPi
publish: dist
	twine check --strict dist/*
	twine upload dist/*
	rm -rf build dist garminexport.egg-info

clean:
	find -name '*~' -exec rm {} \;
	find -name '*pyc' -exec rm {} \;
	rm -rf build dist garminexport.egg-info

test:
	pytest --cov=garminexport

ci-test:
	pytest tests --junitxml=report.xml
